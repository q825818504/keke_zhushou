/* Independent desktop inventory board. Original snapshot fields are retained on disk. */
window.KekeInventory = (() => {
  const labels = {equipment:'装备库存',characters:'角色养成',items:'全部物品与材料',team:'当前队伍',environment:'当前环境'};
  const modeLabels={mouse:'鼠标全量',gamepad:'手柄全量',new:'NEW增量',offline:'截图导入'};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const validUid=value=>/^\d{8,20}$/.test(value) && BigInt(value)<=18446744073709551615n;
  const stateTone=text=>/失败|错误|无法|冲突|\berror\b|\bexception\b/i.test(String(text||''))?'error':/读取中|处理中|连接中/.test(String(text||''))?'working':/尚未|未发现|缺少|部分/.test(String(text||''))?'warning':/已保存|成功|匹配|完整/.test(String(text||''))?'success':'info';
  let deletePending = null;
  const updateNotice=(node,text)=>{node.dataset.tone=stateTone(text);node.innerHTML='<span class="inventory-status-icon" aria-hidden="true"></span>'+escape(text);};
  let selectedSource = 'auto', pendingAccount = null, noteDraft = null, uidDraft = null, ocrBatch = null;
  let viewedAccount = '', status = null, snapshot = {domains:{}}, active = 'equipment', equipmentFilter = '', page = 0, query = '', busy = false, timer = null, message = '';
  const panel = () => document.querySelector('#userInventoryRoute');
  async function request(path, body) {
    const options = {cache:'no-store'};
    if (body) Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-Keke-Inventory':status?.token || ''},body:JSON.stringify(body)});
    const response = await fetch(path,options);
    if (!response.ok) {
      let result = {}; try { result = await response.json(); } catch {}
      throw Error(result.error || '当前入口没有游戏同步服务，请使用新版Windows用户端');
    }
    return response.json();
  }
  async function refresh(account) {
    if (busy) { if (account) pendingAccount=account; return; }
    busy = true;
    try {
      const wasRunning = status?.job?.running;
      const next = await request('/inventory/status');
      status = next;
      const candidateAccount = account || (status.job.running ? status.config.account : viewedAccount) || status.config.account;
      const profiles = status.account_profiles || [];
      viewedAccount = profiles.some(profile => profile.account === candidateAccount)
        ? candidateAccount
        : status.config.native_account || profiles[0]?.account || candidateAccount;
      snapshot = await request('/inventory/snapshot?account=' + encodeURIComponent(viewedAccount) + '&source=' + encodeURIComponent(selectedSource));
      ocrBatch=snapshot.selected_source?.startsWith('ocr:') ? await request('/vision/batch?account='+encodeURIComponent(viewedAccount)+'&id='+snapshot.selected_source.slice(4)) : null;
      message = '';
      const focused=document.activeElement, root=panel();
      // Background initial refresh must not replace a field or button between typing and clicking.
      const editing=!account && !wasRunning && !status.job.running && root?.contains(focused) && focused.matches('input,select,textarea,button');
      if (!editing) paint();
      if (status.job.running || status.vision_job?.running) {
        clearTimeout(timer); timer = setTimeout(() => refresh(),1000);
      } else if (wasRunning) window.dispatchEvent(new Event('keke-inventory-synced'));
    } catch(error) { message = error.message; paint(); }
    finally { busy = false; if (pendingAccount) { const requested=pendingAccount; pendingAccount=null; refresh(requested); } }
  }
  window.addEventListener('keke-inventory-synced',event=>{
    if(event.detail?.account){viewedAccount=event.detail.account;noteDraft=null;uidDraft=null;selectedSource='auto';}
  });
  window.addEventListener('keke-account-changed',event=>{
    if(event.detail?.account){viewedAccount=event.detail.account;selectedSource='auto';deletePending=null;}
  });
  function paint() {
    const root = panel(); if (!root) return;
    // Do not disturb a settings edit while an inactive job is being inspected.
    const account = viewedAccount || status?.config?.account || '默认账号';
    const running = !!status?.job?.running;
    const profiles = status?.account_profiles || [];
    const selectedProfile = profiles.find(profile => profile.account === account);
    const profileOptions = profiles.map(profile => `<option value="${escape(profile.account)}" ${profile.account === account ? 'selected' : ''}>${escape(profile.display_name)}</option>`).join('');
    const equipment = snapshot.inventory?.equipment;
    const equipmentRows = equipment?.records || [];
    const characters = snapshot.inventory?.characters;
    const characterRows = characters?.records || [];
    const summaries = [
      {label:equipment && equipment.coverage.collection_complete!==true?'已识别装备':'背包总数',kind:'equipment',filter:'',count:equipmentRows.length},
      {label:'驱动块数量',kind:'equipment',filter:'drive',count:equipmentRows.filter(row=>row.category==='drive').length},
      {label:'卡带数量',kind:'equipment',filter:'tape',count:equipmentRows.filter(row=>row.category==='tape').length},
      {label:'已装备数量',kind:'equipment',filter:'equipped',count:equipmentRows.some(row=>typeof row.is_equipped!=='boolean')?'—':equipmentRows.filter(row=>row.is_equipped===true).length},
      {label:'角色数量',kind:'characters',filter:'',count:characterRows.length}
    ];
    const detailTitle = active==='equipment' ? summaries.find(item=>item.filter===equipmentFilter && item.kind==='equipment').label.replace('数量','').replace('总数','明细') : labels[active];
    const domain = snapshot.inventory?.[active];
    const filtered = (active==='characters' ? characterRows : domain?.records || []).filter(row => active!=='equipment' || !equipmentFilter || (equipmentFilter==='equipped' ? row.is_equipped===true : row.category===equipmentFilter)).filter(row => !query || JSON.stringify(row).toLowerCase().includes(query.toLowerCase()));
    const pages = Math.max(1, Math.ceil(filtered.length / 50)); page = Math.min(page,pages-1);
    root.innerHTML = `<div class="inventory-heading"><div><h1>背包数据</h1><p>查看背包总量、驱动块、卡带、装备占用和已同步角色。</p></div><button class="ghost-button" data-inventory="export" ${Object.keys(snapshot.inventory || {}).length ? '' : 'disabled'}>导出账号数据</button></div>
      <section class="inventory-connect"><h2>已保存的背包</h2>
      <div class="inventory-settings inventory-source-controls"><label>已保存的数据<select id="inventorySource">${[{id:'auto',label:'自动选择 · 优先原生库存'},...(snapshot.sources || [])].map(source=>`<option value="${escape(source.id)}">${escape(source.id.startsWith('ocr:')?'OCR · '+(modeLabels[source.mode] || source.label.replace('OCR · ','')):source.label)}${source.saved_at?' · '+escape(new Date(source.saved_at).toLocaleString()):''}${source.id!=='auto'?(source.complete?' · 列表完整':' · 部分观测'):''}</option>`).join('')}</select></label><button class="ghost-button" data-inventory="delete" ${!snapshot.sources?.some(item=>item.id===snapshot.selected_source) || running || status?.vision_job?.running ? 'disabled' : ''}>${deletePending===snapshot.selected_source?'确认删除（含该来源保存文件）':'删除选中数据'}</button></div>
      <div class="inventory-account-controls"><label class="inventory-account-picker-label">账号资料<select id="inventoryAccountSelect" ${running || status?.vision_job?.running ? 'disabled' : ''}>${profileOptions || '<option value="" disabled selected>尚无已保存 UID 资料；请先读取游戏数据或导入截图</option>'}</select></label>
      <div class="inventory-account-edit"><div class="inventory-account-field"><label for="inventoryAccountNote">备注</label><div class="inventory-account-input-action"><input id="inventoryAccountNote" maxlength="80" value="${escape(noteDraft ?? selectedProfile?.note ?? '')}" ${!selectedProfile || running || status?.vision_job?.running ? 'disabled' : ''}><button class="ghost-button" type="button" data-account-action="save-note" ${!selectedProfile || running || status?.vision_job?.running ? 'disabled' : ''}>保存备注</button></div></div>
      <div class="inventory-account-field"><label for="inventoryAccountUID">${selectedProfile?.uid ? 'UID' : '绑定 UID'}</label><div class="inventory-account-input-action"><input id="inventoryAccountUID" inputmode="numeric" maxlength="20" value="${escape(uidDraft ?? selectedProfile?.uid ?? selectedProfile?.former_uid ?? '')}" placeholder="8–20位数字" ${!selectedProfile || selectedProfile.uid || running || status?.vision_job?.running ? 'disabled' : ''}><button class="ghost-button" type="button" data-account-action="${selectedProfile?.uid ? 'delete-account' : 'bind'}" ${!selectedProfile || running || status?.vision_job?.running ? 'disabled' : ''}>${selectedProfile?.uid ? '删除 UID 及数据' : '确认绑定 UID'}</button></div></div></div>
      <small class="inventory-account-help">${selectedProfile?.uid ? '删除 UID 会同时删除该账号的原生快照、OCR 批次和截图、保存的配装方案，无法撤销。' : selectedProfile?.former_uid ? `此旧资料曾绑定 UID ${escape(selectedProfile.former_uid)}；不允许改绑至其他 UID。` : selectedProfile ? '这是升级前保存的旧数据。核对归属后输入 UID，完成绑定前不会用于配装。' : '原生读取会自动识别 UID；截图导入需先手动输入 UID。'}</small></div>
      <div class="inventory-actions"><button class="ghost-button" data-inventory="load" ${!status?'disabled':''}>查看此账号</button><button class="primary-button" data-inventory="read">读取新数据</button>${ocrBatch?'<button class="ghost-button" data-inventory="diagnostics">查看扫描诊断 / 重试</button>':''}<span class="inventory-status" data-tone="${message?stateTone(message):'info'}" role="status" aria-live="polite" aria-atomic="true"><span class="inventory-status-icon" aria-hidden="true"></span>${escape(message || '原生库存与扫描结果按账号保存，可切换查看。')}</span></div>
      <p class="inventory-hint">同一标签的 DLL 原生读取更新上次原生快照；截图与扫描每次独立保存，不覆盖旧批次。增量、离线和中断扫描显示已识别数量。未观察到的装备状态保持未知；角色、材料、队伍和环境显示各自保存的快照。</p></section>
      <div class="inventory-summaries">${summaries.map(item => {
        const data = snapshot.inventory?.[item.kind], job = status?.job?.domains?.[item.kind];
        const state = (data?.source?.adapter==='ocr-scan-v1'?'OCR · ':'') + (job?.state==='error' ? job.error : job?.state==='reading' ? '正在读取' : data ? '已保存 · ' + new Date(data.saved_at).toLocaleString() : '尚无数据');
        const selected = active===item.kind && equipmentFilter===item.filter;
        const tone=job?.state==='error'?'error':job?.state==='reading'?'working':data?'success':'info';
        return `<button class="inventory-summary ${selected?'is-active':''}" data-inventory-kind="${item.kind}" data-inventory-filter="${item.filter}" aria-pressed="${selected}"><span>${item.label}</span><strong>${data ? item.count : '—'}</strong><small class="inventory-summary-state" data-tone="${tone}">${escape(state)}</small></button>`;
      }).join('')}</div>
      <details class="inventory-other-data"><summary>其他同步数据</summary><div class="inventory-actions">${['items','team','environment'].map(kind=>`<button class="ghost-button" data-inventory-kind="${kind}">${labels[kind]}</button>`).join('')}</div></details>
      <section class="inventory-browser"><div class="inventory-browser-head"><h2>${detailTitle}</h2><label>搜索字段 <input id="inventorySearch" type="search" value="${escape(query)}" placeholder="名称、ID、属性…"></label></div>
      ${domain?`<p class="inventory-hint">来源：${escape(domain.source.adapter)}${domain.coverage.collection_complete!==true?' · 当前仅为已识别部分':''} · ${domain.coverage.account_complete===true?'来源声明完整':'账号整体覆盖未知'} · ${escape(domain.coverage.scope)}。展开记录可查看全部字段。</p>`:''}
      <div class="inventory-records">${filtered.slice(page*50,(page+1)*50).map((row,i) => {
        const title = row.name || (row.character_id != null?'角色 '+row.character_id:row.definition_id != null?'物品 '+row.definition_id:'记录 '+(page*50+i+1));
        const uid = row.instance_id || '';
        const brief = typeof row.quantity==='number' ? '数量 '+row.quantity : typeof row.level==='number' ? 'Lv.'+row.level+(row.is_locked?' · 已锁定':'') : '';
        const ocrIndex=active==='equipment' && ocrBatch && typeof row.instance_id==='string' ? ocrBatch.records.findIndex(item=>item.instance_id===row.instance_id.slice(('ocr:'+ocrBatch.id+':').length)) : -1;
        return `<details class="inventory-record"><summary><b>${escape(title)}</b><span>${escape(brief)} ${escape(uid)}</span></summary><pre>${escape(JSON.stringify(row,null,2))}</pre>${ocrIndex>=0?`<label>修正识别结果<textarea data-inventory-editor="${ocrIndex}" rows="8">${escape(JSON.stringify(ocrBatch.records[ocrIndex],null,2))}</textarea></label><button class="ghost-button" data-inventory="correct" data-index="${ocrIndex}" ${status?.vision_job?.running?'disabled':''}>保存修正</button>`:''}</details>`;
      }).join('') || '<div class="inventory-empty">'+(domain?'没有匹配记录':'此类别还没有成功同步的数据。')+'</div>'}</div>
      <div class="inventory-pagination"><button class="ghost-button" data-inventory="previous" ${page===0?'disabled':''}>上一页</button><span>${page+1} / ${pages} · ${filtered.length} 条</span><button class="ghost-button" data-inventory="next" ${page+1>=pages?'disabled':''}>下一页</button></div>
      ${domain?'<details class="inventory-metadata"><summary>快照范围与字段诊断（角色记录按历次已观测字段累计）</summary><pre>'+escape(JSON.stringify({source:domain.source,coverage:domain.coverage},null,2))+'</pre></details>':''}</section>`;
    root.onclick = async event => {
      const accountButton = event.target.closest('[data-account-action]');
      if (accountButton) {
        const action = accountButton.dataset.accountAction;
        const selected = root.querySelector('#inventoryAccountSelect')?.value || account;
        accountButton.disabled = true;
        try {
          if (action === 'delete-account') {
            const profile = profiles.find(row => row.account === selected);
            if (!profile?.uid) throw Error('当前账号 UID 不存在，请刷新后重试。');
            if (!window.confirm(`删除 UID ${profile.uid}${profile.note ? '（' + profile.note + '）' : ''}？\n\n将永久删除此账号的原生快照、OCR 批次及全部截图、保存的配装方案。其他账号不受影响，此操作无法撤销。`)) {
              accountButton.disabled = false;return;
            }
            const result = await request('/inventory/account/delete',{account:selected,uid:profile.uid});
            status.account_profiles=result.account_profiles;status.config=result.config;
            viewedAccount=result.config.native_account || result.account_profiles[0]?.account || '';
            selectedSource='auto';deletePending=null;noteDraft=null;uidDraft=null;ocrBatch=null;snapshot={domains:{}};page=0;
            window.dispatchEvent(new CustomEvent('keke-account-deleted',{detail:{account:selected}}));
            if(viewedAccount)await refresh(viewedAccount);
            message='已删除 UID '+profile.uid+' 及其本机数据';paint();
          } else if (action === 'save-note') {
            const result = await request('/inventory/account/note', {account:selected, note:root.querySelector('#inventoryAccountNote')?.value || ''});
            status.account_profiles = result.account_profiles;
            noteDraft = null;
            message = '账号备注已保存';
            paint();
          } else {
            const uid = root.querySelector('#inventoryAccountUID')?.value.trim() || '';
            if (!validUid(uid)) throw Error('UID需为8–20位数字，且处于游戏 UID 范围内。');
            let result = await request('/inventory/account/bind', {account:selected, uid, replace_existing:false});
            if (result.uid_mismatch) {
              message = `绑定被拒绝：该资料已有 UID 记录（${(result.existing_uids || []).join('、')}），不能改绑到 UID ${uid}。原数据未更改。`;
              paint();
              return;
            }
            if (result.conflict) {
              const sourceName = result.source?.note || result.source?.account || '当前资料';
              const targetName = result.target?.note || result.target?.account || '目标资料';
              const dataLabel = data => [data?.native_snapshot ? '原生快照' : '', data?.ocr_batches ? `OCR ${data.ocr_batches} 批` : '', data?.saved_plans ? '配装方案' : ''].filter(Boolean).join('、') || '未发现快照或方案';
              const accepted = window.confirm(`UID ${uid} 已关联到「${targetName}」并含${dataLabel(result.target?.data)}。\n\n确认后，UID 将改绑到「${sourceName}」（${dataLabel(result.source?.data)}）；原 UID 资料会保留为未绑定资料，不合并或删除其数据。继续吗？`);
              if (!accepted) { accountButton.disabled = false; return; }
              result = await request('/inventory/account/bind', {account:selected, uid, replace_existing:true});
              if (result.uid_mismatch) {
                message = `绑定被拒绝：该资料已有 UID 记录（${(result.existing_uids || []).join('、')}），不能改绑到 UID ${uid}。原数据未更改。`;
                paint();
                return;
              }
            }
            status.account_profiles = result.account_profiles;
            viewedAccount = result.source?.account || selected;
            noteDraft = null; uidDraft = null; selectedSource = 'auto';
            const successMessage = result.displaced ? 'UID 已改绑；原资料保留为未绑定账号' : 'UID 已绑定到账号资料';
            await refresh(viewedAccount);
            message = successMessage;
            paint();
          }
        } catch(error) {
          message = error.message; paint();
        }
        return;
      }
      const tab = event.target.closest('[data-inventory-kind]');
      if (tab) { active=tab.dataset.inventoryKind; equipmentFilter=tab.dataset.inventoryFilter || ''; page=0; query=''; paint(); return; }
      const button = event.target.closest('[data-inventory]'); if (!button) return;
      const action = button.dataset.inventory;
      if (action==='export') {
        const blob = new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'}), url=URL.createObjectURL(blob), anchor=document.createElement('a');
        anchor.href=url; anchor.download='可可助手账号数据.json'; anchor.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); return;
      }
      if (action==='previous' || action==='next') { page+=action==='next'?1:-1; paint(); return; }
      const selectedAccount = root.querySelector('#inventoryAccountSelect')?.value || account;
      if (action==='load') { deletePending=null; selectedSource='auto'; await refresh(selectedAccount); return; }
      if (action==='read' || action==='diagnostics') {
        const readAccount = action==='diagnostics' ? selectedAccount : (status?.config?.account || selectedAccount);
        window.KekeVision.openAccount(readAccount,{method:action==='diagnostics'?ocrBatch.mode:'native',batchId:action==='diagnostics'?ocrBatch.id:null});
        showUserRoute('vision'); return;
      }
      if (action==='delete' && deletePending!==snapshot.selected_source) { deletePending=snapshot.selected_source;paint();return; }
      button.disabled = true;
      try {
        if (action==='delete') {
          const deletedSource=snapshot.selected_source;
          await request('/inventory/delete',{account,source:deletedSource});
          window.dispatchEvent(new CustomEvent('keke-source-deleted',{detail:{account,source:deletedSource}}));
          deletePending=null;selectedSource='auto';ocrBatch=null;page=0;
          await refresh(account);window.dispatchEvent(new Event('keke-inventory-synced'));return;
        }
        if (action==='correct') {
          const index=Number(button.dataset.index),record=JSON.parse(root.querySelector('[data-inventory-editor="'+index+'"]').value);
          await request('/vision/correct',{account:ocrBatch.account,id:ocrBatch.id,index,record});
          await refresh(account);return;
        }
      } catch(error) {
        const target = root.querySelector('[role="status"]'); if (target) { updateNotice(target,error.message); }
        button.disabled=false;
      }
    };
    root.querySelector('#inventoryAccountSelect').onchange=async event=>{
      const selected=event.target.value;
      viewedAccount=selected;noteDraft=null;uidDraft=null;selectedSource='auto';deletePending=null;
      await refresh(selected);
    };
    root.querySelector('#inventoryAccountNote').oninput=event=>{noteDraft=event.target.value;};
    root.querySelector('#inventoryAccountUID').oninput=event=>{uidDraft=event.target.value;};
    root.querySelector('#inventorySource').value=selectedSource;
    root.querySelector('#inventorySource').onchange=async event=>{deletePending=null;selectedSource=event.target.value;page=0;await refresh(account);};
    root.querySelector('#inventorySearch').oninput = event => {
      const position=event.target.selectionStart; query=event.target.value; page=0; paint(); const input=root.querySelector('#inventorySearch'); input.focus(); input.setSelectionRange(position,position);
    };
  }
  function render() { paint(); refresh(); }
  return {openAccount(value,source='auto'){deletePending=null;noteDraft=null;uidDraft=null;viewedAccount=value;selectedSource=source;page=0;query='';},currentAccount(){return viewedAccount || status?.config?.account || '';},render};
})();
