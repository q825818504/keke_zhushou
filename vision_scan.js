/* One collection page: native components or local screenshots, with shared account context. */
window.KekeVision = (() => {
  const esc=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const methods={native:'DLL 原生读取',offline:'截图识别 / 文件夹导入',mouse:'鼠标全量扫描',new:'NEW 增量扫描',gamepad:'手柄全量扫描'};
  const stateTone=text=>{
    const value=String(text||'');
    if(/失败0(?:张|个)|未发现新增|本批次未保存/.test(value))return 'success';
    if(/失败|错误|无法|冲突|不完整|\berror\b|\bexception\b/i.test(value))return 'error';
    if(/正在|连接中|读取中|识别中|准备OCR|检测中/.test(value))return 'working';
    if(/尚未|未发现|未运行|未部署|缺少|请退出|请通过|需要/.test(value))return 'warning';
    if(/成功|已保存|已准备|匹配|通过|已发现|已移除|完成/.test(value))return 'success';
    return 'info';
  };
  const statusNotice=(text,tone=stateTone(text))=>`<span class="inventory-status" data-tone="${tone}" role="status" aria-live="polite" aria-atomic="true"><span class="inventory-status-icon" aria-hidden="true"></span>${esc(text)}</span>`;
  const updateNotice=(node,text)=>{node.dataset.tone=stateTone(text);node.innerHTML='<span class="inventory-status-icon" aria-hidden="true"></span>'+esc(text);};
  const stateBadge=(text,tone=stateTone(text))=>`<span class="inventory-state" data-tone="${tone}"><span aria-hidden="true"></span>${esc(text)}</span>`;
  const validUid=value=>/^\d{8,20}$/.test(value) && BigInt(value)<=18446744073709551615n;
  let status=null,nativeStatus=null,batch=null,account='默认账号',accountPinned=false,mode='native',timer=null,history=[],message='',busy=false,page=0;
  let directoryDraft=null,countDraft='',uidDraft=null,selectedFiles=[],selectedFileInputs={},requestedBatch=null;
  let componentFilesOpen=false;
  let riskAcknowledged=false,riskEnabled=false,riskNotice=null;
  const isRiskModeEnabled=()=>riskAcknowledged && riskEnabled;
  function syncRiskState(value){
    const previous=isRiskModeEnabled();
    riskAcknowledged=value?.acknowledged===true;riskEnabled=value?.enabled===true;
    if(previous!==isRiskModeEnabled())window.dispatchEvent(new Event('keke-native-risk-changed'));
  }
  function showRiskNotice(){
    if(riskAcknowledged || riskNotice)return;
    const dialog=document.createElement('dialog');riskNotice=dialog;
    dialog.className='inventory-risk-dialog';dialog.id='nativeRiskDialog';
    dialog.setAttribute('aria-labelledby','nativeRiskTitle');dialog.setAttribute('aria-describedby','nativeRiskDescription');
    dialog.innerHTML='<h2 id="nativeRiskTitle">DLL 读取风险提示</h2><p id="nativeRiskDescription">DLL 读取模式涉及读取游戏数据，存在一定风险。请自行判断是否使用，并承担使用风险。</p><p>风险模式默认关闭。点击“我已了解”后，你仍需主动勾选“启用风险模式”，才能部署组件或使用 DLL 读取。</p><p class="inventory-risk-error" role="status"></p><div class="inventory-actions"><button type="button" class="primary-button">我已了解</button></div>';
    dialog.addEventListener('cancel',event=>event.preventDefault());
    dialog.querySelector('button').onclick=async event=>{
      const button=event.currentTarget;button.disabled=true;
      try{
        if(!nativeStatus?.token)nativeStatus=await request('/inventory/status');
        syncRiskState(await request('/inventory/risk/acknowledge',{}));
        dialog.close();dialog.remove();riskNotice=null;paint();
      }catch(error){dialog.querySelector('[role="status"]').textContent=error.message;button.disabled=false;}
    };
    document.body.append(dialog);dialog.showModal();
  }
  const root=()=>document.querySelector('#userVisionRoute');
  async function request(path,body){
    if(body && ['/inventory/start','/inventory/components/deploy'].includes(path) && !isRiskModeEnabled())
      throw Error('请先在读取数据中启用风险模式，再使用 DLL 读取或部署组件。');
    const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Keke-Inventory':status?.token || nativeStatus?.token || ''},body:JSON.stringify(body)}:{cache:'no-store'});
    let data;try{data=await response.json();}catch{throw Error('当前桌面服务未连接，请使用新版Windows用户端');}
    if(!response.ok)throw Error(data.error || '读取服务不可用');return data;
  }
  const api=(path,body)=>request('/vision/'+path,body);
  async function refresh(){
    if(busy)return;busy=true;
    try{
      const equipmentWasRunning=!!nativeStatus?.equipment_job?.running;
      const nativeReadWasRunning=!!nativeStatus?.job?.running;
      const results=await Promise.allSettled([api('status'),request('/inventory/status')]);
      if(results[0].status==='fulfilled')status=results[0].value;
      if(results[1].status==='fulfilled'){nativeStatus=results[1].value;syncRiskState(nativeStatus.native_risk);}
      if(!status && !nativeStatus)throw Error('当前桌面读取服务未连接');
      if(nativeReadWasRunning && !nativeStatus?.job?.running){
        account=nativeStatus?.config?.account||account;accountPinned=true;batch=null;uidDraft=null;
      }
      if(nativeStatus?.equipment_job?.running){mode='native';account=nativeStatus.equipment_job.account;}
      else if(nativeStatus?.job.running){mode='native';account=nativeStatus.job.account || nativeStatus.config.account;}
      else if(status?.job.running){mode=status.batch?.mode || mode;account=status.job.account;batch=status.batch;}
      else if(!accountPinned && nativeStatus?.config.account)account=nativeStatus.config.account;
      if(requestedBatch){const id=requestedBatch;requestedBatch=null;batch=await api('batch?account='+encodeURIComponent(account)+'&id='+id);}
      else if(status?.batch && status.batch.account===account && (!batch || batch.id===status.batch.id))batch=status.batch;
      if(status)history=await api('history?account='+encodeURIComponent(account));
      const focused=document.activeElement,panel=root();
      const editing=!equipmentWasRunning && !nativeStatus?.equipment_job?.running && !status?.job.running && !nativeStatus?.job.running && panel?.contains(focused) && focused.matches('input,select,button');
      if(!editing)paint();
      clearTimeout(timer);if(status?.job.running || nativeStatus?.job.running || nativeStatus?.equipment_job?.running)timer=setTimeout(refresh,1000);
      if((equipmentWasRunning && !nativeStatus?.equipment_job?.running) || (nativeReadWasRunning && !nativeStatus?.job?.running))
        window.dispatchEvent(new CustomEvent('keke-inventory-synced',{detail:{account:nativeStatus?.config?.account||account}}));
    }catch(error){message=error.message;paint();}finally{busy=false;}
  }
  async function startNativeRead(value){
    if(!isRiskModeEnabled())throw Error('请先在读取数据中启用风险模式，再读取游戏数据。');
    if(!nativeStatus?.token)nativeStatus=await request('/inventory/status');
    if(nativeStatus?.job?.running || nativeStatus?.native_operation || nativeStatus?.equipment_job?.running)
      throw Error('当前已有读取或装备操作正在运行，请完成后再开始 DLL 读取。');
    account=String(value || nativeStatus?.config?.native_account || nativeStatus?.config?.account || account || '默认账号').trim();
    if(!account)throw Error('当前账号标签为空，请先设置本机账号标签。');
    accountPinned=true;mode='native';batch=null;message='';
    const token=nativeStatus.token;
    nativeStatus=await request('/inventory/start',{account});
    if(!nativeStatus.token)nativeStatus.token=token;
    paint();
    refresh();
    return nativeStatus;
  }
  function nativePane(){
    const running=!!nativeStatus?.job.running,c=nativeStatus?.components;
    return `<section class="inventory-connect"><div class="inventory-native-head"><h2>DLL 原生读取</h2><label class="inventory-risk-toggle"><input id="nativeRiskMode" type="checkbox" role="switch" ${isRiskModeEnabled()?'checked':''} ${running || nativeStatus?.native_operation || nativeStatus?.equipment_job?.running || !riskAcknowledged || !nativeStatus?'disabled':''}>启用风险模式</label></div><p>读取装备、角色养成、物品材料、当前队伍与环境，结果保存到背包数据。</p><p id="nativeRiskModeHint">${isRiskModeEnabled()?'风险模式已启用，仅本次程序运行有效。':'风险模式默认关闭。启用后才可部署组件或使用 DLL 读取。'}</p>
      <div class="inventory-actions"><button class="primary-button" data-native="start" ${running || !nativeStatus || !isRiskModeEnabled()?'disabled':''}>${running?'读取中…':'读取所有数据'}</button>${running?'<button class="ghost-button" data-native="cancel">取消读取</button>':''}${statusNotice(message || nativeStatus?.job.message || '正在连接桌面服务…')}</div>
      <div id="readComponents" class="inventory-component-setup"><h3>环境检测与组件部署</h3><p>首次使用：退出游戏 → 检测环境 → 部署组件 → 通过原游戏启动器启动并登录 → 读取数据。</p>
      <label>游戏程序目录（HTGame.exe所在文件夹）<input class="vision-storage-path" id="readGameDirectory" value="${esc(directoryDraft ?? c?.game_directory)}" placeholder="可从正在运行的游戏自动检测" ${running?'disabled':''}></label>
      <div class="inventory-actions"><button class="ghost-button" data-native="check" ${running || !nativeStatus?'disabled':''}>检测环境</button><button class="ghost-button" data-native="deploy" ${running || !nativeStatus || !isRiskModeEnabled()?'disabled':''}>一键部署组件</button><button class="ghost-button" data-native="remove" ${running || !nativeStatus?'disabled':''}>移除助手部署的组件</button></div>${statusNotice(c?.message || '检测后显示组件与游戏连接情况。',c?stateTone(c.message):'info')}
      ${c?.files?`<div class="inventory-state-list" aria-label="组件环境状态">${stateBadge('内置组件 · '+(c.bundle_ready?'校验通过':'不完整'),c.bundle_ready?'success':'error')}${stateBadge('游戏部署 · '+(c.deployment_ready?'文件匹配':'尚未完整匹配'),c.deployment_ready?'success':'warning')}${stateBadge('游戏进程 · '+(c.game_running?'运行中':'未运行'),c.game_running?'success':'info')}${stateBadge('原生端点 · '+(c.endpoint_present?'已发现':'未发现'),c.endpoint_present?'success':'warning')}${(c.runtime_libraries||[]).map(row=>stateBadge('VC++ · '+row.file+(row.present?' 已安装':' 缺少'),row.present?'success':'error')).join('')}</div><details id="componentFileAudit" class="inventory-metadata" ${componentFilesOpen?'open':''}><summary>组件文件核对明细</summary><ul class="inventory-component-files">${c.files.map(row=>`<li><span>${esc(row.file)}</span>${stateBadge(({current:'匹配',missing:'未部署',conflict:'不同文件，保留'}[row.state]||row.state),row.state==='current'?'success':row.state==='missing'?'warning':'warning')}</li>`).join('')}</ul></details>${c.issues?.length?statusNotice(c.issues.join('；')):''}`:''}
      <p>运行组件已内置。检测缺少 VC++ x64 运行库时，可安装 <a href="https://aka.ms/vc14/vc_redist.x64.exe" target="_blank" rel="noopener">Microsoft官方运行库</a> 后重新检测。</p></div></section>`;
  }
  function visionPane(){
    const running=!!status?.job.running,records=batch?.records || [],images=batch?.images || [];
    const manualUid=uidDraft ?? '';
    const pending=images.filter(x=>x.pending || x.error==='采集或识别未完成'),failures=images.filter(x=>x.error && !pending.includes(x));
    const pages=Math.max(1,Math.ceil(images.length/50));page=Math.min(page,pages-1);
    return `<section class="inventory-connect"><h2>${methods[mode]}</h2>
      ${mode!=='native'?`<label class="vision-account-uid">截图数据所属游戏 UID<input id="visionUid" inputmode="numeric" maxlength="20" value="${esc(manualUid)}" placeholder="手动输入 8–20 位数字" ${running?'disabled':''}></label><p>截图识别不会读取游戏账号身份；每次新建扫描都要手动确认 UID，批次会保存在该 UID 的账号资料下。</p>`:''}
      ${mode==='offline'?`<div class="inventory-actions"><label>截图 <input id="visionFiles" type="file" accept="image/*" multiple ${running?'disabled':''}></label><label>截图文件夹 <input id="visionFolder" type="file" accept="image/*" webkitdirectory multiple ${running?'disabled':''}></label></div><p id="readFileCount">已选择 ${selectedFiles.length} 张图片</p>`:`<div class="inventory-settings"><label>当前筛选列表的装备数量<input id="visionCount" type="number" min="1" max="2000" value="${esc(countDraft)}" placeholder="全量扫描需填写；NEW无需填写" ${running || mode==='new'?'disabled':''}></label></div><p>打开游戏装备背包。开始后请在3秒内切回游戏。F8停止采集，已截图继续识别；鼠标移到屏幕左上角也可停止鼠标采集。${mode==='gamepad'?'手柄方式需要本机已有虚拟手柄驱动。':''}</p>`}
      <p>每次扫描独立保存截图。识别结果自动进入背包数据，未显示的状态保持未知。</p>
      <div class="inventory-actions"><button class="primary-button" data-vision="start" ${running || !status?'disabled':''}>${running?'处理中…':'开始识别 / 扫描'}</button>${running?`${status.job.capture_running?`<button class="ghost-button" data-vision="stop-capture" ${status.job.capture_stopping?'disabled':''}>停止采集（F8）</button>`:''}<button class="ghost-button" data-vision="cancel">停止全部</button>`:''}${statusNotice(message || status?.job.message || '正在检查桌面服务…')}</div><p class="inventory-progress-label">已处理 ${status?.job.processed || 0} / ${status?.job.total || 0} 张</p>${running?`<progress class="inventory-progress" value="${status?.job.processed||0}" max="${Math.max(1,status?.job.total||1)}" aria-label="扫描处理进度"></progress>`:''}</section>
      <section class="inventory-browser"><div class="inventory-browser-head"><h2>扫描结果</h2><button class="ghost-button" data-vision="retry" ${running || !batch || !images.some(x=>x.error)?'disabled':''}>${pending.length?'继续识别 / 重试':'重试失败图片'}</button></div><div class="inventory-state-list inventory-result-states">${stateBadge('已识别 '+records.length+' 件',records.length?'success':'info')}${failures.length?stateBadge(failures.length+' 张识别失败','error'):stateBadge('没有识别失败','success')}${pending.length?stateBadge(pending.length+' 张待识别','warning'):''}</div>
      <div class="inventory-actions"><button class="ghost-button" data-vision="backpack" ${batch?'':'disabled'}>查看背包结果</button><button class="ghost-button" data-vision="export" ${batch?'':'disabled'}>导出识别批次</button></div>
      ${batch?`<p class="inventory-hint">${esc(batch.account)} · ${esc(batch.saved_at)} · ${stateBadge(batch.complete?'当前列表采集与识别完成':'部分观测；未识别内容保持未知',batch.complete?'success':'warning')}</p>${batch.storage?`<label class="inventory-hint">本批次截图文件夹<input class="vision-storage-path" aria-label="本批次截图文件夹" readonly value="${esc(batch.storage.images_directory)}"></label><button class="ghost-button" data-vision="open-folder" ${status?.job.capture_running?'disabled':''}>打开截图文件夹</button>`:''}${batch.capture_error?statusNotice('采集未完成：'+batch.capture_error+'。已保存图片可继续识别。','warning'):''}`:''}
      <details class="inventory-metadata"><summary>图片、原文与识别诊断（${images.length}张）</summary>${images.slice(page*50,(page+1)*50).map(image=>`<details class="inventory-record"><summary>${esc(image.file)} · ${stateBadge(image.pending?'等待处理':image.error || '已识别',image.pending?'warning':image.error?'error':'success')}${image.role?.role_name?' · 角色 '+esc(image.role.role_name):''}</summary><img class="vision-evidence" loading="lazy" alt="本机识别原图" src="/vision/image?account=${encodeURIComponent(batch.account)}&id=${batch.id}&name=${encodeURIComponent(image.file)}"><pre>${esc(JSON.stringify({role:image.role,state_candidate:image.state_candidate,lines:image.lines,error:image.error},null,2))}</pre></details>`).join('')}</details>
      <div class="inventory-pagination"><button class="ghost-button" data-vision="previous" ${page===0?'disabled':''}>上一页</button><span>${page+1} / ${pages} · 每页50张</span><button class="ghost-button" data-vision="next" ${page+1>=pages?'disabled':''}>下一页</button></div></section>
      <details class="inventory-browser"><summary>历史扫描与失败图片重试</summary><div class="inventory-actions"><button class="ghost-button" data-vision="history" ${running?'disabled':''}>查看此账号历史</button>${history.map(item=>`<button class="ghost-button" data-vision="load" data-id="${item.id}">${esc(item.saved_at)} · ${esc(methods[item.mode] || item.mode)}</button>`).join('') || '<p>暂无历史批次</p>'}</div></details>`;
  }
  function paint(){
    const panel=root();if(!panel)return;
    const running=!!status?.job.running || !!nativeStatus?.job.running;
    panel.innerHTML=`<div class="inventory-heading"><div><span class="inventory-eyebrow">采集与同步</span><h1>读取数据</h1><p>选择采集方式，读取结果保存到对应账号的背包数据。</p></div><button class="ghost-button" data-vision="backpack">查看背包数据</button></div>
      <section class="inventory-connect"><div class="inventory-settings"><label>采集方式<select id="visionMode" ${running?'disabled':''}>${Object.entries(methods).map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></label><label>本机账号标签<input id="visionAccount" maxlength="80" value="${esc(account)}" ${running?'disabled':''}></label></div><p>原生读取会自动识别已登录 UID；截图扫描需手动填写 UID。</p></section>
      ${mode==='native'?nativePane():visionPane()}`;
    const legacyAccountLabel=panel.querySelector('#visionAccount')?.closest('label');
    if(legacyAccountLabel){
      const profiles=nativeStatus?.account_profiles||[];
      const selected=profiles.find(profile=>profile.account===account);
      const picker=document.createElement('label');picker.className='vision-account-picker';picker.innerHTML=`账号资料<select id="visionAccountSelect" ${running?'disabled':''}>${profiles.map(profile=>`<option value="${esc(profile.account)}" ${profile.account===account?'selected':''}>${esc(profile.display_name)}</option>`).join('') || `<option value="${esc(account)}" disabled selected>尚无 UID 资料（原生读取后自动创建）</option>`}</select><small>${selected?.uid?'当前 UID 资料用于查看扫描历史。':'这是待绑定的旧资料，仅用于查看历史批次。'}</small>`;
      legacyAccountLabel.replaceWith(picker);
    }
    panel.querySelector('#visionMode').value=mode;
    panel.querySelector('#nativeRiskMode')?.setAttribute('aria-describedby','nativeRiskModeHint');
    panel.querySelector('#nativeRiskMode')?.addEventListener('change',async event=>{
      const input=event.currentTarget;input.disabled=true;
      try{syncRiskState(await request('/inventory/risk-mode',{enabled:input.checked}));message='';}
      catch(error){message=error.message;}
      paint();
    });
    panel.querySelector('#componentFileAudit')?.addEventListener('toggle',event=>{componentFilesOpen=event.currentTarget.open;});
    for(const notice of panel.querySelectorAll('.inventory-status[role="status"]'))notice.dataset.tone=notice.dataset.tone||'info';
    panel.querySelector('#visionMode').onchange=event=>{mode=event.target.value;message='';paint();refresh();};
    panel.querySelector('#visionAccountSelect').onchange=async event=>{
      const selected=event.target.value;
      try{await request('/inventory/account/select',{account:selected});account=selected;accountPinned=true;uidDraft=null;batch=null;window.dispatchEvent(new CustomEvent('keke-account-changed',{detail:{account:selected,source:'vision'}}));await refresh();}
      catch(error){message=error.message;paint();}
    };
    panel.querySelector('#visionUid')?.addEventListener('input',event=>{uidDraft=event.target.value;});
    if(panel.querySelector('#readGameDirectory'))panel.querySelector('#readGameDirectory').oninput=event=>{directoryDraft=event.target.value;};
    if(panel.querySelector('#visionCount'))panel.querySelector('#visionCount').oninput=event=>{countDraft=event.target.value;};
    for(const id of ['visionFiles','visionFolder'])if(panel.querySelector('#'+id))panel.querySelector('#'+id).onchange=event=>{selectedFileInputs[id]=Array.from(event.target.files);selectedFiles=Object.values(selectedFileInputs).flat().filter(file=>file.type.startsWith('image/'));panel.querySelector('#readFileCount').textContent='已选择 '+selectedFiles.length+' 张图片';};
    panel.onclick=async event=>{
      const nativeButton=event.target.closest('[data-native]');
      if(nativeButton){
        if(nativeButton.disabled)return;
        nativeButton.disabled=true;const action=nativeButton.dataset.native;
        try{
          if(['check','deploy','remove'].includes(action)){
            const result=await request('/inventory/components/'+action,{game_directory:panel.querySelector('#readGameDirectory').value});
            nativeStatus.components=result;message=result.message;paint();
          }else if(action==='start'){
            await startNativeRead(account);
          }else{
            nativeStatus=await request('/inventory/'+action,action==='cancel'?{}:{account:account.trim()});message='';paint();refresh();
          }
        }catch(error){message=error.message;paint();}
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
        if(action==='retry'){
          const profile=(nativeStatus?.account_profiles||[]).find(row=>row.account===account);
          payload.account_uid=batch?.account_uid || profile?.uid;
          if(!payload.account_uid)throw Error('旧扫描批次仍未绑定 UID，请先在背包数据中确认账号归属。');
        }else if(mode!=='native'){
          payload.account_uid=panel.querySelector('#visionUid')?.value.trim()||'';
          if(!validUid(payload.account_uid))throw Error('请手动输入有效游戏 UID：8–20 位数字，并处于游戏 UID 范围内。');
        }
        if(mode==='offline' && action==='start'){
          if(!selectedFiles.length)throw Error('请选择截图或截图文件夹');
          if(selectedFiles.reduce((sum,file)=>sum+file.size,0)>64*1024*1024)throw Error('每批最多64MB，请分批导入');
          payload.files=await Promise.all(selectedFiles.map(file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=reject;reader.onload=()=>resolve({data:String(reader.result).split(',')[1]});reader.readAsDataURL(file);})));
        }
        page=0;status={...await api('start',payload),token:status.token};batch=status.batch;account=batch?.account||status.job?.account||account;uidDraft=null;message='';paint();await refresh();
      }catch(error){message=error.message;const target=panel.querySelector('[role="status"]');if(target){updateNotice(target,message);}button.disabled=false;}
    };
  }
  window.addEventListener('keke-source-deleted',event=>{
    const removed=event.detail;if(removed.account!==account)return;
    if(removed.source==='ocr:'+batch?.id)batch=null;
    history=history.filter(item=>'ocr:'+item.id!==removed.source);
  });
  window.addEventListener('keke-account-changed',event=>{
    if(!event.detail?.account)return;
    account=event.detail.account;accountPinned=true;batch=null;uidDraft=null;page=0;
    if(!root()?.hidden)refresh();
  });
  window.addEventListener('keke-account-deleted',event=>{
    if(event.detail?.account!==account)return;
    account='默认账号';accountPinned=false;batch=null;history=[];requestedBatch=null;uidDraft=null;page=0;
    nativeStatus=null;status=null;
  });
  return {openAccount(value,options={}){account=value || '默认账号';accountPinned=true;mode=options.method || 'native';requestedBatch=options.batchId || null;batch=null;page=0;message='';selectedFiles=[];selectedFileInputs={};},
    startNativeRead,
    isRiskModeEnabled,syncRiskState,
    render(){paint();refresh().then(showRiskNotice);}};
})();
