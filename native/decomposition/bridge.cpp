#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <sddl.h>
#include <atomic>
#include <array>
#include <cstring>
#include <cwchar>
#include <mutex>
#include <string>
#include <algorithm>
#include "decomposition.h"
#include "verified_profile.h"
#include "bridge_protocol.h"

namespace {
using namespace keke::bridge;
HMODULE self_module{};
Session session{};
std::atomic<bool> started{false}, stopped{false}, subscribed{false}, pending{false};
std::atomic<DWORD> game_thread{0};
std::atomic<ULONGLONG> last_tick{0};
std::atomic<std::uintptr_t> tick_function{0}, live_ui{0};
std::mutex queue_mutex;
Packet queued{};
Reply completed{};
HANDLE completion_event{};
std::atomic<bool> performing{false};
std::string state_message = "initializing";
std::mutex message_mutex;
template<class T> T Resolve(HMODULE module,const char* name) {
    T result{}; FARPROC address=module ? GetProcAddress(module,name) : nullptr;
    static_assert(sizeof(result)==sizeof(address));
    std::memcpy(&result,&address,sizeof(result)); return result;
}

void Message(const char* text) {
    std::lock_guard<std::mutex> lock(message_mutex); state_message = text;
    OutputDebugStringA(text);
    if (self_module) {
        std::array<wchar_t,32768> path{};
        GetModuleFileNameW(self_module,path.data(),static_cast<DWORD>(path.size()));
        auto slash=wcsrchr(path.data(),L'\\');
        if (slash) {
            slash[1]=0;
            const auto log=std::wstring(path.data())+L"bridge-"+std::to_wstring(GetCurrentProcessId())+L".log";
            HANDLE file=CreateFileW(log.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                                    nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if (file!=INVALID_HANDLE_VALUE) { DWORD bytes{}; WriteFile(file,text,static_cast<DWORD>(strlen(text)),&bytes,nullptr); WriteFile(file,"\r\n",2,&bytes,nullptr); CloseHandle(file); }
        }
    }
}
void MessageError(const char* text, DWORD error) {
    const auto detail=std::string(text)+" (win32="+std::to_string(error)+")";
    Message(detail.c_str());
}
template<class T> bool Read(std::uintptr_t address, T& value) {
    SIZE_T bytes{};
    return address && ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address),
                                       &value, sizeof(value), &bytes) && bytes == sizeof(value);
}
std::uintptr_t Base() { return reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr)); }
std::string Name(std::uintptr_t object) {
    std::uint32_t token{}, block_count{};
    if (!Read(object+24, token) || !Read(Base()+keke::decomposition::profile::name_pool_rva+8, block_count)
        || block_count >= 512 || (token>>16) > block_count) return {};
    std::uintptr_t block{};
    if (!Read(Base()+keke::decomposition::profile::name_pool_rva+16+8*(token>>16), block)) return {};
    const auto entry = block+2*(token & 0xffff);
    std::uint16_t header{};
    if (!Read(entry, header)) return {};
    const auto length = header>>6;
    if ((header&1) || !length || length > 128) return {};
    std::array<char,129> text{};
    SIZE_T copied{};
    if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(entry+2),
                           text.data(), length, &copied) || copied != static_cast<SIZE_T>(length)) return {};
    return std::string(text.data(), length);
}
bool LiveUi(std::uintptr_t object) {
    std::uint32_t flags{}; std::uintptr_t cls{}, outer{};
    if (!Read(object+8, flags) || (flags & 0x30) || !Read(object+16, cls)
        || Name(cls) != "BPUI_EquipDecomposeTips_C") return false;
    outer = object;
    for (int i=0; i<6; ++i) {
        if (!Read(outer+32, outer) || !outer) return false;
        if (Name(outer) == "W_OverallUILayout_C") return true;
    }
    return false;
}
std::uintptr_t FindUi() {
    const auto cached = live_ui.load();
    if (LiveUi(cached)) return cached;
    std::uintptr_t chunks{};
    std::int32_t count{}, chunk_count{};
    const auto registry = Base()+keke::decomposition::profile::object_registry_rva;
    if (!Read(registry, chunks) || !Read(registry+20, count) || !Read(registry+28, chunk_count)
        || count < 1 || count > 1000000 || chunk_count < 1 || chunk_count > 64) return 0;
    std::uintptr_t found{};
    for (int i=0; i<count; ++i) {
        std::uintptr_t chunk{}, object{}, cls{}; std::int32_t index{};
        if (!Read(chunks+8*(i/65536), chunk) || !Read(chunk+24*(i%65536), object)
            || !Read(object+12, index) || index != i || !Read(object+16, cls)) continue;
        if (Name(cls) != "BPUI_EquipDecomposeTips_C" || !LiveUi(object)) continue;
        if (found) return 0;
        found = object;
    }
    live_ui.store(found);
    return found;
}
bool Selected(const Packet& packet) {
    const auto ui = live_ui.load();
    std::uintptr_t data{}, object{}; std::int32_t count{};
    keke::decomposition::ItemUid uid{};
    return LiveUi(ui) && Read(ui+0x1380, data) && Read(ui+0x1388, count) && count == 1
        && Read(data, object) && Read(object+0x30, uid)
        && uid.slot == packet.slot && uid.serial == packet.serial;
}
Reply Status(std::uint64_t id=0) {
    Reply result{};
    result.magic=magic; result.version=version; result.request_id=id;
    result.game_thread=game_thread.load();
    result.ready=!stopped.load() && subscribed.load() && result.game_thread
        && GetTickCount64()-last_tick.load()<10000;
    std::lock_guard<std::mutex> lock(message_mutex);
    const auto length=(std::min)(state_message.size(), sizeof(result.message)-1);
    std::memcpy(result.message,state_message.data(),length);
    return result;
}
bool OnGameThread(void*) {
    return !stopped.load() && GetCurrentThreadId()==game_thread.load()
        && GetCurrentThreadId()==session.window_thread && performing.load();
}
bool Armed(void*) {
    return !stopped.load() && queued.confirmations==7 && GetTickCount64()<=queued.deadline_ms;
}
bool Fresh(void*, const keke::decomposition::ItemUid* uid, std::size_t count, std::uint64_t revision) {
    return Armed(nullptr) && count==1 && revision==queued.snapshot_revision
        && uid->slot==queued.slot && uid->serial==queued.serial && Selected(queued);
}
void* Player(void*) {
    if (!OnGameThread(nullptr)) return nullptr;
    using Getter=void*(*)();
    return reinterpret_cast<Getter>(Base()+keke::decomposition::profile::player_getter_rva)();
}
void ExecutePending() {
    if (stopped.load() || !game_thread.load() || GetCurrentThreadId()!=game_thread.load()) return;
    if (performing.load() || !pending.exchange(false)) return;
    performing.store(true);
    keke::decomposition::Host host{nullptr,OnGameThread,Armed,Fresh,Player};
    const keke::decomposition::ItemUid uid{queued.slot,queued.serial};
    const keke::decomposition::Request request{queued.request_id,queued.snapshot_revision,&uid,1,
        static_cast<keke::decomposition::Material>(queued.material)};
    const auto result=keke::decomposition::SubmitOnGameThread(host,request);
    {
        std::lock_guard<std::mutex> lock(queue_mutex);
        completed=Status(request.request_id);
        completed.sender_result=static_cast<std::uint32_t>(result);
    }
    performing.store(false);
    SetEvent(completion_event);
}
void Observe(const void*, void* function, const void*) {
    if (stopped.load() || GetCurrentThreadId()!=session.window_thread) return;
    const auto address=reinterpret_cast<std::uintptr_t>(function);
    auto tick=tick_function.load();
    if (!tick) {
        if (Name(address)!="ReceiveTick") return;
        tick_function.store(address); tick=address;
        game_thread.store(GetCurrentThreadId());
        Message("ready: observed ReceiveTick on game window thread");
    }
    if (address!=tick) return;
    last_tick.store(GetTickCount64());
    ExecutePending();
}
bool Transfer(HANDLE pipe, bool write, void* data, DWORD size) {
    OVERLAPPED operation{}; operation.hEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    if (!operation.hEvent) return false;
    DWORD bytes{};
    BOOL ok=write ? WriteFile(pipe,data,size,&bytes,&operation) : ReadFile(pipe,data,size,&bytes,&operation);
    if (!ok && GetLastError()==ERROR_IO_PENDING) {
        if (WaitForSingleObject(operation.hEvent,3000)!=WAIT_OBJECT_0) {
            CancelIoEx(pipe,&operation); WaitForSingleObject(operation.hEvent,INFINITE);
        }
        ok=GetOverlappedResult(pipe,&operation,&bytes,FALSE);
    }
    CloseHandle(operation.hEvent);
    return ok && bytes==size;
}
bool WakeGameQueue() {
    bool posted=false;
    const HWND window=reinterpret_cast<HWND>(session.window);
    DWORD owner_pid{};
    const DWORD window_thread=IsWindow(window) ? GetWindowThreadProcessId(window,&owner_pid) : 0;
    if (window_thread==session.window_thread && owner_pid==session.pid)
        posted=PostMessageW(window,WM_NULL,0,0)!=FALSE;
    if (session.window_thread)
        posted=PostThreadMessageW(session.window_thread,WM_NULL,0,0)!=FALSE || posted;
    return posted;
}
DWORD WINAPI Worker(void*) {
    if (!keke::decomposition::VerifyRuntimeProfile()) { Message("unsupported game/runtime code"); return 0; }
    using OpenOwner=bool(*)(void*);
    using ObserveApi=bool(*)(void*,void(*)(const void*,void*,const void*));
    HMODULE host=GetModuleHandleW(L"d3d12.dll");
    auto open=Resolve<OpenOwner>(host,"?OpenOwner@NativeHooks@NTE@@YA_NPEAX@Z");
    auto observe=Resolve<ObserveApi>(host,"?Observe@ProcessEvents@NTE@@YA_NPEAXP6AXPEBVUObject@SDK@@PEAVUFunction@4@0@Z@Z");
    if (!open || !observe || !open(self_module) || !observe(self_module,Observe))
        Message("native host event observation unavailable/rejected");
    else { subscribed.store(true); Message("waiting for ReceiveTick on game window thread"); }
    FindUi();
    completion_event=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    // Pipe access is restricted to the current token's user and SYSTEM.
    HANDLE token{}; DWORD required{};
    if (!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)) return 0;
    GetTokenInformation(token,TokenUser,nullptr,0,&required);
    std::string token_buffer(required,'\0');
    if (!GetTokenInformation(token,TokenUser,token_buffer.data(),required,&required)) { CloseHandle(token); return 0; }
    CloseHandle(token);
    LPWSTR sid{};
    if (!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(token_buffer.data())->User.Sid,&sid)) return 0;
    const std::wstring sddl=L"D:P(A;;GA;;;SY)(A;;GA;;;"+std::wstring(sid)+L")S:(ML;;NW;;;ME)";
    LocalFree(sid);
    PSECURITY_DESCRIPTOR descriptor{};
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(),SDDL_REVISION_1,&descriptor,nullptr)) return 0;
    SECURITY_ATTRIBUTES attributes{sizeof(attributes),descriptor,FALSE};
    const auto pipe_name=L"\\\\.\\pipe\\KekeDecompose-"+std::to_wstring(GetCurrentProcessId());
    while (!stopped.load()) {
        HANDLE pipe=CreateNamedPipeW(pipe_name.c_str(),PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,sizeof(Reply),sizeof(Packet),3000,&attributes);
        if (pipe==INVALID_HANDLE_VALUE) { Message("cannot create private bridge pipe"); break; }
        OVERLAPPED connect{}; connect.hEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
        BOOL connected=ConnectNamedPipe(pipe,&connect);
        if (!connected && GetLastError()==ERROR_IO_PENDING) {
            WaitForSingleObject(connect.hEvent,INFINITE);
            DWORD unused{}; connected=GetOverlappedResult(pipe,&connect,&unused,FALSE);
        } else if (!connected && GetLastError()==ERROR_PIPE_CONNECTED) connected=TRUE;
        CloseHandle(connect.hEvent);
        Packet packet{};
        if (connected && Transfer(pipe,false,&packet,sizeof(packet))) {
            Reply reply=Status(packet.request_id);
            if (packet.magic!=magic || std::memcmp(packet.secret,session.secret,32)) reply.transport=1;
            else if (packet.op==1) {}
            else if (packet.op==3 && !performing.load()) {
                stopped.store(true); reply.ready=0; Message("stopped; restart game before reloading");
                const auto event_name=L"Local\\KekeDecomposeStop-"+std::to_wstring(GetCurrentProcessId());
                HANDLE event=OpenEventW(EVENT_MODIFY_STATE,FALSE,event_name.c_str());
                if (event) { SetEvent(event); CloseHandle(event); }
            }
            else if (packet.op!=2 || packet.confirmations!=7 || !packet.request_id || !packet.snapshot_revision
                || packet.deadline_ms<GetTickCount64() || packet.deadline_ms>GetTickCount64()+15000
                || (packet.material!=1 && packet.material!=2)) reply.transport=2;
            else if (!reply.ready || !FindUi()) reply.transport=3;
            else {
                ResetEvent(completion_event);
                { std::lock_guard<std::mutex> lock(queue_mutex); queued=packet; }
                pending.store(true);
                // Wake the same HWND queue that activated WH_GETMESSAGE. A
                // thread message alone may be filtered by the game's pump.
                if (!WakeGameQueue()) Message("request queued; window and thread wake posts failed, waiting for next game tick");
                if (WaitForSingleObject(completion_event,12000)==WAIT_OBJECT_0) {
                    std::lock_guard<std::mutex> lock(queue_mutex); reply=completed;
                } else { stopped.store(true); pending.store(false); reply.transport=4; reply.ready=0; }
            }
            Transfer(pipe,true,&reply,sizeof(reply));
        }
        DisconnectNamedPipe(pipe); CloseHandle(pipe);
    }
    LocalFree(descriptor);
    return 0;
}
void Start() {
    if (started.exchange(true)) return;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&Start),&self_module)) {
        MessageError("startup failed: cannot pin bridge module",GetLastError());
        return;
    }
    Message("hook callback entered; bridge module pinned");
    std::array<wchar_t,32768> path{};
    GetModuleFileNameW(self_module,path.data(),static_cast<DWORD>(path.size()));
    auto slash=wcsrchr(path.data(),L'\\');
    if (!slash) { Message("startup failed: cannot resolve bridge module directory"); return; }
    slash[1]=0;
    const auto file=std::wstring(path.data())+L"bridge-session-"+std::to_wstring(GetCurrentProcessId())+L".bin";
    HANDLE input=CreateFileW(file.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    if (input==INVALID_HANDLE_VALUE) {
        MessageError("startup failed: cannot open bridge session",GetLastError());
        return;
    }
    DWORD bytes{};
    const bool read=ReadFile(input,&session,sizeof(session),&bytes,nullptr)!=FALSE;
    const auto read_error=read ? ERROR_SUCCESS : GetLastError();
    CloseHandle(input);
    if (!read) { MessageError("startup failed: cannot read bridge session",read_error); return; }
    if (bytes!=sizeof(session)) { Message("startup failed: bridge session has unexpected size"); return; }
    if (session.magic!=magic || session.version!=version) { Message("startup failed: bridge session protocol mismatch"); return; }
    if (session.pid!=GetCurrentProcessId()) { Message("startup failed: bridge session PID mismatch"); return; }
    if (session.window_thread!=GetCurrentThreadId()) { Message("startup failed: hook callback thread mismatch"); return; }
    FILETIME created{},exited{},kernel{},user{};
    if (!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user)) {
        MessageError("startup failed: cannot read process creation time",GetLastError());
        return;
    }
    const auto creation=(static_cast<std::uint64_t>(created.dwHighDateTime)<<32)|created.dwLowDateTime;
    if (session.process_creation!=creation) { Message("startup failed: game process creation time mismatch"); return; }
    HANDLE thread=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);
    if (!thread) { MessageError("startup failed: cannot create bridge worker",GetLastError()); return; }
    CloseHandle(thread);
    Message("bridge worker started");
}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK KekeBridgeHook(int code,WPARAM wparam,LPARAM lparam) {
    if (code>=0) {
        Start();
        if (!stopped.load() && game_thread.load() && GetCurrentThreadId()==game_thread.load()) {
            last_tick.store(GetTickCount64());
            ExecutePending();
        }
    }
    return CallNextHookEx(nullptr,code,wparam,lparam);
}
