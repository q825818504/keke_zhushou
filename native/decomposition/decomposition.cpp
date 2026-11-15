#include "decomposition.h"
#include "verified_profile.h"
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <cstring>
#include <mutex>
#include <vector>
#include <cwchar>
#include <new>
#include <atomic>
#if !defined(_M_X64) && !defined(__x86_64__)
#error This researched calling convention requires x86-64.
#endif

namespace keke::decomposition {
namespace {
struct UidArray { ItemUid* data; std::int32_t num; std::int32_t capacity; };
static_assert(sizeof(UidArray) == 16);
struct alignas(8) Message { std::array<std::byte, 32> bytes{}; };
static_assert(sizeof(Message) == 32);

// Explicit hidden-return-buffer ABI observed in the matching Win64 build.
using AllocateArray = void (*)(std::int32_t, std::int32_t, std::int32_t,
                               std::int32_t, void**, std::int32_t, std::int32_t*);
using BuildMessage = Message* (*)(Message*, std::int32_t, bool, UidArray*);
using SendCompose = void (*)(void*, const Message*);
using DestroyParameters = void (*)(void*, std::int32_t);
using GameFree = void (*)(void*);

bool Readable(const void* pointer, std::size_t size) {
    auto cursor = reinterpret_cast<std::uintptr_t>(pointer);
    if (!cursor || !size || cursor + size < cursor) return false;
    const auto end = cursor + size;
    while (cursor < end) {
        MEMORY_BASIC_INFORMATION region{};
        if (!VirtualQuery(reinterpret_cast<void*>(cursor), &region, sizeof(region))
            || region.State != MEM_COMMIT
            || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return false;
        const auto next = reinterpret_cast<std::uintptr_t>(region.BaseAddress) + region.RegionSize;
        if (next <= cursor) return false;
        cursor = next;
    }
    return true;
}

bool MatchingExecutable() {
    std::array<wchar_t, 32768> path{};
    const auto length = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!length || length >= path.size()) return false;
    const auto leaf = wcsrchr(path.data(), L'\\');
    if (!leaf || _wcsicmp(leaf + 1, L"HTGame.exe")) return false;
    HANDLE file = CreateFileW(path.data(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                              OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm{};
    BCRYPT_HASH_HANDLE hash{};
    DWORD object_size{}, returned{};
    bool matches = false;
    std::array<unsigned char, 32> digest{};
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0
        && BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH,
            reinterpret_cast<PUCHAR>(&object_size), sizeof(object_size), &returned, 0) >= 0
        && object_size > 0 && object_size <= 1048576) {
        std::vector<unsigned char> object(object_size);
        if (BCryptCreateHash(algorithm, &hash, object.data(), object_size, nullptr, 0, 0) >= 0) {
            std::array<unsigned char, 65536> buffer{};
            DWORD bytes{};
            bool valid = true;
            for (;;) {
                if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &bytes, nullptr)) {
                    valid = false; break;
                }
                if (!bytes) break;
                if (BCryptHashData(hash, buffer.data(), bytes, 0) < 0) { valid = false; break; }
            }
            matches = valid && BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) >= 0
                && digest == profile::game_sha256;
            BCryptDestroyHash(hash);
        }
    }
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    return matches;
}

bool MatchingCode(std::uintptr_t base) {
    for (const auto& signature : profile::signatures) {
        const auto pointer = reinterpret_cast<const void*>(base + signature.rva);
        if (!Readable(pointer, signature.size)
            || std::memcmp(pointer, signature.bytes, signature.size)) return false;
    }
    return true;
}

bool ValidPlayerState(void* object, std::uintptr_t base) {
    if (!Readable(object, sizeof(void*))) return false;
    const auto table = *reinterpret_cast<const std::uintptr_t*>(object);
    if (!Readable(reinterpret_cast<void*>(table + 0x260), sizeof(void*))) return false;
    const auto target = *reinterpret_cast<const std::uintptr_t*>(table + 0x260);
    // The actual engine-class identity is checked by current_player_state.
    // This additional guard verifies the observed ProcessEvent dispatch slot.
    if (target < base || target - base >= profile::image_size) return false;
    MEMORY_BASIC_INFORMATION region{};
    if (!VirtualQuery(reinterpret_cast<void*>(target), &region, sizeof(region))) return false;
    const auto protection = region.Protect & 0xff;
    return region.State == MEM_COMMIT && !(region.Protect & PAGE_GUARD)
        && (protection == PAGE_EXECUTE || protection == PAGE_EXECUTE_READ
            || protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY);
}

std::mutex request_mutex;
std::atomic_flag dispatch_busy = ATOMIC_FLAG_INIT;
std::atomic<bool> session_stopped{false};
struct DispatchGuard {
    bool acquired = !dispatch_busy.test_and_set();
    ~DispatchGuard() { if (acquired) dispatch_busy.clear(); }
};
std::array<std::uint64_t, 1024> consumed{};
std::size_t consumed_count{};
Result Consume(std::uint64_t id) {
    std::lock_guard<std::mutex> guard(request_mutex);
    for (std::size_t i = 0; i < consumed_count; ++i)
        if (consumed[i] == id) return Result::RequestAlreadyConsumed;
    if (consumed_count == consumed.size()) return Result::RequestCapacityReached;
    consumed[consumed_count++] = id;
    return Result::SubmittedOutcomeUnconfirmed;
}
} // namespace

bool VerifyRuntimeProfile() {
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    return base && MatchingExecutable() && MatchingCode(base);
}

Result SubmitOnGameThread(const Host& host, const Request& request) {
    if (session_stopped.load()) return Result::SessionStopped;
    DispatchGuard dispatch;
    if (!dispatch.acquired) return Result::Busy;
    if (!request.request_id || !request.snapshot_revision || request.count != 1
        || !Readable(request.items, sizeof(ItemUid))
        || (request.material != Material::Experience && request.material != Material::Rewind))
        return Result::InvalidInput;
    if (!host.is_game_thread || !host.risk_mode_enabled || !host.validate_frozen_selection
        || !host.current_player_state) return Result::HostUnavailable;
    if (!host.is_game_thread(host.context)) return Result::WrongThread;
    if (!host.risk_mode_enabled(host.context)) return Result::RiskModeDisabled;
    const ItemUid frozen = request.items[0];
    if (!host.validate_frozen_selection(host.context, &frozen, 1, request.snapshot_revision))
        return Result::SelectionChanged;
    if (!MatchingExecutable()) return Result::UnsupportedGame;
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    if (!base || !MatchingCode(base)) return Result::RuntimeCodeChanged;
    void* player = host.current_player_state(host.context);
    if (!ValidPlayerState(player, base)) return Result::InvalidPlayerState;
    // Revalidate after file hashing. A host must reject equipped/locked/unknown,
    // referenced or replaced items and a stale account/snapshot.
    if (!host.risk_mode_enabled(host.context)) return Result::RiskModeDisabled;
    if (!host.validate_frozen_selection(host.context, &frozen, 1, request.snapshot_revision))
        return Result::SelectionChanged;
    const auto reserved = Consume(request.request_id);
    if (reserved != Result::SubmittedOutcomeUnconfirmed) return reserved;

    const auto allocate = reinterpret_cast<AllocateArray>(base + profile::allocator_rva);
    const auto build = reinterpret_cast<BuildMessage>(base + profile::builder_rva);
    const auto send = reinterpret_cast<SendCompose>(base + profile::sender_rva);
    const auto destroy = reinterpret_cast<DestroyParameters>(base + profile::destroy_rva);
    const auto free_game = reinterpret_cast<GameFree>(base + profile::free_rva);
    UidArray input{};
    void* data{};
    allocate(8, 4, 1, 0, &data, 1, &input.capacity);
    if (!data || input.capacity < 1) {
        if (data) free_game(data);
        return Result::AllocationFailed;
    }
    input.data = static_cast<ItemUid*>(data);
    input.num = 1;
    input.data[0] = frozen;
    Message message;
    Message* built = build(&message, 99, request.material == Material::Experience, &input);
    // The verified builder consumes the UID array. Unexpected ownership or
    // message shape prevents dispatch; no request is sent on this path.
    void* parameters{};
    std::int32_t count{}, type{};
    std::memcpy(&parameters, message.bytes.data(), 8);
    std::memcpy(&count, message.bytes.data() + 8, 4);
    std::memcpy(&type, message.bytes.data() + 24, 4);
    if (built != &message || input.data || input.num || input.capacity
        || !parameters || count != 2 || type != 99) {
        // Do not guess how to free a structure whose contract has changed.
        // The native host must stop this session; request ID remains consumed.
        session_stopped.store(true);
        return Result::MessageContractChanged;
    }
    send(player, &message);
    destroy(parameters, count);
    free_game(parameters);
    return Result::SubmittedOutcomeUnconfirmed;
}
} // namespace keke::decomposition

extern "C" KEKE_DECOMPOSITION_API keke::decomposition::Result
KekeSubmitNativeDecomposition(const keke::decomposition::Host* host,
                              const keke::decomposition::Request* request) noexcept {
    using namespace keke::decomposition;
    if (!Readable(host, sizeof(Host)) || !Readable(request, sizeof(Request)))
        return Result::InvalidInput;
    try {
        return SubmitOnGameThread(*host, *request);
    } catch (const std::bad_alloc&) {
        session_stopped.store(true);
        return Result::AllocationFailed;
    } catch (...) {
        // Do not retry after an unexpected exception. No success is implied.
        session_stopped.store(true);
        return Result::MessageContractChanged;
    }
}
