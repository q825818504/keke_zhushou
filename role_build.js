/* Owned roster and equipment come exclusively from the selected account's native snapshot. */
window.KekeRoleBuild = (() => {
  let tab = "calculate", snapshot = null, account = "", accountProfiles = [], message = "", generation = 0, selectedRoleId = "", query = "", loading = false;
  let worker = null, calculating = false, proposal = null, excludeOthers = true, actionBusy = false, actionMessage = '', operationPreview = null, job = null;
  let pollTimer=null, pollGeneration=0, globalNotice='', nativeReadBusy=false;
  let pendingDeleteRole=null, deleteDialog=null;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const root = () => document.querySelector("#userRoleBuildPlusRoute");
  const score = value => Number.isFinite(value) ? value.toFixed(1) : "—";
  const locksKey=()=>`keke-plus-role-locks:${encodeURIComponent(snapshot?.account_uid||account)}`;
  function roleLocks(){try{const value=JSON.parse(localStorage.getItem(locksKey())||'[]');return new Set(Array.isArray(value)?value.map(String):[]);}catch{return new Set();}}
  function toggleRoleLock(role){
    try{
      const locks=roleLocks();if(locks.has(role.id))locks.delete(role.id);else locks.add(role.id);
      localStorage.setItem(locksKey(),JSON.stringify([...locks]));clearCalculation();
      actionMessage=locks.has(role.id)?`已锁定 ${role.name} 当前装备，其他角色计算时不会使用这些装备。`:`已解除 ${role.name} 的装备保护。`;paint();
    }catch{actionMessage='角色锁保存失败，请检查本机存储后重试。';paint();}
  }
  function unlockAllRoles(){
    if(!snapshot?.account_uid)return;
    try{
      localStorage.removeItem(locksKey());clearCalculation();
      actionMessage='已解除当前 UID 的全部角色装备保护。';paint();
    }catch{actionMessage='解锁失败，请检查本机存储后重试。';paint();}
  }
  const lockIcon=()=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v3"/></svg>';
  function lockButton(role,disabled){
    const locked=roleLocks().has(role.id);
    return `<button type="button" class="rb-lock-toggle${locked?' is-locked':''}" data-role-lock aria-pressed="${locked}" aria-label="${locked?'解锁':'锁定'}${esc(role.name)}的当前配装" title="${locked?'已锁定：其他角色计算时不会使用其装备':'锁定当前角色已装备的空幕与驱动'}" ${disabled?'disabled':''}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v3"/></svg></button>`;
  }
  function openDeleteConfirmation(role) {
    if(!deleteDialog){
      deleteDialog=document.createElement('dialog');
      deleteDialog.className='rb-confirm-dialog';
      deleteDialog.setAttribute('aria-labelledby','rbDeleteTitle');
      deleteDialog.setAttribute('aria-describedby','rbDeleteMessage');
      deleteDialog.innerHTML='<h2 id="rbDeleteTitle">删除已保存方案</h2><p id="rbDeleteMessage" data-delete-message></p><div class="rb-confirm-actions"><button type="button" class="rb-button rb-confirm-cancel" data-delete-cancel>取消</button><button type="button" class="rb-button rb-confirm-accept" data-delete-accept>删除方案</button></div>';
      document.body.append(deleteDialog);
      deleteDialog.querySelector('[data-delete-cancel]').addEventListener('click',()=>{pendingDeleteRole=null;deleteDialog.close();});
      deleteDialog.querySelector('[data-delete-accept]').addEventListener('click',()=>{const roleToDelete=pendingDeleteRole;pendingDeleteRole=null;deleteDialog.close();if(roleToDelete)perform('delete',roleToDelete);});
      deleteDialog.addEventListener('cancel',()=>{pendingDeleteRole=null;});
      deleteDialog.addEventListener('click',event=>{if(event.target===deleteDialog){pendingDeleteRole=null;deleteDialog.close();}});
    }
    pendingDeleteRole=role;
    deleteDialog.querySelector('[data-delete-message]').textContent=`确定删除${role.name}的已保存方案？此操作无法撤销。`;
    if(!deleteDialog.open)deleteDialog.showModal();
  }
  // Native names include presentation quotes, e.g. 「零」 vs encyclopedia 零.
  const nameKey = value => String(value ?? "").normalize('NFKC').replace(/[\s\p{P}\p{S}]/gu, "").toLowerCase();
  const statName = value => value?.names?.zh_cn || value?.name || value?.property_id || value?.id || "未知属性";
  const stats = item => [...(item.main_stats || item.main_attributes || []), ...(item.sub_stats || item.sub_attributes || [])];
  const percent = value => value?.percent === true || value?.is_percent === true;
  const amount = value => Number(value.value) * (percent(value) ? 100 : 1);
  const number = value => Number(value.toFixed(2)).toLocaleString("zh-CN");

  async function request(path, body, token) {
    const response = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json", "X-Keke-Inventory": token || "" }, body: JSON.stringify(body) } : { cache: "no-store" });
    let result;
    try { result = await response.json(); } catch { throw Error("桌面读取服务没有返回有效数据"); }
    if (!response.ok) throw Error(result.error || "读取服务不可用");
    return result;
  }

  function roles() {
    if (!snapshot?.ready || !Array.isArray(snapshot.characters)) return [];
    const library = typeof characterData === "undefined" ? [] : Object.entries(characterData);
    const seen = new Set();
    return snapshot.characters.filter(row => {
      const id = String(row.character_id ?? "");
      if (!id || seen.has(id)) return false;
      seen.add(id); return true;
    }).map(row => {
      const match = library.find(([name, data]) => (data.knowledge?.assets?.some(asset => asset.type === 'character_icon' && String(asset.source_url || '').includes('/Appearance/' + row.character_id + '/')) || String(data.id) === String(row.character_id)) || nameKey(name) === nameKey(row.name));
      return { id: String(row.character_id), name: row.name || match?.[0] || `角色 ${row.character_id}`, data: match?.[1], native: row, cassette: match?.[1]?.knowledge?.recommended?.cassette };
    });
  }

  const DRIVER_ASSET_BOUNDS = {"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type2-h.webp":[55,89,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type2-v.webp":[89,54,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-h.webp":[30,93,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-lb.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-lt.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-rb.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-rt.webp":[55,55,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-v.webp":[92,33,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-h.webp":[18,92,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-v.webp":[97,19,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-z-h.webp":[34,63,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-z-v.webp":[63,33,131,192],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type2-h.webp":[55,88,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type2-v.webp":[89,53,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-h.webp":[30,92,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-lb.webp":[54,54,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-lt.webp":[54,54,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-rb.webp":[55,53,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-rt.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-v.webp":[92,32,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-h.webp":[18,91,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-v.webp":[97,18,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-z-h.webp":[34,62,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-z-v.webp":[63,32,131,192],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_baoji.webp":[14,14,100,100],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_baojishanghai.webp":[14,14,100,100],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_fangyu.webp":[32,28,64,82],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_gongji.webp":[23,29,82,71],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_kangxing.webp":[18,25,92,78],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_shengming.webp":[16,22,96,84],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/Icon_attri_strength_qingxian.webp":[18,34,92,60],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/Icon_attri_surpass.webp":[28,21,72,87],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type2-h.webp":[55,89,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type2-v.webp":[89,54,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-h.webp":[30,93,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-lb.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-lt.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-rb.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-rt.webp":[55,55,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-v.webp":[92,33,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-h.webp":[18,92,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-v.webp":[97,19,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-z-h.webp":[34,63,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-z-v.webp":[63,33,131,192]};
  const scorer = () => window.KekeCassetteScoring;
  function driveCatalog(item) {
    const shape = window.NativeAssemblyPlanner?.shapeOf(item);
    return (window.driverBlockKnowledge?.items || []).find(row => shape ? row.id === shape.id : row.source_data?.type_geometry?.replace('EquipmentGeometry_', '') === String(item.shape).replace('EquipmentGeometry_', ''));
  }
  function quality(item) {
    const value = String(item.rarity || '').toLowerCase();
    return /orange|gold|金/.test(value) ? 'gold' : /purple|紫/.test(value) ? 'purple' : 'blue';
  }
  function equippedFor(role) {
    return (snapshot?.items || []).filter(item => item.owner != null && String(item.owner) === role.id);
  }
  function tapeCatalogFor(item, role) {
    const catalog=window.skyCurtainKnowledge?.items||[];
    return catalog.find(row=>nameKey(row.name)===nameKey(item?.name)) || catalog.find(row=>row.id===role?.cassette?.id);
  }
  function assessment(role, plan=null) {
    const planned=plan?proposedItems(plan):null;
    const items = planned?[...(planned.tape?[planned.tape]:[]),...planned.drives]:equippedFor(role), tapes = items.filter(item => item.category === 'tape'), drives = items.filter(item => item.category === 'drive');
    const catalog = tapeCatalogFor(tapes[0],role);
    const configured = role.cassette?.recommended_main_affixes?.length && role.cassette?.recommended_sub_affixes?.length;
    const tape = configured && tapes.length === 1 && (tapes[0].main_stats || tapes[0].main_attributes)?.length && (tapes[0].sub_stats || tapes[0].sub_attributes)?.length ? scorer()?.scoreItem(tapes[0], role.cassette, catalog) : null;
    const driveScores = drives.map(item => ({ item, ...scorer()?.scoreDrive(item, role.cassette, driveCatalog(item)) }));
    const overall = configured ? scorer()?.scoreLoadout(tapes.length ? tape?.score : 0, driveScores, role.native.board) : null;
    return { items, tapes, drives, tape, driveScores, overall };
  }
  function gradeBadge(value) {
    const grade = scorer()?.grade(value);
    return grade ? `<b class="rb-grade rb-grade-${grade.toLowerCase()}">${grade}</b>` : '<span class="rb-muted">待评分</span>';
  }
  function driveImage(item, boardImage = false) {
    const catalog = driveCatalog(item), tier = quality(item);
    const path = Object.values(catalog?.qualities || {}).find(row => row.images?.[tier])?.images[tier]?.local_path;
    if (!path) return '<span class="rb-muted">形状未识别</span>';
    const bounds = DRIVER_ASSET_BOUNDS[path] || [0,0,256,256];
    return `<svg class="rb-drive-art${boardImage ? ' is-board-art' : ''}" viewBox="${bounds.join(' ')}" preserveAspectRatio="${boardImage ? 'none' : 'xMidYMid meet'}" role="img" aria-label="${esc(item.name || '驱动块')}"><image href="${esc(path)}" width="256" height="256"/></svg>`;
  }

  function pieceOutline(item) {
    const cells=item.cells||[], keys=new Set(cells.map(([r,c])=>`${r}:${c}`));
    const rows=Math.max(...cells.map(p=>p[0]))+1, columns=Math.max(...cells.map(p=>p[1]))+1;
    const edges=[];
    for(const [r,c] of cells){
      const x=c*100,y=r*100;
      if(!keys.has(`${r-1}:${c}`))edges.push(`M${x},${y}h100`);
      if(!keys.has(`${r+1}:${c}`))edges.push(`M${x},${y+100}h100`);
      if(!keys.has(`${r}:${c-1}`))edges.push(`M${x},${y}v100`);
      if(!keys.has(`${r}:${c+1}`))edges.push(`M${x+100},${y}v100`);
    }
    return `<svg class="rb-piece-outline rb-quality-${quality(item)}" viewBox="-2 -2 ${columns*100+4} ${rows*100+4}" preserveAspectRatio="none" aria-hidden="true"><path class="rb-piece-edge-separation" d="${edges.join('')}"/><path class="rb-piece-edge-highlight" d="${edges.join('')}"/></svg>`;
  }

  function avatar(role) {
    return role.data?.icon ? `<img src="${esc(role.data.icon)}" alt="" loading="lazy">` : `<span>${esc(role.name.slice(0, 1))}</span>`;
  }

  function statChips(attributes, main = false) {
    return (attributes || []).map(attribute => `<span class="rb-stat-chip${main ? ' rb-main-stat' : ''}">${main ? '<small>主</small>' : ''}${esc(statName(attribute))}${Number.isFinite(attribute.value) ? ` <b>${number(amount(attribute))}${percent(attribute) ? "%" : ""}</b>` : ""}</span>`).join("") || `<span class="rb-muted">${main ? '主' : '副'}属性尚未读取</span>`;
  }

  function tapeImage(item) {
    const catalog = tapeCatalogFor(item);
    const path = catalog?.images?.[quality(item)]?.local_path;
    return path ? `<img class="rb-tape-art" src="${esc(path)}" alt="${esc(catalog.name)}">` : '<span class="rb-muted">空幕图片待匹配</span>';
  }

  function board(role, drives) {
    if (!Array.isArray(role.native.board) || !role.native.board.length) return '<div class="rb-board-empty">该角色盘面尚未识别</div>';
    const active = new Set(role.native.board.map(([r, c]) => `${r}:${c}`)), occupied = new Map();
    drives.forEach((item, index) => {
      if (!item.placement || !Array.isArray(item.cells)) return;
      item.cells.forEach(([r, c]) => occupied.set(`${r + item.placement.row}:${c + item.placement.column}`, { item, index }));
    });
    return `<div class="rb-board" role="img" aria-label="${esc(role.name)}当前已读取驱动盘面">${Array.from({ length: 25 }, (_, i) => {
      const key = `${Math.floor(i / 5) + 1}:${i % 5 + 1}`, piece = occupied.get(key);
      return `<span class="rb-board-cell${!active.has(key) ? " is-disabled" : ""}${piece ? ` is-filled rb-piece-${piece.index % 6}` : ""}" style="grid-row:${Math.floor(i / 5)+1};grid-column:${i%5+1}" title="${esc(piece ? piece.item.label + ' · ' + piece.item.name : active.has(key) ? '空槽' : '不可用槽位')}"></span>`;
    }).join("")}${drives.map(item => {
      if (!item.placement || !item.cells?.length) return '';
      const rows = item.cells.map(cell => cell[0]), columns = item.cells.map(cell => cell[1]);
      const minR = Math.min(...rows), minC = Math.min(...columns), height = Math.max(...rows)-minR+1, width = Math.max(...columns)-minC+1;
      return `<div class="rb-board-piece rb-board-art-layer" style="grid-row:${item.placement.row+minR} / span ${height};grid-column:${item.placement.column+minC} / span ${width}" title="${esc(item.label+' · '+item.name)}">${driveImage(item,true)}</div>`;
    }).join('')}${drives.map(item => {
      if (!item.placement || !item.cells?.length) return '';
      const rows = item.cells.map(cell => cell[0]), columns = item.cells.map(cell => cell[1]);
      const minR = Math.min(...rows), minC = Math.min(...columns), height = Math.max(...rows)-minR+1, width = Math.max(...columns)-minC+1;
      return `<div class="rb-board-piece rb-board-outline-layer" style="grid-row:${item.placement.row+minR} / span ${height};grid-column:${item.placement.column+minC} / span ${width}" aria-hidden="true">${pieceOutline(item)}</div>`;
    }).join('')}</div>`;
  }

  function summary(items, title='当前装备属性汇总') {
    const totals = new Map();
    items.flatMap(stats).forEach(attribute => {
      if (!Number.isFinite(attribute.value)) return;
      const name = statName(attribute), key = `${name}:${percent(attribute)}`;
      const total = totals.get(key) || { name, percent: percent(attribute), value: 0 };
      total.value += amount(attribute); totals.set(key, total);
    });
    return `<section class="rb-summary"><h3>${esc(title)}</h3><dl>${[...totals.values()].map(row => `<div><dt>${esc(row.name)}</dt><dd>+${number(row.value)}${row.percent ? "%" : ""}</dd></div>`).join("") || '<div><dt>没有可展示的装备属性</dt><dd>—</dd></div>'}</dl><p>只合计装备词条，未计角色基础属性与套装效果。</p></section>`;
  }

  function gearRow(item, kind, entry) {
    const value = entry?.score;
    return `<article class="rb-gear-row"><div class="rb-gear-symbol">${kind === '驱动' ? driveImage(item) : tapeImage(item)}</div><div class="rb-gear-copy"><div class="rb-gear-title"><b>${esc(item.name || kind)}</b><span>${esc(item.label || '')}</span>${item.level != null ? `<span>强化 +${esc(item.level)}</span>` : ''}${statChips(item.main_stats || item.main_attributes, true)}</div><div class="rb-stat-chips rb-sub-stats">${statChips(item.sub_stats || item.sub_attributes)}</div>${kind === '空幕' && entry ? `<p class="rb-item-breakdown">主属性 ${score(entry.mainPoints)} / 60 · 副属性 ${score(entry.subPoints)} / 40</p>` : ''}</div><div class="rb-item-score"><span><strong>${score(value)}</strong><small>/100</small></span>${gradeBadge(value)}</div></article>`;
  }

  function clearCalculation() {
    worker?.terminate(); worker=null; calculating=false; proposal=null; operationPreview=null;
  }

  function proposedItems(plan) {
    const tape=(snapshot?.items||[]).find(item=>item.id===plan.core);
    const drives=plan.modules.map(position=>{
      const item=snapshot.items.find(row=>row.id===position.id);
      return item ? {...item,placement:{row:position.row,column:position.column}} : null;
    }).filter(Boolean);
    return {tape,drives};
  }

  function planView(role, plan, saved=false) {
    const {tape,drives}=proposedItems(plan);
    const transfers=[...(tape?[tape]:[]),...drives].filter(item=>item.owner!=null&&String(item.owner)!==role.id).length;
    return `<div class="rb-plan-context"><p>${saved?'已保存方案 · '+esc(plan.saved_at):plan.complete?'计算结果 · 推荐空幕四件套内最高分':'计算结果 · 搜索未证实最优'} · ${!saved&&plan.schemes_evaluated?`已比较 ${esc(plan.schemes_evaluated)} 种驱动组合 · `:''}${plan.exclude_others?'不使用其他角色装备':'允许转移其他角色装备'}${transfers?' · 将转移 '+transfers+' 件':''}${plan.skipped?' · '+plan.skipped+' 件数据不完整未参与':''}</p><span>下方盘面、装备、属性汇总和评分均展示此方案${saved?'':'，保存与计算不会改动游戏装备'}。</span></div>`;
  }

  function actions(role) {
    const disabled=loading||calculating||actionBusy||job?.running;
    const saved=snapshot.saved_plans?.[role.id];
    const chosen=tab==='calculate'?proposal:saved?.valid?saved:null;
    const preview=operationPreview;
    const batchPreview=preview?.execution_mode==='one_key';
    const operationStatus=job?`<div class="rb-operation-status" role="status">${esc(job.message)} · ${esc(job.completed||0)} / ${esc(job.total||0)}${job.running?(job.batch_active?'<span class="rb-muted">批量指令已提交，完成核验前无法中断</span>':'<button type="button" class="rb-button" data-build-cancel>停止操作</button>'):''}${job.unknown?'<button type="button" class="rb-button" data-build-status>重新查询状态</button>':''}</div>`:'';
    return `<section class="rb-actions"><div class="rb-section-heading"><h3>${tab==='calculate'?'毕业配装计算':'保存方案与游戏操作'}</h3>${tab==='calculate'?lockButton(role,disabled):''}</div>${tab==='calculate'?`<label class="rb-exclude"><input type="checkbox" data-build-exclude ${excludeOthers?'checked':''} ${disabled?'disabled':''}>不使用其他角色已装备的驱动与空幕<span>本角色当前装备仍参与</span></label><div class="rb-action-buttons"><button type="button" class="rb-button rb-button-primary" data-build-calculate ${disabled?'disabled':''}>${calculating?'正在搜索合法搭配…':'计算毕业配装'}</button>${calculating?'<button type="button" class="rb-button" data-build-stop>停止计算</button>':''}<button type="button" class="rb-button" data-build-save ${disabled||!proposal?'disabled':''}>保存该角色方案</button></div>`:`<div class="rb-action-buttons"><button type="button" class="rb-button rb-button-primary" data-build-equip ${disabled||!saved?.valid?'disabled':''}>自动装配已保存方案</button><button type="button" class="rb-button" data-build-unequip ${disabled?'disabled':''}>拆卸本角色空幕与驱动</button></div>${!saved?'<p class="rb-muted">请先在计算配装中计算并保存该角色方案。</p>':!saved.valid?`<p class="rb-action-notice">${esc(saved.reason)}。请重新计算并保存。</p>`:''}`}${chosen?planView(role,chosen,tab==='game'):''}${preview?`<div class="rb-operation-preview"><h3>${preview.operation==='assembly'?'自动装配预览':'拆卸预览'}</h3><p>${batchPreview?'空幕和驱动将通过一次批量指令提交，完成后整体核验':`共 ${preview.total} 步`}${preview.transfers?` · 从其他角色转移 ${preview.transfers} 件`:''}</p><ol>${preview.items.map(item=>`<li>${item.action==='equip'?'装入':'卸下'} · ${esc(item.character_name)} · ${esc(item.label)} ${esc(item.name)}</li>`).join('')}</ol>${preview.total?`<button class="rb-button rb-button-primary" type="button" data-build-execute ${disabled?'disabled':''}>${batchPreview?'确认一键装配并核验':`确认执行 ${preview.total} 步`}</button>`:'<p>当前装备与方案一致，无需操作。</p>'}<button class="rb-button" type="button" data-build-dismiss ${disabled?'disabled':''}>关闭预览</button></div>`:''}${operationStatus}${actionMessage?`<p class="rb-action-notice" role="status">${esc(actionMessage)}</p>`:''}</section>`;
  }

  function calculate(role) {
    clearCalculation(); calculating=true; actionMessage=''; if(!job?.running)job=null;paint();
    const current=generation, roleId=role.id;
    try{
      worker=new Worker('loadout_worker.js');
      worker.onmessage=event=>{
        if(current!==generation||selectedRoleId!==roleId)return;
        worker?.terminate();worker=null;calculating=false;
        if(event.data.error)actionMessage=event.data.error;
        else {proposal=event.data.result;actionMessage=proposal.complete?`已比较 ${proposal.schemes_evaluated} 种驱动组合，并在推荐空幕四件套约束内验证为最高分。`:'已找到可用方案，但搜索达到限制，尚未证明为最高分。';}
        paint();
      };
      worker.onerror=()=>{worker?.terminate();worker=null;calculating=false;actionMessage='计算线程无法运行，请刷新重试。';paint();};
      worker.postMessage({snapshot,characterId:role.id,cassette:role.cassette,excludeOthers,protectedOwners:[...roleLocks()],driverCatalog:window.driverBlockKnowledge,tapeCatalog:window.skyCurtainKnowledge});
    }catch(error){calculating=false;actionMessage=error.message;paint();}
  }

  async function perform(action, role) {
    if(actionBusy)return;
    const current=generation, targetAccount=account, targetRole=role.id;
    actionBusy=true;actionMessage='';paint();
    try{
      const status=await request('/inventory/status');
      if(current!==generation||selectedRoleId!==targetRole)throw Error('账号或角色已切换，请重试');
      if(action==='save'){
        if(!proposal)throw Error('请先计算方案');
        const protectedRoles=roleLocks();
        const chosenIds=new Set([proposal.core,...proposal.modules.map(row=>row.id)]);
        if(snapshot.items.some(item=>chosenIds.has(item.id)&&item.owner!=null&&String(item.owner)!==role.id&&protectedRoles.has(String(item.owner))))throw Error('方案包含已锁定角色的装备，请重新计算。');
        const saved=await request('/inventory/equipment/save-build',{account:targetAccount,selection_id:snapshot.selection_id,character_id:Number(role.id),...proposal},status.token);
        if(current===generation){snapshot.saved_plans||={};snapshot.saved_plans[role.id]=saved;actionMessage='方案已保存，可在游戏配装中自动装配。';}
      }else if(action==='equip'||action==='unequip'){
        const path=action==='equip'?'/inventory/equipment/saved-preview':'/inventory/equipment/preview';
        const body=action==='equip'?{account:targetAccount,character_id:Number(role.id)}:{account:targetAccount,character_ids:[Number(role.id)],categories:['drive','tape']};
        const preview=await request(path,body,status.token);
        if(current===generation&&selectedRoleId===targetRole)operationPreview=preview;
      }else if(action==='delete'){
        if(!snapshot?.saved_plans?.[role.id])throw Error('该角色没有已保存方案，请刷新快照');
        await request('/inventory/equipment/delete-build',{account:targetAccount,character_id:Number(role.id)},status.token);
        if(current===generation&&selectedRoleId===targetRole){delete snapshot.saved_plans[role.id];proposal=null;operationPreview=null;globalNotice=`${role.name} 的已保存方案已删除`;}
      }else if(action==='execute'){
        if(!operationPreview?.token)throw Error('请重新生成操作预览');
        job=await request('/inventory/equipment/start',{token:operationPreview.token},status.token);operationPreview=null;
        pollOperation(targetAccount);
      }else if(action==='cancel'){
        if(!status.equipment_job?.running || status.equipment_job.account!==job?.account)throw Error('后台任务状态已变化，请重新查询后操作');
        job=await request('/inventory/equipment/cancel',{},status.token);
        pollOperation(job.account);
      }
    }catch(error){actionMessage=error.message;}
    finally{actionBusy=false;paint();}
  }

  async function pollOperation(targetAccount,failures=0) {
    clearTimeout(pollTimer);const currentPoll=++pollGeneration;
    try{
      const status=await request('/inventory/status');
      if(currentPoll!==pollGeneration)return;
      const current=status.equipment_job;
      if(!current||current.account!==targetAccount)throw Error('操作状态已变化，请刷新快照核对');
      job=current;paint();
      if(current.running || status.native_operation || status.job?.running){
        if(!current.running){
          job={...current,running:true,message:'装配结果已核验，正在载入最新装备快照…'};
          paint();
        }
        pollTimer=setTimeout(()=>pollOperation(targetAccount),800);
      }
      else if(account===targetAccount){clearCalculation();await load(targetAccount);}
    }catch(error){
      if(currentPoll!==pollGeneration)return;
      job={...job,account:targetAccount,running:true,unknown:true,message:'执行状态待确认：'+error.message+(job?.batch_active?'。批量指令已提交，请重新查询结果。':'。可停止操作或重新查询。')};paint();
      if(failures<4)pollTimer=setTimeout(()=>pollOperation(targetAccount,failures+1),Math.min(1000*2**failures,5000));
    }
  }

  function details(role) {
    const saved=snapshot.saved_plans?.[role.id];
    const deleteButton=tab==='game'&&saved?`<button type="button" class="rb-button rb-delete-plan" data-build-delete aria-label="删除${esc(role.name)}的已保存方案" ${loading||actionBusy||job?.running?'disabled':''}>删除此方案</button>`:'';
    if(tab==='game'&&!saved?.valid)return `<section class="rb-detail"><header class="rb-detail-heading"><div class="rb-selected-role">${avatar(role)}<h2>${esc(role.name)}</h2></div><div class="rb-detail-side">${deleteButton}</div></header>${actions(role)}</section>`;
    const plan=tab==='calculate'?proposal:saved;
    const { items, tapes, drives, tape, driveScores, overall } = assessment(role,plan);
    return `<section class="rb-detail"><header class="rb-detail-heading"><div class="rb-selected-role">${avatar(role)}<div><h2>${esc(role.name)}</h2><span>${plan?(tab==='game'?'已保存方案':'计算结果预览'):'当前游戏快照'} · 空幕 ${tapes.length} / 驱动 ${drives.length}</span></div></div><div class="rb-detail-side"><div class="rb-build-metrics"><div><span>空幕毕业率</span><b>${tapes.length ? score(tape?.score) : '0.0'}<small>%</small></b></div><div><span>配装毕业率</span><b>${score(overall?.graduation)}<small>%</small></b></div><div class="rb-score-total"><span>总分</span><b>${score(overall?.total)}</b><small>/ 200</small>${gradeBadge(overall?.graduation)}</div></div>${deleteButton}</div></header>${actions(role)}<div class="rb-loadout-overview"><section class="rb-board-section"><h3>${plan?'方案驱动盘面':'当前驱动盘面'}</h3>${board(role, drives)}<p>${overall ? `已填 ${overall.filled} / ${overall.capacity} 格 · 驱动盘面 ${score(overall.driveScore)} / 100` : '读取快照中的摆放位置'}</p></section>${summary(items,plan?'方案装备属性汇总':'当前装备属性汇总')}</div><section class="rb-current-gear"><div class="rb-section-heading"><h3>${plan?'方案空幕':'当前空幕'} <span>${tapes.length} 件</span></h3></div>${tapes.map(item => gearRow(item, '空幕', tape)).join('') || '<p class="rb-muted">当前未装备空幕</p>'}<div class="rb-section-heading"><h3>${plan?'方案驱动':'当前驱动'} <span>${drives.length} 块</span></h3></div>${driveScores.map(entry => gearRow(entry.item, '驱动', entry)).join('') || '<p class="rb-muted">当前未装备驱动块</p>'}</section><details class="rb-scoring-help"><summary>评分规则与等级</summary><p>使用角色图鉴推荐：P1～P5 权重为 0.40 / 0.55 / 0.70 / 0.85 / 1.00，未推荐为 0。空幕主属性占 60%、副属性占 40%；驱动只按四条副属性的推荐适配度评分。品质系数：金色 ×1.00、紫色 ×0.80、蓝色 ×0.60，空幕主属性分、副属性分和驱动分分别乘对应品质系数。</p><p>驱动盘面分 = 各驱动评分 × 占格数之和 ÷ 盘面可用格数，空槽计 0 分。总分 = 空幕分 + 驱动盘面分，满分 200；配装毕业率 = 总分 ÷ 200。ACE ≥ 95%、S ≥ 85%、A ≥ 70%、B ≥ 50%，其余 C。</p><p>品质比例取自同词条的实际数值：空幕主属性、副属性以及同形驱动副属性，紫色约为金色的 80%，蓝色约为 60%。强化等级不另外加分，套装和实战收益不计分。推荐或读取数据不完整时显示待评分。毕业配装按可用背包装备搜索合法搭配，保存后可在游戏配装中预览并执行。</p></details>${!overall ? '<p class="rb-muted">总评暂不可用：请确认角色推荐、装备属性和盘面位置已完整读取。</p>' : ''}</section>`;
  }

  function paint() {
    const panel = root(); if (!panel) return;
    const rosterScrollLeft = panel.querySelector('.rb-roster')?.scrollLeft || 0;
    panel.classList.add("rb-workspace");
    const owned = roles(), visible=tab==='game'?owned.filter(role=>Object.prototype.hasOwnProperty.call(snapshot?.saved_plans||{},role.id)):owned, filtered = visible.filter(role => nameKey(role.name).includes(nameKey(query)) || nameKey(role.data?.id).includes(nameKey(query)));
    if (!filtered.some(role => role.id === selectedRoleId) && !(loading && selectedRoleId)) { clearCalculation();selectedRoleId = filtered[0]?.id || ""; }
    const selected = filtered.find(role => role.id === selectedRoleId);
    panel.innerHTML = `<header class="rb-header"><h1 id="userRoleBuildPlusTitle">配装</h1><nav class="user-role-build-tabs rb-tabs" aria-label="角色配装功能"><button type="button" data-role-build-tab="calculate" aria-pressed="${tab === 'calculate'}">计算配装</button><button type="button" data-role-build-tab="game" aria-pressed="${tab === 'game'}">游戏配装</button></nav><div class="rb-account"><span class="rb-status-dot${snapshot?.ready ? ' is-ready' : ''}"></span>${esc(snapshot?.account_uid ? 'UID ' + snapshot.account_uid : '尚未读取 UID')}<small>角色配装 PLUS</small><button type="button" class="rb-button" data-role-unlock-all ${!snapshot?.account_uid||!roleLocks().size||loading||actionBusy||job?.running?'disabled':''}>解锁全部</button></div></header><div class="rb-toolbar"><label class="rb-search"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg><input type="search" data-role-search aria-label="${tab==='game'?'搜索已保存方案的角色':'搜索已读取的持有角色'}" placeholder="${tab==='game'?'搜索已保存方案的角色':'搜索已读取的持有角色'}" value="${esc(query)}"></label><button class="rb-button" type="button" data-role-refresh ${loading ? 'disabled' : ''}>${loading ? '载入中…' : '刷新快照'}</button><button class="rb-button rb-button-primary" type="button" data-go-read ${nativeReadBusy || !window.KekeVision?.isRiskModeEnabled()?'disabled':''} title="${window.KekeVision?.isRiskModeEnabled()?'读取当前游戏账号数据':'请先在读取数据中启用风险模式'}">${nativeReadBusy?'DLL读取中…':'读取游戏数据'}</button></div>${globalNotice?`<p class="rb-action-notice rb-global-notice" role="status">${esc(globalNotice)}</p>`:''}<div class="rb-roster-heading"><span>${tab==='game'?'已保存方案':'已持有角色'} <b>${visible.length}</b></span><small>${tab==='game'?'仅显示当前账号已保存方案的角色':'仅显示当前账号游戏快照中的角色'}</small></div><div class="rb-roster" aria-label="${tab==='game'?'已保存方案的角色':'已读取的持有角色'}">${filtered.map(role => {
      const saved=snapshot?.saved_plans?.[role.id]; const result = assessment(role,tab==='game'?(saved?.valid?saved:null):(role.id===selectedRoleId?proposal:null)).overall;
      return `<button type="button" class="rb-role-card" data-cassette-score-role="${esc(role.id)}" aria-pressed="${role.id === selectedRoleId}">${avatar(role)}${roleLocks().has(role.id)?`<span class="rb-role-lock-badge" title="当前角色装备已锁定" aria-label="装备已锁定">${lockIcon()}</span>`:''}<span><b>${esc(role.name)}</b><small>${tab==='game'&&!saved?.valid?'方案需重新计算':result ? '总分 ' + score(result.total) + ' · ' + result.grade : role.cassette ? '待评分' : '推荐待配置'}</small></span><i aria-hidden="true"></i></button>`;
    }).join('') || `<div class="rb-empty">${loading ? '正在载入当前账号角色…' : !snapshot?.ready ? esc(message || snapshot?.message || '请先读取游戏数据，载入已持有角色。') : tab==='game' ? (visible.length?'没有匹配的已保存方案':'暂无已保存方案，请先在计算配装中计算并保存。') : owned.length ? '没有匹配的已持有角色' : '该快照未包含持有角色，请重新读取游戏数据。'}</div>`}</div>${selected ? details(selected) : ''}<footer class="rb-source">${snapshot?.ready ? `已保存快照 · ${esc(snapshot.saved_at || '时间未记录')} · ${esc(snapshot.equipment_count ?? snapshot.items?.length ?? 0)} 件装备` : esc(message || '角色和装备均使用本机账号读取快照')}</footer>`;
    const roster = panel.querySelector('.rb-roster');
    if (roster) roster.scrollLeft = rosterScrollLeft;
    panel.querySelector('[data-role-unlock-all]')?.addEventListener('click',unlockAllRoles);
    panel.querySelectorAll("[data-role-build-tab]").forEach(button => button.onclick = () => { operationPreview=null;globalNotice='';if(!job?.running)job=null;actionMessage='';tab = button.dataset.roleBuildTab; paint(); });
    panel.querySelectorAll("[data-cassette-score-role]").forEach(button => button.onclick = () => { clearCalculation();globalNotice='';selectedRoleId = button.dataset.cassetteScoreRole; paint(); });
    panel.querySelector('[data-build-exclude]')?.addEventListener('change',event=>{excludeOthers=event.target.checked;clearCalculation();paint();});
    panel.querySelector('[data-role-lock]')?.addEventListener('click',()=>selected&&toggleRoleLock(selected));
    panel.querySelector('[data-build-calculate]')?.addEventListener('click',()=>calculate(selected));
    panel.querySelector('[data-build-stop]')?.addEventListener('click',()=>{clearCalculation();actionMessage='计算已停止';paint();});
    for(const action of ['save','equip','unequip','execute','cancel'])panel.querySelector(`[data-build-${action}]`)?.addEventListener('click',()=>perform(action,selected));
    panel.querySelector('[data-build-delete]')?.addEventListener('click',()=>{if(selected)openDeleteConfirmation(selected);});
    panel.querySelector('[data-build-dismiss]')?.addEventListener('click',()=>{operationPreview=null;paint();});
    panel.querySelector('[data-build-status]')?.addEventListener('click',()=>pollOperation(job.account));
    panel.querySelector("[data-role-search]")?.addEventListener("input", event => {
      query = event.target.value; const cursor = event.target.selectionStart; paint();
      const input = panel.querySelector("[data-role-search]"); input.focus(); input.setSelectionRange(cursor, cursor);
    });
    panel.querySelector("[data-role-refresh]")?.addEventListener("click", () => load());
    panel.querySelector("[data-go-read]")?.addEventListener("click", async () => {
      if(nativeReadBusy || !window.KekeVision?.isRiskModeEnabled())return;
      nativeReadBusy=true;globalNotice='正在启动 DLL 原生读取…';paint();
      try {
        if(!window.KekeVision?.startNativeRead)throw Error('DLL 原生读取入口不可用，请重启应用后重试。');
        await window.KekeVision.startNativeRead(account);
        globalNotice='DLL 原生读取已启动，完成后会自动刷新角色与装备快照。';paint();
      } catch(error) {
        nativeReadBusy=false;globalNotice=error.message;paint();
      }
    });
  }

  async function load() {
    const previousUid=snapshot?.account_uid;clearCalculation();const current = ++generation; loading = true; snapshot = null; message = ""; globalNotice='';paint();
    try {
      const status = await request("/inventory/status");
      window.KekeVision?.syncRiskState(status.native_risk);
      if (current !== generation) return;
      accountProfiles = status.account_profiles || [];
      account = status.config?.native_account || ""; const nativeProfile = accountProfiles.find(profile => profile.account === account); if (!nativeProfile?.uid) throw Error("尚无最近一次内存读取确认的游戏 UID。请先读取当前游戏账号的数据。");
      if (status.job?.running || status.native_operation) throw Error("正在读取或操作装备，请完成后刷新快照。");
      const data = await request("/inventory/equipment/inspect", { account }, status.token);
      if (current !== generation) return;
      if(previousUid&&data.account_uid&&String(previousUid)!==String(data.account_uid))selectedRoleId='';
      snapshot = data;
    } catch (error) { if (current !== generation) return; snapshot = null; message = error.message; }
    if (current === generation) { loading = false; paint(); }
  }

  window.addEventListener?.("storage",event=>{if(event.key===locksKey()){clearCalculation();if(!root()?.hidden)paint();}});
  window.addEventListener?.("keke-native-risk-changed", () => { if (!root()?.hidden) paint(); });
  window.addEventListener?.('keke-account-deleted',event=>{
    if(event.detail?.account!==account)return;
    clearCalculation();++generation;snapshot=null;account='';selectedRoleId='';operationPreview=null;globalNotice='账号数据已删除';
    if(!root()?.hidden)load();
  });
  window.addEventListener?.("keke-inventory-synced", () => { nativeReadBusy=false;if (!root()?.hidden) load(); });
  return {
    render() { query = ""; account = ""; load(); },
    setSnapshot(value) { clearCalculation();++generation; loading = false; message = ""; snapshot = value; account = value?.account || ""; paint(); }
  };
})();
