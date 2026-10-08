/* One collection page: native components or local screenshots, with shared account context. */
window.KekeVision = (() => {
  const esc=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const methods={native:'DLL 原生读取',offline:'截图识别 / 文件夹导入',mouse:'鼠标全量扫描',new:'NEW 增量扫描',gamepad:'手柄全量扫描'};
  let status=null,nativeStatus=null,batch=null,account='默认账号',accountPinned=false,mode='native',timer=null,history=[],message='',busy=false,page=0;
  let directoryDraft=null,countDraft='',selectedFiles=[],selectedFileInputs={},requestedBatch=null;
  const root=()=>document.querySelector('#userVisionRoute');
  async function request(path,body){
    const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Keke-Inventory':status?.token || nativeStatus?.token || ''},body:JSON.stringify(body)}:{cache:'no-store'});
    let data;try{data=await response.json();}catch{throw Error('当前桌面服务未连接，请使用新版Windows用户端');}
    if(!response.ok)throw Error(data.error || '读取服务不可用');return data;
  }
  const api=(path,body)=>request('/vision/'+path,body);
  async function refresh(){
    if(busy)return;busy=true;
    try{
      const results=await Promise.allSettled([api('status'),request('/inventory/status')]);
      if(results[0].status==='fulfilled')status=results[0].value;
      if(results[1].status==='fulfilled')nativeStatus=results[1].value;
      if(!status && !nativeStatus)throw Error('当前桌面读取服务未连接');
      if(nativeStatus?.job.running){mode='native';account=nativeStatus.job.account || nativeStatus.config.account;}
      else if(status?.job.running){mode=status.batch?.mode || mode;account=status.job.account;batch=status.batch;}
      else if(!accountPinned && nativeStatus?.config.account)account=nativeStatus.config.account;
      if(requestedBatch){const id=requestedBatch;requestedBatch=null;batch=await api('batch?account='+encodeURIComponent(account)+'&id='+id);}
      else if(status?.batch && status.batch.account===account && (!batch || batch.id===status.batch.id))batch=status.batch;
      if(status)history=await api('history?account='+encodeURIComponent(account));
      const focused=document.activeElement,panel=root();
      const editing=!status?.job.running && !nativeStatus?.job.running && panel?.contains(focused) && focused.matches('input,select,button');
      if(!editing)paint();
      clearTimeout(timer);if(status?.job.running || nativeStatus?.job.running)timer=setTimeout(refresh,1000);
    }catch(error){message=error.message;paint();}finally{busy=false;}
  }
  function nativePane(){
    const running=!!nativeStatus?.job.running,c=nativeStatus?.components;
    return `<section class="inventory-connect"><h2>DLL 原生读取</h2><p>读取装备、角色养成、物品材料、当前队伍与环境，结果保存到背包数据。</p>
      <div class="inventory-actions"><button class="primary-button" data-native="start" ${running || !nativeStatus?'disabled':''}>${running?'读取中…':'读取所有数据'}</button>${running?'<button class="ghost-button" data-native="cancel">取消读取</button>':''}<span role="status">${esc(message || nativeStatus?.job.message || '正在连接桌面服务…')}</span></div>
      <div id="readComponents" class="inventory-component-setup"><h3>环境检测与组件部署</h3><p>首次使用：退出游戏 → 检测环境 → 部署组件 → 通过原游戏启动器启动并登录 → 读取数据。</p>
      <label>游戏程序目录（HTGame.exe所在文件夹）<input class="vision-storage-path" id="readGameDirectory" value="${esc(directoryDraft ?? c?.game_directory)}" placeholder="可从正在运行的游戏自动检测" ${running?'disabled':''}></label>
      <div class="inventory-actions"><button class="ghost-button" data-native="check" ${running || !nativeStatus?'disabled':''}>检测环境</button><button class="ghost-button" data-native="deploy" ${running || !nativeStatus?'disabled':''}>一键部署组件</button><button class="ghost-button" data-native="remove" ${running || !nativeStatus?'disabled':''}>移除助手部署的组件</button></div><p>${esc(c?.message || '检测后显示组件与游戏连接情况。')}</p>
      ${c?.files?`<p>内置组件：${c.bundle_ready?'校验通过':'不完整'} · 游戏部署：${c.deployment_ready?'文件匹配':'尚未完整匹配'} · 游戏进程：${c.game_running?'运行中':'未运行'} · 原生端点：${c.endpoint_present?'已发现':'未发现'}</p><details class="inventory-metadata"><summary>组件文件核对明细</summary><pre>${esc(c.files.map(row=>row.file+' · '+({current:'匹配',missing:'未部署',conflict:'不同文件，保留'}[row.state])).join('\n'))}</pre></details>${c.issues?.length?'<p>'+esc(c.issues.join('；'))+'</p>':''}`:''}
      <p>运行组件已内置。检测缺少 VC++ x64 运行库时，可安装 <a href="https://aka.ms/vc14/vc_redist.x64.exe" target="_blank" rel="noopener">Microsoft官方运行库</a> 后重新检测。</p></div></section>`;
  }
  function visionPane(){
    const running=!!status?.job.running,records=batch?.records || [],images=batch?.images || [];
    const pending=images.filter(x=>x.pending || x.error==='采集或识别未完成'),failures=images.filter(x=>x.error && !pending.includes(x));
    const pages=Math.max(1,Math.ceil(images.length/50));page=Math.min(page,pages-1);
    return `<section class="inventory-connect"><h2>${methods[mode]}</h2>
      ${mode==='offline'?`<div class="inventory-actions"><label>截图 <input id="visionFiles" type="file" accept="image/*" multiple ${running?'disabled':''}></label><label>截图文件夹 <input id="visionFolder" type="file" accept="image/*" webkitdirectory multiple ${running?'disabled':''}></label></div><p id="readFileCount">已选择 ${selectedFiles.length} 张图片</p>`:`<div class="inventory-settings"><label>当前筛选列表的装备数量<input id="visionCount" type="number" min="1" max="2000" value="${esc(countDraft)}" placeholder="全量扫描需填写；NEW无需填写" ${running || mode==='new'?'disabled':''}></label></div><p>打开游戏装备背包。开始后请在3秒内切回游戏。F8停止采集，已截图继续识别；鼠标移到屏幕左上角也可停止鼠标采集。${mode==='gamepad'?'手柄方式需要本机已有虚拟手柄驱动。':''}</p>`}
      <p>每次扫描独立保存截图。识别结果自动进入背包数据，未显示的状态保持未知。</p>
      <div class="inventory-actions"><button class="primary-button" data-vision="start" ${running || !status?'disabled':''}>${running?'处理中…':'开始识别 / 扫描'}</button>${running?`${status.job.capture_running?`<button class="ghost-button" data-vision="stop-capture" ${status.job.capture_stopping?'disabled':''}>停止采集（F8）</button>`:''}<button class="ghost-button" data-vision="cancel">停止全部</button>`:''}<span role="status">${esc(message || status?.job.message || '正在检查桌面服务…')}</span></div><p>${status?.job.processed || 0} / ${status?.job.total || 0} 张</p></section>
      <section class="inventory-browser"><div class="inventory-browser-head"><h2>已识别 ${records.length} 件 · ${failures.length} 张识别失败${pending.length?` · ${pending.length} 张待识别`:''}</h2><button class="ghost-button" data-vision="retry" ${running || !batch || !images.some(x=>x.error)?'disabled':''}>${pending.length?'继续识别 / 重试':'重试失败图片'}</button></div>
      <div class="inventory-actions"><button class="ghost-button" data-vision="backpack" ${batch?'':'disabled'}>查看背包结果</button><button class="ghost-button" data-vision="export" ${batch?'':'disabled'}>导出识别批次</button></div>
      ${batch?`<p class="inventory-hint">${esc(batch.account)} · ${esc(batch.saved_at)} · ${batch.complete?'当前列表采集与识别完成':'离线、增量或部分批次'}</p>${batch.storage?`<label class="inventory-hint">本批次截图文件夹<input class="vision-storage-path" aria-label="本批次截图文件夹" readonly value="${esc(batch.storage.images_directory)}"></label><button class="ghost-button" data-vision="open-folder" ${status?.job.capture_running?'disabled':''}>打开截图文件夹</button>`:''}${batch.capture_error?`<p>采集未完成：${esc(batch.capture_error)}。已保存图片可继续识别。</p>`:''}`:''}
      <details class="inventory-metadata"><summary>图片、原文与识别诊断（${images.length}张）</summary>${images.slice(page*50,(page+1)*50).map(image=>`<details class="inventory-record"><summary>${esc(image.file)} · ${esc(image.error || '已识别')}${image.role?.role_name?' · 角色 '+esc(image.role.role_name):''}</summary><img class="vision-evidence" loading="lazy" alt="本机识别原图" src="/vision/image?account=${encodeURIComponent(batch.account)}&id=${batch.id}&name=${encodeURIComponent(image.file)}"><pre>${esc(JSON.stringify({role:image.role,state_candidate:image.state_candidate,lines:image.lines,error:image.error},null,2))}</pre></details>`).join('')}</details>
      <div class="inventory-pagination"><button class="ghost-button" data-vision="previous" ${page===0?'disabled':''}>上一页</button><span>${page+1} / ${pages} · 每页50张</span><button class="ghost-button" data-vision="next" ${page+1>=pages?'disabled':''}>下一页</button></div></section>
      <details class="inventory-browser"><summary>历史扫描与失败图片重试</summary><div class="inventory-actions"><button class="ghost-button" data-vision="history" ${running?'disabled':''}>查看此账号历史</button>${history.map(item=>`<button class="ghost-button" data-vision="load" data-id="${item.id}">${esc(item.saved_at)} · ${esc(methods[item.mode] || item.mode)}</button>`).join('') || '<p>暂无历史批次</p>'}</div></details>`;
  }
  function paint(){
    const panel=root();if(!panel)return;
    const running=!!status?.job.running || !!nativeStatus?.job.running;
    panel.innerHTML=`<div class="inventory-heading"><div><span class="inventory-eyebrow">采集与同步</span><h1>读取数据</h1><p>选择采集方式，读取结果保存到对应账号的背包数据。</p></div><button class="ghost-button" data-vision="backpack">查看背包数据</button></div>
      <section class="inventory-connect"><div class="inventory-settings"><label>采集方式<select id="visionMode" ${running?'disabled':''}>${Object.entries(methods).map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></label><label>本机账号标签<input id="visionAccount" maxlength="80" value="${esc(account)}" ${running?'disabled':''}></label></div><p>切换游戏账号时请更换标签。</p></section>
      ${mode==='native'?nativePane():visionPane()}`;
    panel.querySelector('#visionMode').value=mode;
    panel.querySelector('#visionMode').onchange=event=>{mode=event.target.value;message='';paint();refresh();};
    panel.querySelector('#visionAccount').oninput=event=>{account=event.target.value;accountPinned=true;};
    if(panel.querySelector('#readGameDirectory'))panel.querySelector('#readGameDirectory').oninput=event=>{directoryDraft=event.target.value;};
    if(panel.querySelector('#visionCount'))panel.querySelector('#visionCount').oninput=event=>{countDraft=event.target.value;};
    for(const id of ['visionFiles','visionFolder'])if(panel.querySelector('#'+id))panel.querySelector('#'+id).onchange=event=>{selectedFileInputs[id]=Array.from(event.target.files);selectedFiles=Object.values(selectedFileInputs).flat().filter(file=>file.type.startsWith('image/'));panel.querySelector('#readFileCount').textContent='已选择 '+selectedFiles.length+' 张图片';};
    panel.onclick=async event=>{
      const nativeButton=event.target.closest('[data-native]');
      if(nativeButton){
        nativeButton.disabled=true;const action=nativeButton.dataset.native;
        try{
          if(['check','deploy','remove'].includes(action)){
            const result=await request('/inventory/components/'+action,{game_directory:panel.querySelector('#readGameDirectory').value});
            nativeStatus.components=result;message=result.message;paint();
          }else{
            nativeStatus=await request('/inventory/'+action,action==='cancel'?{}:{account:account.trim()});message='';paint();refresh();
          }
        }catch(error){message=error.message;const target=panel.querySelector('[role="status"]');if(target)target.textContent=message;nativeButton.disabled=false;}
        return;
      }
      const button=event.target.closest('[data-vision]');if(!button)return;
      const action=button.dataset.vision;
      try{
        if(action==='backpack'){window.KekeInventory.openAccount(account.trim(),mode!=='native' && batch && batch.account===account.trim()?'ocr:'+batch.id:'auto');showUserRoute('inventory');return;}
        if(action==='previous' || action==='next'){page+=action==='next'?1:-1;paint();return;}
        if(action==='export'){
          const url=URL.createObjectURL(new Blob([JSON.stringify(batch,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='可可助手视觉识别批次.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
        }
        if(action==='cancel' || action==='stop-capture'){await api(action,{});message='';paint();await refresh();return;}
        if(action==='open-folder'){await api('open-folder',{account:batch.account,id:batch.id});return;}
        account=account.trim();accountPinned=true;
        if(action==='history'){batch=null;page=0;message='';await refresh();paint();return;}
        if(action==='load'){page=0;batch=await api('batch?account='+encodeURIComponent(account)+'&id='+button.dataset.id);message='';paint();return;}
        button.disabled=true;message='正在准备图片…';
        const payload={mode:action==='retry'?'retry':mode,account,count:Number(countDraft),id:action==='retry'?batch.id:undefined};
        if(mode==='offline' && action==='start'){
          if(!selectedFiles.length)throw Error('请选择截图或截图文件夹');
          if(selectedFiles.reduce((sum,file)=>sum+file.size,0)>64*1024*1024)throw Error('每批最多64MB，请分批导入');
          payload.files=await Promise.all(selectedFiles.map(file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=reject;reader.onload=()=>resolve({data:String(reader.result).split(',')[1]});reader.readAsDataURL(file);})));
        }
        page=0;status={...await api('start',payload),token:status.token};batch=status.batch;message='';paint();await refresh();
      }catch(error){message=error.message;const target=panel.querySelector('[role="status"]');if(target)target.textContent=message;button.disabled=false;}
    };
  }
  window.addEventListener('keke-source-deleted',event=>{
    const removed=event.detail;if(removed.account!==account)return;
    if(removed.source==='ocr:'+batch?.id)batch=null;
    history=history.filter(item=>'ocr:'+item.id!==removed.source);
  });
  return {openAccount(value,options={}){account=value || '默认账号';accountPinned=true;mode=options.method || 'native';requestedBatch=options.batchId || null;batch=null;page=0;message='';selectedFiles=[];selectedFileInputs={};},render(){paint();refresh();}};
})();
