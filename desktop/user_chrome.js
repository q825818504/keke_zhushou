window.__desktopErrors = [];
window.addEventListener('error', event => window.__desktopErrors.push(event.message));
window.addEventListener('unhandledrejection', event => window.__desktopErrors.push(String(event.reason)));
async function diagnosticsRequest(action,body={}) {
  const {token}=await (await fetch('/inventory/status',{cache:'no-store'})).json();
  const response=await fetch('/diagnostics/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Keke-Inventory':token},body:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error);return data;
}
for (const name of ['error','unhandledrejection']) window.addEventListener(name,event=>{
  diagnosticsRequest('client-error',{message:String(event.message || event.reason)}).catch(()=>{});
});
window.addEventListener('DOMContentLoaded', () => {
  document.querySelector('#diagnosticsButton')?.addEventListener('click',async()=>{
    let dialog=document.querySelector('#diagnosticsDialog');
    if(!dialog){
      dialog=document.createElement('dialog');dialog.id='diagnosticsDialog';
      dialog.innerHTML='<h2>诊断日志</h2><p>查看近期功能错误和 Windows 确认的助手、采集组件、游戏崩溃。导出包不含背包数据和截图。</p><div class="diagnostics-actions"><button data-action="refresh">刷新记录</button><button data-action="export">导出诊断包</button><button data-action="close">关闭</button></div><p role="status"></p><pre></pre>';
      document.body.append(dialog);
      dialog.addEventListener('click',async event=>{
        const action=event.target.dataset.action;if(!action)return;
        if(action==='close'){dialog.close();return;}
        event.target.disabled=true;
        try{
          const data=await diagnosticsRequest(action);
          if(action==='export')dialog.querySelector('[role=status]').textContent='已导出：'+data.file;
          else display(data);
        }catch(error){dialog.querySelector('[role=status]').textContent=error.message;}
        finally{event.target.disabled=false;}
      });
    }
    function display(data){
      dialog.querySelector('pre').textContent='系统崩溃记录\n'+(data.crashes.map(row=>`${row.time} · ${row.application} · ${row.module} · ${row.code}`).join('\n') || '近期未发现系统确认的崩溃')+'\n\n功能日志\n'+data.logs;
      dialog.querySelector('[role=status]').textContent=data.hint;
    }
    dialog.showModal();
    try{display(await (await fetch('/diagnostics/recent',{cache:'no-store'})).json());}
    catch(error){dialog.querySelector('[role=status]').textContent=error.message;}
  });
  let currentVersion = null, busy = false;
  const check = async () => {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch('/local-data-version', { cache: 'no-store' });
      if (!response.ok) return;
      const { version } = await response.json();
      if (currentVersion && currentVersion !== version) {
        sessionStorage.setItem('keke-desktop-view', JSON.stringify({ route: userActiveRoute, character: selectedCharacter, tab: userActiveTab }));
        location.reload();
      }
      currentVersion = version;
    } catch { /* Keep the current display when local data is temporarily unavailable. */ }
    finally { busy = false; }
  };
  try {
    const view = JSON.parse(sessionStorage.getItem('keke-desktop-view') || 'null');
    sessionStorage.removeItem('keke-desktop-view');
    if (view) {
      if (characterData[view.character]) applyCharacter(view.character);
      userActiveTab = view.tab || 'overview';
      showUserRoute(view.route || 'team');
    }
  } catch { /* A malformed view state does not change user settings. */ }
  check();
  setInterval(check, 2500);
  window.addEventListener('focus', check);
});
document.addEventListener('keydown', event => {
  if (!event.ctrlKey || !/^[1-7]$/.test(event.key) || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  event.preventDefault();
  showUserRoute(['team','characters','arc-drives','cassettes','drive-blocks','inventory','vision'][Number(event.key)-1]);
});
