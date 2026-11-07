/* Dense backpack viewer with selectable entries and pending action controls. */
window.KekeInventoryManagement = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const root = () => document.querySelector('#userInventoryManagementRoute');
  const qualityAliases = {
    gold:['5','gold','orange','橙','橙色','金','金色','s'],
    purple:['4','purple','紫','紫色','a'],
    blue:['3','blue','蓝','蓝色','b']
  };
  const solverShapeIds = {
    H_2:'cell2_style1_1', V_2:'cell2_style2_1',
    H_3:'cell3_style1_1', V_3:'cell3_style2_1',
    L_3_TL:'cell3_style3_1', L_3_TR:'cell3_style4_1', L_3_BL:'cell3_style5_1', L_3_BR:'cell3_style6_1',
    H_4:'cell4_style1_1', V_4:'cell4_style2_1',
    Trap_4_H:'cell4_style5_1', Trap_4_V:'cell4_style6_1'
  };
  const toneQuality = value => {
    const normalized=String(value ?? '').trim().toLowerCase();
    return Object.entries(qualityAliases).find(([,aliases])=>aliases.includes(normalized))?.[0] || 'unknown';
  };
  const labelQuality = value => ({gold:'金色',purple:'紫色',blue:'蓝色'})[toneQuality(value)] || (value ? String(value) : '品质未知');
  const icon = type => type === 'drive'
    ? '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M10 10h28v28H10z"/><path d="M10 19h28M10 29h28M19 10v28M29 10v28"/></svg>'
    : '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="7" y="12" width="34" height="24" rx="5"/><circle cx="17" cy="24" r="5"/><circle cx="31" cy="24" r="5"/><path d="m13 36-3 5m28-5 3 5"/></svg>';
  const escapeShape = value => {
    if (typeof value === 'string' && value) return value;
    if (Array.isArray(value)) return `${value.length} 格`;
    return '';
  };
  const statValue = stat => {
    const raw=stat?.value;
    if (raw == null) return '—';
    const rawText=String(raw).trim();
    const numeric=Number(raw);
    const percent=stat?.is_percent === true || stat?.percent === true;
    // NTE native inventory stores rates as fractions (0.015); OCR records already use percentage points (1.5).
    const fractionalRates=snapshot?.inventory?.equipment?.source?.adapter === 'nte-native-v1';
    const displayNumeric=percent && fractionalRates && !/[％%]$/.test(rawText) ? numeric * 100 : numeric;
    const value=Number.isFinite(numeric) ? displayNumeric.toLocaleString('zh-CN') : rawText;
    return `${value}${percent && !/[％%]$/.test(rawText) ? '%' : ''}`;
  };
  const statLine = stat => {
    const name = stat?.name || stat?.names?.zh_cn || stat?.property_id || stat?.id || '属性';
    return `<div class="bm-stat"><span>${esc(name)}</span><b>${esc(statValue(stat))}</b></div>`;
  };
  const statRows = value => {
    if (Array.isArray(value)) return value;
    if (value && typeof value === 'object') {
      if ('name' in value || 'names' in value || 'property_id' in value || 'id' in value) return [value];
      return Object.entries(value).map(([name, raw]) => ({name, value:raw, is_percent:name.includes('%') || name.includes('百分比')}));
    }
    if (typeof value === 'string' && value.trim()) return [{name:value.trim()}];
    return [];
  };

  let status = null, snapshot = null, account = '', sourceChoice = 'auto';
  let category = 'tape', query = '';
  const emptyFilters=()=>({sets:[],quality:[],state:[],main:[],subs:[],counts:[]});
  let filters=emptyFilters();
  let selected = new Set(), message = '', loading = false, stateActionBusy = false;

  async function request(path, body) {
    const options = {cache:'no-store'};
    if (body) Object.assign(options, {method:'POST', headers:{'Content-Type':'application/json','X-Keke-Inventory':status?.token || ''}, body:JSON.stringify(body)});
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.error || '背包管理数据读取失败，请重试。');
    return data;
  }
  function actualSource() { return snapshot?.selected_source || 'none'; }
  function currentRows() {
    return snapshot?.inventory?.equipment?.records?.filter(row => row?.category === 'drive' || row?.category === 'tape') || [];
  }
  function itemSearchText(row) { return JSON.stringify(row).toLocaleLowerCase(); }
  function statKey(stat) {
    let name=String(stat?.name || stat?.names?.zh_cn || stat?.property_id || stat?.id || '').normalize('NFKC');
    const percent=stat?.is_percent===true || stat?.percent===true || /%|百分比|提升/.test(name);
    name=name.replace(/异能伤害增强|属性伤害加成/g,'伤害').replace(/通用伤害增强|全伤害加成/g,'全伤害').replace(/增加|提升|百分比|固定值|固定|[()（）%\s]/g,'').replace(/属性(?=伤害)/g,'');
    if (/^(攻击力|生命值|防御力)$/.test(name)) return name+(percent?'%':'');
    return name;
  }
  function setKey(row) { return cassetteFor(row)?.id || String(row.set_id ?? row.suit_id ?? ''); }
  function matchesFilters(row,f=filters) {
    const stats=statsFor(row);
    if(f.sets.length && !f.sets.includes(setKey(row)))return false;
    if(f.quality.length && !f.quality.includes(toneQuality(row.rarity ?? row.quality ?? row.rarity_candidate)))return false;
    const states=[];
    if(row.is_equipped===true)states.push('equipped');
    if(row.is_locked===true)states.push('locked');
    if(row.is_discarded===true)states.push('discarded');
    if(row.is_equipped===false && row.is_locked===false && row.is_discarded===false)states.push('other');
    if(f.state.length && !f.state.some(x=>states.includes(x)))return false;
    if(f.main.length && !stats.main.some(x=>f.main.includes(statKey(x))))return false;
    if(f.subs.length){
      if(!stats.subs.length)return false;
      const hits=new Set(stats.subs.map(statKey).filter(x=>f.subs.includes(x))).size;
      if(f.counts.length ? !f.counts.includes(String(hits)) : hits===0)return false;
    }
    return true;
  }
  function filteredRows(f=filters) {
    return currentRows().filter(row => row.category === category)
      .filter(row => !query || itemSearchText(row).includes(query.toLocaleLowerCase()))
      .filter(row=>matchesFilters(row,f));
  }
  function actionDialog(title,content) {
    return new Promise(resolve=>{
      const dialog=document.createElement('dialog');dialog.className='inventory-risk-dialog bm-confirm-dialog';
      dialog.setAttribute('aria-label',title);
      dialog.innerHTML=`<h2>${esc(title)}</h2><div class="bm-confirm-copy">${esc(content)}</div><div class="inventory-actions"><button type="button" data-cancel>取消</button><button type="button" class="primary-button" data-confirm>确认操作</button></div>`;
      dialog.querySelector('[data-cancel]').onclick=()=>dialog.close('cancel');
      dialog.querySelector('[data-confirm]').onclick=()=>dialog.close('confirm');
      dialog.addEventListener('close',()=>{const accepted=dialog.returnValue==='confirm';dialog.remove();resolve(accepted);},{once:true});
      document.body.append(dialog);dialog.showModal();dialog.querySelector('[data-cancel]').focus();
    });
  }
  function openFilters() {
    const draft=structuredClone(filters), dialog=document.createElement('dialog');
    dialog.className='inventory-risk-dialog bm-filter-dialog';dialog.setAttribute('aria-label','背包筛选与批量选择');
    // Game filter screenshots are authoritative for cassette affixes; the encyclopedia's
    // broad descriptive pools are not per-slot eligibility tables.
    const pools={main:new Map(),subs:new Map()};
    const add=(group,stat,label=stat.name)=>{const key=statKey(stat);if(key)pools[group].set(key,label);};
    if(category==='tape'){
      const main=['生命值百分比','攻击力百分比','防御力百分比','暴击率','暴击伤害','环合强度','倾陷强度','治疗加成',
        '光属性异能伤害增强','灵属性异能伤害增强','咒属性异能伤害增强','暗属性异能伤害增强','魂属性异能伤害增强','相属性异能伤害增强','心灵伤害增强'];
      const subs=['生命值百分比','攻击力百分比','防御力百分比','生命值','攻击力','防御力','暴击率','暴击伤害','环合强度','倾陷强度','通用伤害增强'];
      for(const name of main)add('main',{name});
      for(const name of subs)add('subs',{name});
    }else{
      for(const item of window.driverBlockKnowledge?.items || [])for(const tier of Object.values(item.qualities || {})){
        for(const stat of tier.main_stats || [])add('main',stat,stat.name);
        for(const stat of tier.random_stats || [])add('subs',stat,stat.name);
      }
    }
    const sets=new Map();for(const row of currentRows().filter(x=>x.category===category)){const key=setKey(row);if(key)sets.set(key,cassetteFor(row)?.name || String(row.set_id ?? row.suit_id));}
    const group=(key,label,entries)=>`<fieldset><legend>${label}</legend><div class="bm-filter-options">${entries.map(([value,text])=>`<label><input type="checkbox" data-filter="${key}" value="${esc(value)}" ${draft[key].includes(value)?'checked':''}><span>${esc(text)}</span></label>`).join('') || '<small>当前类别没有套装资料</small>'}</div></fieldset>`;
    const render=()=>{
      dialog.innerHTML=`<h2>筛选与批量选择 · ${category==='drive'?'驱动块':'空幕'}</h2><p>同组条件满足任一项即可，不同组同时生效。未选择的筛选项不限。</p><div class="bm-filter-body">${group('sets','套装',[...sets])}${group('state','状态',[['equipped','已装备'],['locked','已锁定'],['discarded','已弃置'],['other','其他']])}${group('quality','品质',[['blue','蓝色'],['purple','紫色'],['gold','橙色']])}${group('main','主属性',[...pools.main])}${group('subs','副属性',[...pools.subs])}${group('counts','符合所选副属性的词条数量',[0,1,2,3,4].map(x=>[String(x),String(x)]))}<p>选择副属性后，数量未选表示至少命中 1 条；选择 0 表示没有命中所选词条。缺少副属性数据的记录不会匹配。</p></div><p class="bm-filter-result" role="status"></p><div class="inventory-actions"><button type="button" data-reset>重置</button><button type="button" data-cancel>取消</button><button type="button" data-apply>应用筛选</button><button type="button" class="primary-button" data-select>选择符合项</button></div>`;
      const update=()=>{dialog.querySelector('.bm-filter-result').textContent=`当前符合 ${filteredRows(draft).length} 件；“选择符合项”会替换当前选择。`;dialog.querySelectorAll('[data-filter="counts"]').forEach(x=>{x.disabled=!draft.subs.length;x.checked=draft.counts.includes(x.value);});};
      dialog.onchange=e=>{const key=e.target.dataset.filter;if(!key)return;draft[key]=[...dialog.querySelectorAll(`[data-filter="${key}"]:checked`)].map(x=>x.value);if(key==='subs'&&!draft.subs.length)draft.counts=[];update();};
      dialog.querySelector('[data-reset]').onclick=()=>{Object.assign(draft,emptyFilters());render();};
      dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();
      const apply=choose=>{filters=structuredClone(draft);if(choose)selected=new Set(filteredRows().map(x=>x.instance_id));else selected=new Set([...selected].filter(id=>filteredRows().some(x=>x.instance_id===id)));dialog.close();paint();};
      dialog.querySelector('[data-apply]').onclick=()=>apply(false);dialog.querySelector('[data-select]').onclick=()=>apply(true);update();
    };
    dialog.addEventListener('close',()=>dialog.remove(),{once:true});render();document.body.append(dialog);dialog.showModal();
  }
  function formatSaved(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '' : date.toLocaleString();
  }
  function sourceLabel(row) {
    const label = row.id.startsWith('ocr:') ? `截图识别 · ${row.mode || ''}` : row.label || '原生库存';
    return `${label}${row.saved_at ? ` · ${formatSaved(row.saved_at)}` : ''}${row.complete === false ? ' · 部分记录' : ''}`;
  }
  function sourceOptions() {
    return `<option value="auto">自动选择 · 优先原生库存</option>${(snapshot?.sources || []).map(row => `<option value="${esc(row.id)}">${esc(sourceLabel(row))}</option>`).join('')}`;
  }
  function normalizedName(value) {
    return String(value ?? '').normalize('NFKC').replace(/[「」『』【】\[\]()（）:：·\s]/g,'').toLocaleLowerCase();
  }
  function cassetteFor(row) {
    const catalog=window.skyCurtainKnowledge?.items || [];
    const suitNames={Suit1:'迪亚波罗斯',Suit2:'森林萤火之心',Suit3:'恶魔之血诅咒',Suit4:'真红双生蝶',Suit5:'街头拳王',Suit6:'失落光芒',Suit7:'守卫王国',Suit8:'影之信条',Suit9:'缇娅的夜间酒馆',Suit10:'小小大冒险',Suit11:'音速蓝刺猬',Suit12:'静谧山庄'};
    const setId=row.set_id ?? row.suit_id;
    const suitKey=typeof setId==='number' || /^\d+$/.test(String(setId ?? '')) ? `Suit${setId}` : setId;
    const candidates=[row.name,suitNames[suitKey]].map(normalizedName).filter(Boolean);
    const names=catalog.flatMap(item=>[
      {item,name:normalizedName(item.name)},
      {item,name:normalizedName(item.screenshot_name)}
    ]).filter(entry=>entry.name).sort((a,b)=>b.name.length-a.name.length);
    return names.find(entry=>candidates.some(name=>name===entry.name || name.includes(entry.name)))?.item;
  }
  function driveFor(row) {
    const catalog=window.driverBlockKnowledge?.items || [];
    const shape=String(row.shape ?? row.shape_id ?? '').trim();
    const geometry=shape.replace(/^EquipmentGeometry_/,'');
    const canonicalId=solverShapeIds[shape.toUpperCase()];
    return catalog.find(item=>item.id===shape || item.id===canonicalId || item.source_data?.type_geometry===shape || String(item.source_data?.type_geometry ?? '').replace(/^EquipmentGeometry_/,'')===geometry);
  }
  function artworkFor(row, quality, resolvedItem) {
    if (quality==='unknown') return '';
    const item=row.category==='drive' ? resolvedItem : cassetteFor(row);
    const asset=row.category==='drive' ? item?.qualities?.gold?.images?.[quality] : item?.images?.[quality];
    return typeof asset?.local_path==='string' ? asset.local_path : '';
  }
  function statsFor(row) {
    const directMain=row.main_attributes ?? row.main_stats;
    const inferredMain=directMain == null ? row.inferred_main_attributes : null;
    const main = statRows(directMain ?? inferredMain);
    const subs = statRows(row.sub_attributes ?? row.sub_stats);
    const mainCount=row.category==='drive' ? 2 : 1;
    return {main:main.slice(0,mainCount), inferred:Boolean(inferredMain), subs:subs.slice(0,4)};
  }
  function card(row) {
    const identity = row.instance_id;
    const qualityValue = row.rarity ?? row.quality ?? row.rarity_candidate;
    const quality = toneQuality(qualityValue);
    const label = labelQuality(qualityValue);
    const shape = row.shape ?? row.shape_id ?? row.parser_result?.shape_id;
    const driverItem=row.category==='drive' ? driveFor({...row,shape}) : null;
    const cellCount = row.cell_count ?? row.area;
    const driveShape=driverItem ? `${driverItem.model} · ${driverItem.shape}` : escapeShape(shape) || (cellCount ? `${cellCount} 格` : '形状未知');
    const kindLabel = row.category === 'drive' ? `驱动块 · ${driveShape}` : '空幕';
    const recognizedName=String(row.name || '').trim();
    const unknownName=/未知套装|未知驱动|unknown/i.test(recognizedName);
    const title = row.category === 'drive' ? driverItem?.name || (!unknownName && recognizedName) || '驱动块' : row.name || '空幕';
    const setId = row.set_id ?? row.suit_id;
    const setLabel = setId ? `套装 ${setId}` : '';
    const checked = selected.has(identity);
    const stats = statsFor(row);
    const artPath=artworkFor(row,quality,driverItem);
    const mainStat=stats.main.length ? stats.main.map(statLine).join('') : '<div class="bm-main-stat-value bm-main-stat-missing">未识别</div>';
    const subStats=stats.subs.map(statLine).join('');
    const imageIcon=artPath ? `<img class="bm-item-artwork" data-bm-artwork src="${esc(artPath)}" alt="" loading="lazy">` : '';
    return `<article class="bm-item-card bm-quality-${quality} is-selectable${checked ? ' is-selected' : ''}" data-bm-card="${esc(identity)}">
      <header class="bm-card-head"><span class="bm-item-mark bm-item-mark-${row.category}"><span class="bm-item-art-fallback" ${artPath ? 'hidden' : ''}>${icon(row.category)}</span>${imageIcon}</span><div class="bm-card-title"><small>${esc(kindLabel)}${row.level != null ? ` · Lv.${esc(row.level)}` : ''}</small><b title="${esc(title)}">${esc(title)}</b></div></header>
      <div class="bm-item-meta"><span class="bm-quality-tag">${esc(label)}</span>${setLabel ? `<span>${esc(setLabel)}</span>` : ''}${row.is_equipped === true ? '<span class="bm-equipped-tag">已装备</span>' : ''}</div>
      <div class="bm-main-stat"><small>${stats.inferred ? '主属性 · 推断' : '主属性'}</small>${mainStat}</div>
      <div class="bm-stat-list"><small class="bm-stat-heading">副属性</small>${subStats || '<span class="bm-no-stats">此记录未包含副属性</span>'}</div>
    </article>`;
  }
  function paint() {
    const host = root(); if (!host) return;
    const profiles = status?.account_profiles || [];
    const selectedProfile = profiles.find(row => row.account === account);
    const all = currentRows();
    const rows = filteredRows();
    const chosenCount = selected.size;
    const selectedRows = all.filter(row => selected.has(row.instance_id));
    const nativeSource = actualSource() === 'native' && snapshot?.inventory?.equipment?.source?.adapter === 'nte-native-v1';
    const riskEnabled = status?.native_risk?.acknowledged === true && status?.native_risk?.enabled === true;
    const stateJob = status?.state_action_job;
    const stateOperationBusy = Boolean(stateActionBusy || stateJob?.running || status?.job?.running || status?.equipment_job?.running || status?.ui_assembly_job?.running || status?.native_operation || status?.vision_job?.running);
    const lockFieldKnown = selectedRows.length > 0 && selectedRows.every(row => typeof row.is_locked === 'boolean');
    const discardFieldKnown = selectedRows.length > 0 && selectedRows.every(row => typeof row.is_discarded === 'boolean');
    const lockLabel = lockFieldKnown && selectedRows.every(row => row.is_locked === true) ? '解锁' : '锁定';
    const discardLabel = discardFieldKnown && selectedRows.every(row => row.is_discarded === true) ? '取消弃置' : '弃置';
    const lockKnown = lockFieldKnown && (lockLabel !== '锁定' || selectedRows.every(row => typeof row.is_discarded === 'boolean'));
    const discardKnown = discardFieldKnown && (discardLabel !== '弃置' || selectedRows.every(row => typeof row.is_locked === 'boolean'));
    const operationDisabled = !selectedRows.length || !nativeSource || !riskEnabled || stateOperationBusy;
    const nativeActionHint = !selectedRows.length ? '先选择装备' : !nativeSource ? '仅支持 DLL 原生库存；OCR 操作尚未接入' : !riskEnabled ? '请先在“读取数据”启用风险模式' : stateOperationBusy ? '当前有读取或装备操作正在进行' : '';
    const lockDisabled = operationDisabled || !lockKnown;
    const discardDisabled = operationDisabled || !discardKnown;
    const stateMessage = stateJob?.running ? `${stateJob.message} · ${stateJob.completed || 0}/${stateJob.total || 0}` : '';
    const dataHint = '当前账号还没有可预览的背包数据。';
    const label = actualSource() === 'native' ? '原生库存' : actualSource().startsWith('ocr:') ? '截图扫描记录' : '无数据';
    host.innerHTML = `<section class="bm-workspace">
      <header class="bm-header"><div><h1>背包管理</h1><p>选择空幕或驱动块并标记弃置，再到游戏内筛选“已弃置”，选择材料并分解。</p></div>
        <div class="bm-data-selectors"><label>UID / 账号<select id="bmAccount" ${loading ? 'disabled' : ''}>${profiles.map(row => `<option value="${esc(row.account)}" ${row.account===account?'selected':''}>${esc(row.display_name)}</option>`).join('') || `<option value="${esc(account)}">${esc(selectedProfile?.display_name || '尚无账号资料')}</option>`}</select></label><label>读取数据<select id="bmSource" ${loading ? 'disabled' : ''}>${sourceOptions()}</select></label><button type="button" class="bm-refresh" data-bm-action="refresh" ${loading ? 'disabled' : ''} aria-label="刷新背包数据" title="刷新背包数据"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.5-2L20 12M4 12l2.4 5a7 7 0 0 0 11.5-2"/></svg></button></div>
      </header>
      <div class="bm-toolbar"><div class="bm-kind-tabs" role="group" aria-label="物品类型"><button type="button" data-bm-kind="tape" aria-pressed="${category==='tape'}">空幕 <b>${all.filter(row=>row.category==='tape').length}</b></button><button type="button" data-bm-kind="drive" aria-pressed="${category==='drive'}">驱动块 <b>${all.filter(row=>row.category==='drive').length}</b></button></div>
        <div class="bm-toolbar-actions" role="group" aria-label="所选条目操作"><button type="button" class="bm-action-button bm-action-lock" data-bm-action="lock" ${lockDisabled?'disabled':''} title="${esc(lockDisabled ? (!lockKnown && selectedRows.length ? '所选装备状态未知，无法安全修改' : nativeActionHint) : '修改游戏内锁定状态')}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg><span>${lockLabel}</span></button><button type="button" class="bm-action-button bm-action-discard" data-bm-action="discard" ${discardDisabled?'disabled':''} title="${esc(discardDisabled ? (!discardKnown && selectedRows.length ? '所选装备状态未知，无法安全修改' : nativeActionHint) : '修改游戏内弃置标记')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg><span>${discardLabel}</span></button>${stateJob?.running?'<button type="button" class="bm-action-button" data-bm-action="cancel-state">停止后续操作</button>':''}</div></div>
      <div class="bm-list-controls"><div class="bm-bulk-actions"><button type="button" data-bm-action="filters">筛选与批量选择${Object.values(filters).some(x=>x.length)?" · 已启用":""}</button><button type="button" data-bm-action="select-visible">全选筛选结果</button><button type="button" data-bm-action="clear-selection">清空选择</button></div><span>显示 <b>${rows.length ? `1–${rows.length}` : '0'}</b> / ${rows.length} 件 <i>·</i> ${chosenCount} 件已选</span></div>
      <div class="bm-search-row"><label class="bm-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg><input id="bmSearch" type="search" value="${esc(query)}" placeholder="搜索名称、套装、词条或驱动形状" aria-label="搜索背包条目"></label></div>
      <div class="bm-status-line" role="status" aria-live="polite">${esc(message || stateMessage || (actualSource()==='none' ? dataHint : `${label} · ${formatSaved(snapshot?.inventory?.equipment?.saved_at) || '保存时间未知'}${snapshot?.inventory?.equipment?.coverage?.collection_complete === false ? ' · 当前为部分记录' : ''}`))}</div>
      ${!all.length ? `<div class="bm-empty"><h2>${actualSource()==='none' ? '没有可预览的数据' : '这份快照没有空幕或驱动块'}</h2><p>${actualSource()==='none' ? '先在“读取数据”中读取游戏数据或导入截图。' : '切换另一份读取数据，或返回读取数据页新增一份快照。'}</p>${actualSource()==='none' ? '<button type="button" data-bm-action="read-data">前往读取数据</button>' : ''}</div>` : rows.length ? `<div class="bm-item-grid">${rows.map(card).join('')}</div>` : '<div class="bm-empty"><h2>没有符合条件的条目</h2><p>清空搜索内容或切换物品类别。</p></div>'}
    </section>`;
    host.querySelector('#bmAccount')?.addEventListener('change', event => switchAccount(event.target.value));
    const sourceSelect=host.querySelector('#bmSource'); if(sourceSelect) sourceSelect.value=sourceChoice;
    sourceSelect?.addEventListener('change', event => switchSource(event.target.value));
    host.querySelector('#bmSearch')?.addEventListener('input', event => {
      const position=event.target.selectionStart; query=event.target.value; paint();
      const input=host.querySelector('#bmSearch'); input?.focus(); input?.setSelectionRange(position,position);
    });
  }
  async function loadData() {
    if (loading) return;
    loading=true; message=''; paint();
    try {
      status=await request('/inventory/status');
      const profiles=status.account_profiles || [];
      if (!profiles.some(row=>row.account===account)) account=profiles.find(row=>row.account===status.config?.account)?.account || profiles[0]?.account || status.config?.account || '默认账号';
      const params=`account=${encodeURIComponent(account)}&source=${encodeURIComponent(sourceChoice)}`;
      snapshot=await request('/inventory/snapshot?'+params);
      if (!currentRows().some(row=>row.category===category)) category=currentRows().some(row=>row.category==='tape')?'tape':'drive';
      message='';
    } catch(error) { snapshot={sources:[],selected_source:'none',inventory:{}}; selected.clear(); message=error.message; }
    finally { loading=false; paint(); }
  }
  async function switchAccount(value) {
    account=value; filters=emptyFilters(); sourceChoice='auto'; message=''; query=''; selected.clear(); await loadData();
  }
  async function switchSource(value) {
    sourceChoice=value; filters=emptyFilters(); message=''; query=''; selected.clear(); await loadData();
  }
  async function performStateAction(field) {
    if (stateActionBusy) return;
    const ids=[...selected];
    if (!ids.length) return;
    stateActionBusy=true;
    message='正在生成状态操作清单…';
    paint();
    try {
      const plan=await request('/inventory/equipment/state-preview',{account,source:actualSource(),instance_ids:ids,field});
      const actionName=field==='locked'?(plan.target?'锁定':'解锁'):(plan.target?'弃置':'取消弃置');
      const names=plan.items.slice(0,12).map(row=>`· ${row.name}（${row.category==='drive'?'驱动块':'空幕'}）`).join('\n');
      const more=plan.total>12?`\n· 另有 ${plan.total-12} 件` : '';
      const clearDiscard=plan.items.filter(row=>row.clears==='discarded').length;
      const unlock=plan.items.filter(row=>row.clears==='locked').length;
      const sideEffects=[
        clearDiscard ? `· 为锁定装备，将先取消 ${clearDiscard} 件的弃置标记` : '',
        unlock ? `· 为弃置装备，将先解锁 ${unlock} 件` : ''
      ].filter(Boolean).join('\n');
      const discardInstruction=field==='discarded' && plan.target ? '\n\n标记完成后，请到游戏的空幕分解页面筛选“已弃置”，核对物品后选择经验材料或倒带材料并分解。筛选结果也可能包含之前已弃置的物品。' : '';
      const accepted=await actionDialog(`确认${actionName}`, `将通过 DLL 修改游戏内 ${plan.total} 件装备的状态为“${actionName}”。${sideEffects?`\n\n${sideEffects}`:''}\n\n${names}${more}${discardInstruction}\n\n确认继续？`);
      if (!accepted) { message='已取消，未修改游戏状态。'; return; }
      message=`正在执行${actionName}，等待原生快照复核…`;
      paint();
      await request('/inventory/equipment/state-start',{token:plan.token});
      status=await request('/inventory/status');
      paint();
      while (status.state_action_job?.running) {
        await new Promise(resolve=>setTimeout(resolve,400));
        status=await request('/inventory/status');
        message=status.state_action_job?.message || message;
        paint();
      }
      const finalMessage=status.state_action_job?.message || '状态操作已结束。';
      selected.clear();
      await loadData();
      message=finalMessage+(field==='discarded' && plan.target ? ' 请到游戏分解页面筛选“已弃置”，核对物品并选择分解材料后手动分解。' : '');
    } catch(error) {
      message=error.message;
    } finally {
      stateActionBusy=false;
      paint();
    }
  }
  function handleClick(event) {
    const kind=event.target.closest('[data-bm-kind]');
    if (kind) { category=kind.dataset.bmKind; filters=emptyFilters(); selected.clear(); paint(); return; }
    const actionButton=event.target.closest('[data-bm-action]');
    if (actionButton) {
      const action=actionButton.dataset.bmAction;
      if (action==='filters') { openFilters(); return; }
      if (action==='select-visible') { selected=new Set(filteredRows().map(x=>x.instance_id)); paint(); return; }
      if (action==='clear-selection') { selected.clear(); paint(); return; }
      if (action==='refresh') { loadData(); return; }
      if (action==='read-data') { window.showUserRoute?.('vision'); return; }
      if (action==='lock') { performStateAction('locked'); return; }
      if (action==='discard') { performStateAction('discarded'); return; }
      if (action==='cancel-state') { request('/inventory/equipment/state-cancel',{}).then(result=>{status={...status,state_action_job:result};message=result.message;paint();}).catch(error=>{message=error.message;paint();}); return; }
    }
    const itemCard=event.target.closest('[data-bm-card]');
    if (itemCard && !event.target.closest('button,input,label,a,select')) {
      const id=itemCard.dataset.bmCard;
      if (event.ctrlKey || event.metaKey) {
        if (selected.has(id)) selected.delete(id); else selected.add(id);
      } else {
        selected.clear();
        selected.add(id);
      }
      paint(); return;
    }
  }
  function bind() {
    const host=root(); if (!host || host.dataset.bound==='true') return;
    host.dataset.bound='true'; host.addEventListener('click',handleClick);
    document.addEventListener('keydown',event=>{
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase()!=='a') return;
      const target=event.target instanceof Element ? event.target : null;
      if (target?.closest('input,textarea,select,[contenteditable="true"]')) return;
      const activeHost=root();
      if (!activeHost?.getClientRects().length) return;
      const rows=filteredRows();
      if (!rows.length) return;
      event.preventDefault();
      selected=new Set(rows.map(row=>row.instance_id));
      paint();
    });
    host.addEventListener('error',event=>{
      if (event.target.matches?.('[data-bm-artwork]')) {
        event.target.hidden=true;
        if (event.target.previousElementSibling?.matches('.bm-item-art-fallback')) event.target.previousElementSibling.hidden=false;
      }
    },true);
    for (const name of ['keke-inventory-synced','keke-account-changed','keke-account-deleted','keke-source-deleted']) {
      window.addEventListener(name,event=>{
        if (event.detail?.account && event.detail.account !== account) return;
        if (event.detail?.account) account=event.detail.account;
        if (event.detail?.source && event.detail.account===account && event.detail.source===actualSource()) sourceChoice='auto';
        sourceChoice='auto'; selected.clear(); loadData();
      });
    }
  }
  function render() { bind(); paint(); loadData(); }
  return {render};
})();
