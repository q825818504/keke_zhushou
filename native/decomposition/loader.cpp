#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <sddl.h>
#include <tlhelp32.h>
#include <array>
#include <vector>
#include <string>
#include <cwchar>
#include <cstring>
#include "verified_profile.h"
#include "bridge_protocol.h"
#include "bridge_expected.h"

namespace {
using namespace keke::bridge;
bool Hash(const wchar_t* path, const std::array<unsigned char,32>& expected) {
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_SEQUENTIAL_SCAN,nullptr);
    if (file==INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm{}; BCRYPT_HASH_HANDLE hash{};
    DWORD size{},returned{}; bool valid=false;
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0
        && BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof(size),&returned,0)>=0
        && size>0 && size<1048576) {
        std::vector<unsigned char> object(size);
        if (BCryptCreateHash(algorithm,&hash,object.data(),size,nullptr,0,0)>=0) {
            std::array<unsigned char,65536> buffer{}; DWORD bytes{}; bool ok=true;
            for (;;) {
                if (!ReadFile(file,buffer.data(),static_cast<DWORD>(buffer.size()),&bytes,nullptr)) { ok=false; break; }
                if (!bytes) break;
                if (BCryptHashData(hash,buffer.data(),bytes,0)<0) { ok=false; break; }
            }
            std::array<unsigned char,32> digest{};
            valid=ok && BCryptFinishHash(hash,digest.data(),static_cast<ULONG>(digest.size()),0)>=0 && digest==expected;
            BCryptDestroyHash(hash);
        }
    }
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm,0);
    CloseHandle(file); return valid;
}
struct Window { DWORD pid; HWND handle{}; LONGLONG area{}; };
BOOL CALLBACK FindWindow(HWND window,LPARAM data) {
    auto& result=*reinterpret_cast<Window*>(data);
    DWORD pid{}; GetWindowThreadProcessId(window,&pid);
    std::array<wchar_t,128> name{}; GetClassNameW(window,name.data(),static_cast<int>(name.size()));
    if (pid!=result.pid || !IsWindowVisible(window) || wcscmp(name.data(),L"UnrealWindow")) return TRUE;
    RECT rect{}; GetClientRect(window,&rect);
    const LONGLONG area=static_cast<LONGLONG>(rect.right-rect.left)*(rect.bottom-rect.top);
    if (area>result.area) { result.area=area; result.handle=window; }
    return TRUE;
}
void Log(const std::wstring& root,const char* text) {
    HANDLE file=CreateFileW((root+L"loader.log").c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                            nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file!=INVALID_HANDLE_VALUE) { DWORD bytes{}; WriteFile(file,text,static_cast<DWORD>(strlen(text)),&bytes,nullptr); WriteFile(file,"\r\n",2,&bytes,nullptr); CloseHandle(file); }
}
void LogPid(const std::wstring& root,DWORD pid,const char* text) {
    const auto entry=std::string("pid=")+std::to_string(pid)+" loader="+
        std::to_string(GetCurrentProcessId())+" "+text;
    Log(root,entry.c_str());
}
struct ModuleProbe { bool checked{}; bool found{}; DWORD error{}; DWORD count{}; };
ModuleProbe ProbeBridgeModule(DWORD pid) {
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);
    if (snapshot==INVALID_HANDLE_VALUE) return {false,false,GetLastError(),0};
    MODULEENTRY32W entry{}; entry.dwSize=sizeof(entry);
    if (!Module32FirstW(snapshot,&entry)) {
        const auto error=GetLastError(); CloseHandle(snapshot);
        return {false,false,error,0};
    }
    DWORD count=0;
    do {
        ++count;
        if (_wcsicmp(entry.szModule,L"KekeDecompositionBridge.dll")==0) {
            CloseHandle(snapshot); return {true,true,ERROR_SUCCESS,count};
        }
        entry.dwSize=sizeof(entry);
    } while (Module32NextW(snapshot,&entry));
    const auto error=GetLastError(); CloseHandle(snapshot);
    return {true,false,error==ERROR_NO_MORE_FILES ? ERROR_SUCCESS : error,count};
}
std::string IntegrityLevel(HANDLE process) {
    HANDLE token{};
    if (!OpenProcessToken(process,TOKEN_QUERY,&token)) return "unknown";
    DWORD required{};
    GetTokenInformation(token,TokenIntegrityLevel,nullptr,0,&required);
    std::vector<unsigned char> buffer(required);
    if (!required || !GetTokenInformation(token,TokenIntegrityLevel,buffer.data(),required,&required)) {
        CloseHandle(token); return "unknown";
    }
    const auto* label=reinterpret_cast<const TOKEN_MANDATORY_LABEL*>(buffer.data());
    const auto* count=GetSidSubAuthorityCount(label->Label.Sid);
    const DWORD rid=count && *count ? *GetSidSubAuthority(label->Label.Sid,*count-1) : 0;
    CloseHandle(token);
    if (rid>=0x4000) return "system";
    if (rid>=0x3000) return "high";
    if (rid>=0x2000) return "medium";
    return "low";
}
std::string ProcessContext(HANDLE process) {
    BOOL wow64{};
    const std::string arch=IsWow64Process(process,&wow64) ? (wow64 ? "x86" : "x64") : "unknown";
    DWORD session{};
    const std::string session_text=ProcessIdToSessionId(GetProcessId(process),&session)
        ? std::to_string(session) : "unknown";
    DWORD signature{},dynamic_code{},protection=0xffffffff;
    using QueryMitigation=BOOL(WINAPI*)(HANDLE,int,PVOID,SIZE_T);
    using QueryInformation=BOOL(WINAPI*)(HANDLE,int,PVOID,DWORD);
    const auto kernel=GetModuleHandleW(L"kernel32.dll");
    const auto mitigation_address=GetProcAddress(kernel,"GetProcessMitigationPolicy");
    const auto information_address=GetProcAddress(kernel,"GetProcessInformation");
    QueryMitigation mitigation{}; QueryInformation information{};
    static_assert(sizeof(mitigation)==sizeof(mitigation_address));
    static_assert(sizeof(information)==sizeof(information_address));
    std::memcpy(&mitigation,&mitigation_address,sizeof(mitigation));
    std::memcpy(&information,&information_address,sizeof(information));
    const bool has_signature=mitigation && mitigation(process,8,&signature,sizeof(signature));
    const bool has_dynamic=mitigation && mitigation(process,2,&dynamic_code,sizeof(dynamic_code));
    const bool has_protection=information && information(process,7,&protection,sizeof(protection));
    return "arch="+arch+" session="+session_text+" integrity="+IntegrityLevel(process)+
        " sig="+(has_signature ? std::to_string(signature) : "unknown")+
        " dyn="+(has_dynamic ? std::to_string(dynamic_code) : "unknown")+
        " protection="+(has_protection ? std::to_string(protection) : "unknown");
}
}
int wmain(int argc,wchar_t** argv) {
    using namespace keke::bridge;
    std::array<wchar_t,32768> location{};
    GetModuleFileNameW(nullptr,location.data(),static_cast<DWORD>(location.size()));
    auto slash=wcsrchr(location.data(),L'\\'); if (!slash) return 1; slash[1]=0;
    const std::wstring root=location.data();
    if (argc!=3 || wcscmp(argv[1],L"--pid")) { Log(root,"usage: KekeDecompositionLoader --pid GAME_PID"); return 2; }
    wchar_t* end{}; const auto number=wcstoul(argv[2],&end,10);
    if (!number || *end) return 2;
    const DWORD pid=number;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid);
    if (!process) { Log(root,"cannot query game; run loader with administrator privileges"); return 3; }
    std::array<wchar_t,32768> game{}; DWORD length=static_cast<DWORD>(game.size());
    if (!QueryFullProcessImageNameW(process,0,game.data(),&length)
        || !Hash(game.data(),keke::decomposition::profile::game_sha256)) {
        Log(root,"unsupported game executable/version"); CloseHandle(process); return 4;
    }
    Window window{pid}; EnumWindows(FindWindow,reinterpret_cast<LPARAM>(&window));
    if (!window.handle) { Log(root,"no visible Unreal game window"); CloseHandle(process); return 5; }
    const auto dll=root+L"KekeDecompositionBridge.dll";
    if (!Hash(dll.c_str(),keke_bridge_expected_sha256)) { Log(root,"bridge DLL checksum mismatch"); CloseHandle(process); return 6; }
    HANDLE token{}; DWORD required{};
    if (!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)) return 7;
    GetTokenInformation(token,TokenUser,nullptr,0,&required);
    std::vector<unsigned char> user(required);
    if (!GetTokenInformation(token,TokenUser,user.data(),required,&required)) return 7;
    CloseHandle(token);
    LPWSTR sid{};
    if (!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(user.data())->User.Sid,&sid)) return 7;
    const std::wstring sddl=L"D:P(A;;GA;;;SY)(A;;GA;;;"+std::wstring(sid)+L")";
    LocalFree(sid);
    PSECURITY_DESCRIPTOR descriptor{};
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(),SDDL_REVISION_1,&descriptor,nullptr)) return 7;
    SECURITY_ATTRIBUTES attributes{sizeof(attributes),descriptor,FALSE};
    const auto stop_name=L"Local\\KekeDecomposeStop-"+std::to_wstring(pid);
    SetLastError(ERROR_SUCCESS);
    HANDLE stop=CreateEventW(&attributes,TRUE,FALSE,stop_name.c_str());
    if (!stop) {
        const auto error=GetLastError();
        LogPid(root,pid,(std::string("cannot create loader stop event; win32=")+std::to_string(error)).c_str());
        LocalFree(descriptor); CloseHandle(process); return 8;
    }
    if (GetLastError()==ERROR_ALREADY_EXISTS) {
        LogPid(root,pid,"loader already active for this game process");
        CloseHandle(stop); LocalFree(descriptor); CloseHandle(process); return 8;
    }
    Session session{}; session.magic=magic; session.version=version; session.pid=pid;
    session.window_thread=GetWindowThreadProcessId(window.handle,nullptr);
    session.window=reinterpret_cast<std::uint64_t>(window.handle);
    LogPid(root,pid,(std::string("target ")+ProcessContext(process)+" window=0x"+
        std::to_string(reinterpret_cast<std::uintptr_t>(window.handle))+" thread="+
        std::to_string(session.window_thread)).c_str());
    FILETIME creation{},exit{},kernel{},cpu{};
    if (!GetProcessTimes(process,&creation,&exit,&kernel,&cpu)
        || BCryptGenRandom(nullptr,session.secret,32,BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0) return 9;
    session.process_creation=(static_cast<std::uint64_t>(creation.dwHighDateTime)<<32)|creation.dwLowDateTime;
    const auto session_path=root+L"bridge-session-"+std::to_wstring(pid)+L".bin";
    HANDLE file=CreateFileW(session_path.c_str(),GENERIC_WRITE,0,&attributes,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    DWORD bytes{};
    if (file==INVALID_HANDLE_VALUE || !WriteFile(file,&session,sizeof(session),&bytes,nullptr) || bytes!=sizeof(session)) return 10;
    CloseHandle(file); LocalFree(descriptor);
    // SetWindowsHookEx requires the hook procedure to belong to a normally
    // loaded DLL. DONT_RESOLVE_DLL_REFERENCES leaves this module unusable as
    // a cross-process hook image even though GetProcAddress can find exports.
    SetLastError(ERROR_SUCCESS);
    HMODULE module=LoadLibraryW(dll.c_str());
    if (!module) {
        const auto error=GetLastError();
        LogPid(root,pid,(std::string("bridge DLL normal load failed; win32=")+std::to_string(error)).c_str());
        CloseHandle(process); CloseHandle(stop); DeleteFileW(session_path.c_str()); return 11;
    }
    HOOKPROC hook{};
    FARPROC address=module ? GetProcAddress(module,"KekeBridgeHook") : nullptr;
    static_assert(sizeof(hook)==sizeof(address));
    std::memcpy(&hook,&address,sizeof(hook));
    if (!hook) {
        LogPid(root,pid,"bridge DLL does not export KekeBridgeHook");
        FreeLibrary(module); CloseHandle(process); CloseHandle(stop); DeleteFileW(session_path.c_str()); return 12;
    }
    SetLastError(ERROR_SUCCESS);
    HHOOK installed=SetWindowsHookExW(WH_GETMESSAGE,hook,module,session.window_thread);
    if (!installed) {
        const auto error=GetLastError();
        LogPid(root,pid,(std::string("Windows rejected hook loading; win32=")+std::to_string(error)).c_str());
        DeleteFileW(session_path.c_str()); return 11;
    }
    LogPid(root,pid,"Windows hook installed; loading alone does not submit decomposition");
    SetLastError(ERROR_SUCCESS);
    const BOOL window_posted=PostMessageW(window.handle,WM_NULL,0,0);
    const DWORD window_post_error=window_posted ? ERROR_SUCCESS : GetLastError();
    SetLastError(ERROR_SUCCESS);
    const BOOL thread_posted=PostThreadMessageW(session.window_thread,WM_NULL,0,0);
    const DWORD thread_post_error=thread_posted ? ERROR_SUCCESS : GetLastError();
    LogPid(root,pid,(std::string("initial hook wake window=")+(window_posted ? "posted" : "failed")+
        " win32="+std::to_string(window_post_error)+" thread="+(thread_posted ? "posted" : "failed")+
        " win32="+std::to_string(thread_post_error)).c_str());
    bool module_found=false,probe_error_logged=false,callback_log_found=false;
    ModuleProbe last_probe{};
    const auto callback_log=root+L"bridge-"+std::to_wstring(pid)+L".log";
    HANDLE probe_waits[]={process,stop};
    for (int attempt=0;attempt<20;++attempt) {
        if (GetFileAttributesW(callback_log.c_str())!=INVALID_FILE_ATTRIBUTES) {
            callback_log_found=true; break;
        }
        last_probe=ProbeBridgeModule(pid);
        if (!last_probe.checked && !probe_error_logged) {
            LogPid(root,pid,(std::string("target module snapshot unavailable; win32=")+std::to_string(last_probe.error)).c_str());
            probe_error_logged=true;
        }
        if (last_probe.found && !module_found) {
            module_found=true;
            LogPid(root,pid,"bridge DLL is mapped in game; waiting for its hook callback log");
        }
        if (WaitForMultipleObjects(2,probe_waits,FALSE,500)!=WAIT_TIMEOUT) break;
    }
    callback_log_found=callback_log_found || GetFileAttributesW(callback_log.c_str())!=INVALID_FILE_ATTRIBUTES;
    if (module_found && !callback_log_found)
        LogPid(root,pid,"bridge DLL mapped, but its hook callback did not create a startup log");
    else if (!module_found && !callback_log_found) {
        const auto outcome=std::string("bridge DLL not observed after 10 seconds; snapshot=")+
            (last_probe.checked ? "ok" : "failed")+" modules="+std::to_string(last_probe.count)+
            " snapshot_error="+std::to_string(last_probe.error)+" WM_NULL_window="+
            (window_posted ? "posted" : "failed")+" WM_NULL_thread="+
            (thread_posted ? "posted" : "failed")+
            "; SetWindowsHookEx returned a hook handle, but no target module or callback was observed; cause unknown; no decomposition was sent";
        LogPid(root,pid,outcome.c_str());
    }
    else if (callback_log_found)
        LogPid(root,pid,"bridge hook callback started; see bridge-PID.log for initialization details");
    HANDLE waits[]={process,stop}; WaitForMultipleObjects(2,waits,FALSE,INFINITE);
    UnhookWindowsHookEx(installed); FreeLibrary(module);
    CloseHandle(process); CloseHandle(stop); DeleteFileW(session_path.c_str());
    Log(root,"loader ended; pinned bridge unloads when game exits");
    return 0;
}
