#pragma once
#include <cstddef>
#include <cstdint>

namespace keke::decomposition {

// No default material: the UI must provide one of these explicitly.
enum class Material : std::uint32_t { Experience = 1, Rewind = 2 };
struct ItemUid { std::uint32_t slot; std::uint32_t serial; };
static_assert(sizeof(ItemUid) == 8);

enum class Result {
    InvalidInput, HostUnavailable, WrongThread, RiskModeDisabled,
    SelectionChanged, UnsupportedGame, RuntimeCodeChanged, InvalidPlayerState,
    RequestAlreadyConsumed, RequestCapacityReached, AllocationFailed,
    MessageContractChanged, Busy, SessionStopped, SubmittedOutcomeUnconfirmed
};

// Implement inside an authorized native host. Never call this from a Python
// thread or a transport thread. These checks must consult current engine state.
struct Host {
    void* context;
    bool (*is_game_thread)(void*);
    bool (*risk_mode_enabled)(void*);
    bool (*validate_frozen_selection)(void*, const ItemUid*, std::size_t,
                                       std::uint64_t snapshot_revision);
    void* (*current_player_state)(void*);
};

struct Request {
    std::uint64_t request_id;
    std::uint64_t snapshot_revision;
    const ItemUid* items;
    std::size_t count;
    Material material;
};

// Initial native integration deliberately accepts one item per explicit request.
// Returning SubmittedOutcomeUnconfirmed means only that dispatch returned.
// It never means the server destroyed an item. Do not automatically retry.
Result SubmitOnGameThread(const Host& host, const Request& request);
bool VerifyRuntimeProfile();

} // namespace keke::decomposition

// C linkage permits an independently built authorized host to resolve one
// narrow entry point. The DLL does not load itself or schedule remote work.
#if defined(KEKE_DECOMPOSITION_DLL)
#define KEKE_DECOMPOSITION_API __declspec(dllexport)
#else
#define KEKE_DECOMPOSITION_API
#endif
extern "C" KEKE_DECOMPOSITION_API keke::decomposition::Result
KekeSubmitNativeDecomposition(const keke::decomposition::Host* host,
                              const keke::decomposition::Request* request) noexcept;
