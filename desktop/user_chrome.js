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
  const icons={
    team:'<circle cx="8" cy="7" r="3"/><path d="M2 20v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m1 4a5 5 0 0 1 5 5"/>',
    characters:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    'arc-drives':'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>',
    cassettes:'<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="8" cy="11" r="2"/><circle cx="16" cy="11" r="2"/><path d="m6 19 2-4h8l2 4"/>',
    'drive-blocks':'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
    inventory:'<path d="m3 7 9-4 9 4v10l-9 4-9-4V7Zm0 0 9 4 9-4M12 11v10"/>',
    vision:'<path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5M5 12h14"/>'
  };
  document.querySelectorAll('.desktop-sidebar [data-user-route]').forEach(button=>{
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    svg.innerHTML=icons[button.dataset.userRoute] || icons.inventory;button.prepend(svg);
  });
  async function releaseRequest(action){
    const {token}=await (await fetch('/inventory/status',{cache:'no-store'})).json();
    const response=await fetch('/release/'+action,{method:'POST',headers:{'X-Keke-Inventory':token,'Content-Type':'application/json'},body:'{}'});
    if(!response.ok)throw Error('更新记录操作未完成，请重试。');
  }
  async function showRelease(force=false){
    const response=await fetch('/release/status',{cache:'no-store'});if(!response.ok)return;
    const data=await response.json();if(!force && !data.show)return;
    let dialog=document.querySelector('#releaseNotesDialog');
    if(!dialog){
      dialog=document.createElement('dialog');dialog.id='releaseNotesDialog';
      dialog.innerHTML='<div class="release-heading"><img src="mint-avatar.png" alt="薄荷"><div><h2>本次更新内容</h2><p class="release-version"></p></div></div><label class="release-history-control" hidden>查看版本<select aria-label="查看更新版本"></select></label><div class="release-copy"></div><p role="status"></p><button type="button">开始使用</button>';
      document.body.append(dialog);
      dialog.querySelector('button').addEventListener('click',async()=>{
        const button=dialog.querySelector('button');button.disabled=true;
        try{if(dialog.dataset.automatic==='true')await releaseRequest('acknowledge');dialog.close();}
        catch(error){dialog.querySelector('[role=status]').textContent=error.message;}
        finally{button.disabled=false;}
      });
      dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.querySelector('button').click();});
    }
    dialog.dataset.automatic=String(!force);
    dialog.querySelector('h2').textContent=force?'历次更新内容':'本次更新内容';
    dialog.querySelector('button').textContent=force?'关闭':'开始使用';
    dialog.querySelector('[role=status]').textContent='';
    dialog.querySelector('.release-history-control').hidden=!force;
    const history=force && data.history?.length?data.history:[data];
    const selector=dialog.querySelector('select');selector.replaceChildren();
    for(const entry of history){const option=document.createElement('option');option.value=entry.version;option.textContent='v'+entry.version;selector.append(option);}
    selector.value=data.version;
    function render(entry){
      dialog.querySelector('.release-version').textContent=force?'v'+entry.version+' 更新说明':'已更新至 v'+data.version;
      const copy=dialog.querySelector('.release-copy');copy.replaceChildren();
      for(const line of entry.notes.split('\n')){
        if(!line.trim() || line.startsWith('# '))continue;
        const element=document.createElement(line.startsWith('## ')?'h3':'p');
        element.textContent=line.replace(/^## |^- /,'');copy.append(element);
      }
    }
    selector.onchange=()=>render(history.find(entry=>entry.version===selector.value) || data);
    render(data);
    if(!dialog.open)dialog.showModal();
  }
  document.querySelector('#releaseNotesButton')?.addEventListener('click',()=>showRelease(true).catch(()=>{}));
  // The application's routes are rendered by its DOMContentLoaded handler first.
  requestAnimationFrame(()=>{
    if(window.__desktopErrors.length===0 && document.querySelector('#userTeamRoute')?.textContent.trim()){
      releaseRequest('ready').then(()=>showRelease()).catch(error=>console.warn(error.message));
    }
  });
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
