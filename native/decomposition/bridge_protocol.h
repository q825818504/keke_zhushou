#pragma once
#include <cstdint>
namespace keke::bridge {
constexpr std::uint32_t magic = 0x31444b4b; // KKD1
constexpr std::uint32_t version = 1;
#pragma pack(push, 1)
struct Session {
    std::uint32_t magic, version, pid, window_thread;
    std::uint64_t process_creation;
    unsigned char secret[32];
    std::uint64_t window;
};
struct Packet {
    std::uint32_t magic, op; // 1 status, 2 explicit submit, 3 stop
    unsigned char secret[32];
    std::uint64_t request_id, snapshot_revision;
    std::uint32_t slot, serial, material, confirmations;
    std::uint64_t deadline_ms;
};
struct Reply {
    std::uint32_t magic, version, transport, ready;
    std::uint64_t request_id;
    std::uint32_t game_thread, sender_result;
    char message[128];
};
#pragma pack(pop)
static_assert(sizeof(Session) == 64);
static_assert(sizeof(Packet) == 80);
static_assert(sizeof(Reply) == 160);
}
