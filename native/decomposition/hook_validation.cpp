#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <tlhelp32.h>
#include <array>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <sddl.h>
#include <string>
#include <vector>

namespace {
struct WindowSearch { DWORD pid{}; HWND window{}; DWORD thread{}; };
HANDLE target_message_event{};
HANDLE target_retrieved_event{};
HANDLE local_ready_event{},local_hook_event{};
LRESULT CALLBACK LocalHook(int code,WPARAM wparam,LPARAM lparam) {
    if (code>=0 && lparam) {
        const auto* message=reinterpret_cast<const MSG*>(lparam);
        if (message->message==WM_NULL && local_hook_event) SetEvent(local_hook_event);
    }
    return CallNextHookEx(nullptr,code,wparam,lparam);
}
DWORD WINAPI LocalMessageThread(void*) {
    MSG message{}; PeekMessageW(&message,nullptr,0,0,PM_NOREMOVE);
    SetEvent(local_ready_event);
    while (GetMessageW(&message,nullptr,0,0)>0) {}
    return 0;
}
bool VerifyLocalHook() {
    local_ready_event=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    local_hook_event=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    if (!local_ready_event || !local_hook_event) return false;
    DWORD thread_id{}; HANDLE thread=CreateThread(nullptr,0,LocalMessageThread,nullptr,0,&thread_id);
    if (!thread || WaitForSingleObject(local_ready_event,3000)!=WAIT_OBJECT_0) return false;
    SetLastError(ERROR_SUCCESS);
    HHOOK hook=SetWindowsHookExW(WH_GETMESSAGE,LocalHook,nullptr,thread_id);
    const bool posted=hook && PostThreadMessageW(thread_id,WM_NULL,0,0);
    const bool called=posted && WaitForSingleObject(local_hook_event,3000)==WAIT_OBJECT_0;
    if (hook) UnhookWindowsHookEx(hook);
    PostThreadMessageW(thread_id,WM_QUIT,0,0); WaitForSingleObject(thread,3000);
    CloseHandle(thread); CloseHandle(local_ready_event); CloseHandle(local_hook_event);
    local_ready_event=local_hook_event=nullptr;
    return called;
}
void LogTargetMitigations(DWORD pid) {
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    if (!process) {
        wprintf(L"TARGET_POLICY open_failed=%lu\n",GetLastError());
        return;
    }
    DWORD signature{},dynamic_code{},image_load{},extension_points{};
    const bool signature_ok=GetProcessMitigationPolicy(process,ProcessSignaturePolicy,
        &signature,sizeof(signature))!=FALSE;
    const auto signature_error=signature_ok ? ERROR_SUCCESS : GetLastError();
    const bool dynamic_ok=GetProcessMitigationPolicy(process,ProcessDynamicCodePolicy,
        &dynamic_code,sizeof(dynamic_code))!=FALSE;
    const auto dynamic_error=dynamic_ok ? ERROR_SUCCESS : GetLastError();
    const bool image_ok=GetProcessMitigationPolicy(process,ProcessImageLoadPolicy,
        &image_load,sizeof(image_load))!=FALSE;
    const auto image_error=image_ok ? ERROR_SUCCESS : GetLastError();
    const bool extension_ok=GetProcessMitigationPolicy(process,ProcessExtensionPointDisablePolicy,
        &extension_points,sizeof(extension_points))!=FALSE;
    const auto extension_error=extension_ok ? ERROR_SUCCESS : GetLastError();
    wprintf(L"TARGET_POLICY signature_ok=%u signature=0x%08lx signature_error=%lu "
            L"dynamic_ok=%u dynamic=0x%08lx dynamic_error=%lu "
            L"image_ok=%u image=0x%08lx image_error=%lu "
            L"extension_ok=%u extension=0x%08lx extension_error=%lu\n",
            signature_ok?1U:0U,signature,signature_error,dynamic_ok?1U:0U,dynamic_code,dynamic_error,
            image_ok?1U:0U,image_load,image_error,extension_ok?1U:0U,extension_points,extension_error);
    CloseHandle(process);
}
std::wstring DesktopName(DWORD thread_id) {
    HDESK desktop=GetThreadDesktop(thread_id);
    if (!desktop) return L"<unavailable>";
    DWORD bytes{};
    GetUserObjectInformationW(desktop,UOI_NAME,nullptr,0,&bytes);
    if (!bytes) return L"<unavailable>";
    std::vector<wchar_t> name(bytes/sizeof(wchar_t)+1);
    if (!GetUserObjectInformationW(desktop,UOI_NAME,name.data(),bytes,&bytes)) return L"<unavailable>";
    return name.data();
}
DWORD IntegrityRid(HANDLE process) {
    HANDLE token{};
    if (!OpenProcessToken(process,TOKEN_QUERY,&token)) return 0;
    DWORD bytes{};
    GetTokenInformation(token,TokenIntegrityLevel,nullptr,0,&bytes);
    std::vector<std::byte> buffer(bytes);
    DWORD rid{};
    if (bytes && GetTokenInformation(token,TokenIntegrityLevel,buffer.data(),bytes,&bytes)) {
        auto* label=reinterpret_cast<TOKEN_MANDATORY_LABEL*>(buffer.data());
        PSID sid=label->Label.Sid;
        PUCHAR count=sid ? GetSidSubAuthorityCount(sid) : nullptr;
        if (count && *count) rid=*GetSidSubAuthority(sid,*count-1);
    }
    CloseHandle(token);
    return rid;
}
void LogTargetContext(DWORD pid,DWORD tid) {
    DWORD current_session{},target_session{};
    ProcessIdToSessionId(GetCurrentProcessId(),&current_session);
    ProcessIdToSessionId(pid,&target_session);
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    const DWORD target_integrity=process ? IntegrityRid(process) : 0;
    wprintf(L"TARGET_CONTEXT current_session=%lu target_session=%lu current_integrity=0x%lx "
            L"target_integrity=0x%lx current_desktop=%ls target_desktop=%ls\n",
            current_session,target_session,IntegrityRid(GetCurrentProcess()),target_integrity,
            DesktopName(GetCurrentThreadId()).c_str(),DesktopName(tid).c_str());
    if (process) CloseHandle(process);
}
LRESULT CALLBACK ProbeWindowProc(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    if (message==WM_NULL && target_message_event) SetEvent(target_message_event);
    return DefWindowProcW(window,message,wparam,lparam);
}
BOOL CALLBACK FindTargetWindow(HWND window,LPARAM parameter) {
    auto& search=*reinterpret_cast<WindowSearch*>(parameter);
    DWORD pid{}; const DWORD thread=GetWindowThreadProcessId(window,&pid);
    if (pid==search.pid) { search.window=window; search.thread=thread; return FALSE; }
    return TRUE;
}
struct ModuleProbe { bool checked{}; bool found{}; DWORD error{}; DWORD count{}; };
ModuleProbe ProbeBridgeModule(DWORD pid) {
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);
    if (snapshot==INVALID_HANDLE_VALUE) return {false,false,GetLastError(),0};
    MODULEENTRY32W entry{}; entry.dwSize=sizeof(entry);
    if (!Module32FirstW(snapshot,&entry)) {
        const auto error=GetLastError(); CloseHandle(snapshot); return {false,false,error,0};
    }
    DWORD count=0;
    do {
        ++count;
        if (_wcsicmp(entry.szModule,L"KekeDecompositionBridge.dll")==0) {
            CloseHandle(snapshot); return {true,true,ERROR_SUCCESS,count};
        }
        entry.dwSize=sizeof(entry);
    } while (Module32NextW(snapshot,&entry));
    const auto error=GetLastError();
    CloseHandle(snapshot);
    return {true,false,error==ERROR_NO_MORE_FILES ? ERROR_SUCCESS : error,count};
}
int RunTarget(const wchar_t* event_name) {
    const auto message_event_name=L"Local\\KekeBridgeHookProbeMessage-"+
        std::to_wstring(GetCurrentProcessId());
    target_message_event=CreateEventW(nullptr,TRUE,FALSE,message_event_name.c_str());
    if (!target_message_event) return 17;
    const auto retrieved_event_name=L"Local\\KekeBridgeHookProbeRetrieved-"+
        std::to_wstring(GetCurrentProcessId());
    target_retrieved_event=CreateEventW(nullptr,TRUE,FALSE,retrieved_event_name.c_str());
    if (!target_retrieved_event) { CloseHandle(target_message_event); return 21; }
    const wchar_t class_name[]=L"KekeBridgeHookProbeWindow";
    WNDCLASSW window_class{}; window_class.lpfnWndProc=ProbeWindowProc;
    window_class.hInstance=GetModuleHandleW(nullptr); window_class.lpszClassName=class_name;
    if (!RegisterClassW(&window_class)) {
        CloseHandle(target_retrieved_event); CloseHandle(target_message_event); return 19;
    }
    const HWND window=CreateWindowExW(0,class_name,L"Keke bridge hook validation",
        WS_OVERLAPPEDWINDOW,0,0,64,64,nullptr,nullptr,window_class.hInstance,nullptr);
    if (!window) { CloseHandle(target_retrieved_event); CloseHandle(target_message_event); return 18; }
    MSG message{};
    HANDLE ready=OpenEventW(EVENT_MODIFY_STATE,FALSE,event_name);
    if (!ready) {
        CloseHandle(target_retrieved_event); CloseHandle(target_message_event); return 20;
    }
    SetEvent(ready); CloseHandle(ready);
    while (GetMessageW(&message,nullptr,0,0)>0) {
        if (message.message==WM_NULL && target_retrieved_event) SetEvent(target_retrieved_event);
        TranslateMessage(&message); DispatchMessageW(&message);
    }
    CloseHandle(target_retrieved_event); target_retrieved_event=nullptr;
    CloseHandle(target_message_event); target_message_event=nullptr;
    return 0;
}
int RunController(const wchar_t* dll_path) {
    const bool local_hook=VerifyLocalHook();
    wprintf(L"LOCAL_HOOK callback=%u\n",local_hook?1U:0U);
    const auto ready_name=L"Local\\KekeBridgeHookProbeReady-"+
        std::to_wstring(GetCurrentProcessId());
    HANDLE ready=CreateEventW(nullptr,TRUE,FALSE,ready_name.c_str());
    if (!ready) { wprintf(L"FAIL create-ready-event win32=%lu\n",GetLastError()); return 2; }

    std::array<wchar_t,32768> executable{};
    const DWORD executable_size=GetModuleFileNameW(nullptr,executable.data(),static_cast<DWORD>(executable.size()));
    if (!executable_size || executable_size>=executable.size()) {
        wprintf(L"FAIL resolve-probe-executable win32=%lu\n",GetLastError()); CloseHandle(ready); return 3;
    }
    std::wstring command=L"\""+std::wstring(executable.data())+L"\" --target \""+ready_name+L"\"";
    std::vector<wchar_t> command_line(command.begin(),command.end()); command_line.push_back(L'\0');
    STARTUPINFOW startup{}; startup.cb=sizeof(startup);
    PROCESS_INFORMATION target{};
    if (!CreateProcessW(nullptr,command_line.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,
                        nullptr,nullptr,&startup,&target)) {
        wprintf(L"FAIL create-probe-target win32=%lu\n",GetLastError()); CloseHandle(ready); return 4;
    }
    CloseHandle(target.hThread);
    const DWORD ready_result=WaitForSingleObject(ready,5000);
    CloseHandle(ready);
    if (ready_result!=WAIT_OBJECT_0) {
        wprintf(L"FAIL target-message-queue-ready result=%lu\n",ready_result);
        TerminateProcess(target.hProcess,1); CloseHandle(target.hProcess); return 5;
    }
    LogTargetMitigations(target.dwProcessId);
    LogTargetContext(target.dwProcessId,target.dwThreadId);
    const auto message_event_name=L"Local\\KekeBridgeHookProbeMessage-"+
        std::to_wstring(target.dwProcessId);
    HANDLE message_event=OpenEventW(SYNCHRONIZE,FALSE,message_event_name.c_str());
    const auto retrieved_event_name=L"Local\\KekeBridgeHookProbeRetrieved-"+
        std::to_wstring(target.dwProcessId);
    HANDLE retrieved_event=OpenEventW(SYNCHRONIZE,FALSE,retrieved_event_name.c_str());

    std::wstring bridge_directory(dll_path);
    const auto separator=bridge_directory.find_last_of(L"\\/");
    if (separator!=std::wstring::npos) bridge_directory.resize(separator+1);
    const auto callback_log=bridge_directory+L"bridge-"+std::to_wstring(target.dwProcessId)+L".log";
    DeleteFileW(callback_log.c_str());
    SetLastError(ERROR_SUCCESS);
    HMODULE module=LoadLibraryW(dll_path);
    if (!module) {
        wprintf(L"FAIL load-bridge-in-controller win32=%lu\n",GetLastError());
        if (message_event) CloseHandle(message_event);
        if (retrieved_event) CloseHandle(retrieved_event);
        PostThreadMessageW(target.dwThreadId,WM_QUIT,0,0);
        WaitForSingleObject(target.hProcess,5000); CloseHandle(target.hProcess); return 6;
    }
    FARPROC address=GetProcAddress(module,"KekeBridgeHook");
    HOOKPROC hook{}; static_assert(sizeof(hook)==sizeof(address));
    std::memcpy(&hook,&address,sizeof(hook));
    if (!hook) {
        wprintf(L"FAIL bridge-export-missing\n"); FreeLibrary(module);
        if (message_event) CloseHandle(message_event);
        if (retrieved_event) CloseHandle(retrieved_event);
        PostThreadMessageW(target.dwThreadId,WM_QUIT,0,0);
        WaitForSingleObject(target.hProcess,5000); CloseHandle(target.hProcess); return 7;
    }
    WindowSearch target_window{target.dwProcessId};
    for (int i=0;i<50 && !target_window.window;++i) {
        EnumWindows(FindTargetWindow,reinterpret_cast<LPARAM>(&target_window));
        if (!target_window.window) Sleep(100);
    }
    if (!target_window.window || target_window.thread!=target.dwThreadId) {
        wprintf(L"FAIL target-window-not-found pid=%lu tid=%lu\n",target.dwProcessId,target.dwThreadId);
        if (message_event) CloseHandle(message_event);
        if (retrieved_event) CloseHandle(retrieved_event);
        FreeLibrary(module); PostThreadMessageW(target.dwThreadId,WM_QUIT,0,0);
        WaitForSingleObject(target.hProcess,5000); CloseHandle(target.hProcess); return 8;
    }
    SetLastError(ERROR_SUCCESS);
    HHOOK installed=SetWindowsHookExW(WH_GETMESSAGE,hook,module,target_window.thread);
    if (!installed) {
        wprintf(L"FAIL set-hook win32=%lu\n",GetLastError()); FreeLibrary(module);
        if (message_event) CloseHandle(message_event);
        if (retrieved_event) CloseHandle(retrieved_event);
        PostThreadMessageW(target.dwThreadId,WM_QUIT,0,0);
        WaitForSingleObject(target.hProcess,5000); CloseHandle(target.hProcess); return 8;
    }
    const BOOL posted=PostMessageW(target_window.window,WM_NULL,0,0);
    const bool retrieved=retrieved_event && WaitForSingleObject(retrieved_event,5000)==WAIT_OBJECT_0;
    const bool received=message_event && WaitForSingleObject(message_event,5000)==WAIT_OBJECT_0;
    ModuleProbe module_probe{}; bool callback=false;
    for (int i=0;i<50;++i) {
        module_probe=ProbeBridgeModule(target.dwProcessId);
        callback=GetFileAttributesW(callback_log.c_str())!=INVALID_FILE_ATTRIBUTES;
        if ((module_probe.checked && module_probe.found) || callback) break;
        if (WaitForSingleObject(target.hProcess,100)!=WAIT_TIMEOUT) break;
    }
    if (callback) {
        wprintf(L"CALLBACK_LOG=%ls\n",callback_log.c_str());
        HANDLE file=CreateFileW(callback_log.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,
                                nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if (file!=INVALID_HANDLE_VALUE) {
            std::array<char,1024> text{}; DWORD bytes{};
            if (ReadFile(file,text.data(),static_cast<DWORD>(text.size()-1),&bytes,nullptr))
                wprintf(L"CALLBACK_TEXT=%S\n",text.data());
            CloseHandle(file);
        }
    }
    wprintf(L"MODULE_SNAPSHOT checked=%u found=%u count=%lu error=%lu\n",
            module_probe.checked?1U:0U,module_probe.found?1U:0U,module_probe.count,module_probe.error);
    wprintf(L"RESULT mapped=%u callback=%u post=%u retrieved=%u received=%u target_pid=%lu target_thread=%lu\n",
            module_probe.found?1U:0U,callback?1U:0U,posted?1U:0U,retrieved?1U:0U,received?1U:0U,
            target.dwProcessId,target_window.thread);
    if (message_event) CloseHandle(message_event);
    if (retrieved_event) CloseHandle(retrieved_event);
    UnhookWindowsHookEx(installed); FreeLibrary(module);
    PostThreadMessageW(target.dwThreadId,WM_QUIT,0,0);
    const DWORD exited=WaitForSingleObject(target.hProcess,5000);
    if (exited!=WAIT_OBJECT_0) TerminateProcess(target.hProcess,1);
    CloseHandle(target.hProcess);
    return module_probe.checked && module_probe.found && callback && posted ? 0 : 9;
}
}

int wmain(int argc,wchar_t** argv) {
    if (argc==3 && wcscmp(argv[1],L"--target")==0) return RunTarget(argv[2]);
    if (argc==3 && wcscmp(argv[1],L"--controller")==0) return RunController(argv[2]);
    wprintf(L"usage: hook-validation.exe --controller BRIDGE_DLL\n");
    return 1;
}
