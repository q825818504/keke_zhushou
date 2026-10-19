/* Offline role build from explicitly selected saved DLL or OCR inventory data. */
window.KekeRoleBuildStandard = (() => {
  let tab = "calculate", snapshot = null, account = "", selectedSource = "", sourceOptions = [], accountProfiles = [], inventoryToken = "", message = "", generation = 0, selectedRoleId = "", query = "", loading = false;
  let worker = null, calculating = false, proposal = null, excludeOthers = true, actionBusy = false, actionMessage = '', operationPreview = null, job = null;
  let pollTimer=null, pollGeneration=0, globalNotice='';
  let pendingDeleteRole=null, deleteDialog=null;
  let calculationSnapshot=null;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const root = () => document.querySelector("#userRoleBuildRoute");
  const score = value => Number.isFinite(value) ? value.toFixed(1) : "—";
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
    const library = typeof characterData === "undefined" ? [] : Object.entries(characterData);
    return library.filter(([, data]) => data?.id && String(data.id) !== 'tajiduo').map(([name, data]) => {
      const active = data.knowledge?.terminal?.layout?.active_slots || data.knowledge?.recommended?.cassette?.terminal?.layout?.active_slots || [];
      const board = active.filter(slot => Number.isInteger(slot?.row) && Number.isInteger(slot?.column)).map(slot => [slot.row, slot.column]);
      return { id: String(data.id), name, data, native: { character_id: String(data.id), board }, cassette: data.knowledge?.recommended?.cassette };
    });
  }

  const SOURCE_SHAPES = {
    H_2:[[0,0],[0,1]], V_2:[[0,0],[1,0]], H_3:[[0,0],[0,1],[0,2]], V_3:[[0,0],[1,0],[2,0]],
    L_3_TL:[[0,0],[0,1],[1,0]], L_3_TR:[[0,0],[0,1],[1,1]], L_3_BL:[[0,0],[1,0],[1,1]], L_3_BR:[[0,1],[1,0],[1,1]],
    H_4:[[0,0],[0,1],[0,2],[0,3]], V_4:[[0,0],[1,0],[2,0],[3,0]],
    Trap_4_H:[[0,1],[0,2],[1,0],[1,1]], Trap_4_V:[[0,1],[1,0],[1,1],[2,0]]
  };
  const SHAPE_ALIASES = {hen2:'H_2',hen3:'H_3',hen4:'H_4',heng2:'H_2',heng3:'H_3',heng4:'H_4',shu2:'V_2',shu3:'V_3',shu4:'V_4',z3:'Trap_4_H',z4:'Trap_4_V',zhijiao1:'L_3_BL',zhijiao2:'L_3_TL',zhijiao3:'L_3_TR',zhijiao4:'L_3_BR'};
  const SOLVER_SHAPE_IDS = {H_2:'cell2_style1_1',V_2:'cell2_style2_1',H_3:'cell3_style1_1',V_3:'cell3_style2_1',L_3_TL:'cell3_style3_1',L_3_TR:'cell3_style4_1',L_3_BL:'cell3_style5_1',L_3_BR:'cell3_style6_1',H_4:'cell4_style1_1',V_4:'cell4_style2_1',Trap_4_H:'cell4_style5_1',Trap_4_V:'cell4_style6_1'};
  const NATIVE_ORIGINS={hen3:[0,-1],hen4:[0,-1],shu3:[-1,0],shu4:[-1,0],z3:[0,-1],z4:[-1,0],zhijiao4:[0,-1]};
  function sourceShape(value) {
    const key=String(value||'').replace(/^EquipmentGeometry_/i,'');
    return SOURCE_SHAPES[key]?key:(SHAPE_ALIASES[key.replace(/[^a-z0-9]/gi,'').toLowerCase()]||key);
  }
  const solverShapeId = item => SOLVER_SHAPE_IDS[sourceShape(item?.shape||item?.shape_id)]||'';
  function attributes(value) {
    const normalize=(name,raw)=>{
      if(name&&typeof name==='object')return {...name,name:name.name||name.names?.zh_cn||name.names?.zh_CN||name.property_id||name.id};
      const text=String(name||'');
      const val=raw&&typeof raw==='object'?Number(raw.value):Number(raw);
      const isPercent=/[%％]|百分比/.test(text)||raw?.is_percent===true||raw?.percent===true;
      // OCR maps store displayed percentage points; DLL arrays store fractions.
      return {name:text,value:Number.isFinite(val)?(isPercent?val/100:val):undefined,is_percent:isPercent};
    };
    if(Array.isArray(value))return value.map(row=>Array.isArray(row)?normalize(row[0],row[1]):normalize(row,undefined));
    if(value&&typeof value==='object')return Object.entries(value).map(([name,raw])=>normalize(name,raw));
    if(typeof value==='string'&&value.trim())return [normalize(value.trim(),undefined)];
    return [];
  }
  function normalizeItem(record) {
    const parser=record.parser_result||{};
    const legacy=sourceShape(record.shape||parser.shape_id);
    const shape=Object.entries(SOURCE_SHAPES).find(([id,cells])=>id===legacy)?.[1];
    const main=record.main_attributes||record.inferred_main_attributes||parser.main_stats;
    const subs=record.sub_attributes||parser.sub_stats;
    const setName=record.name||parser.set_name||'';
    const row={id:record.instance_id,category:record.category,name:setName,shape:record.shape||parser.shape_id,
      cells:shape,rarity:record.rarity_candidate||record.rarity||parser.quality,level:record.level,main_stats:attributes(main),sub_stats:attributes(subs),
      owner:record.is_equipped===false?null:record.equipped_character_id||null,placement:null,locked:record.is_locked,discarded:record.is_discarded,label:record.category==='tape'?'空幕':'驱动'};
    if(record.placement){
      const origin=NATIVE_ORIGINS[String(record.shape||'').replace(/^EquipmentGeometry_/i,'').toLowerCase()]||[0,0];
      row.placement={row:record.placement.row+origin[0],column:record.placement.column+origin[1]};
    }
    if(record.category==='tape'){
      const catalog=(window.skyCurtainKnowledge?.items||[]).find(item=>nameKey(item.name)===nameKey(setName));
      row.cassette_id=catalog?.id;
    }
    return row;
  }
  function plansKey(accountKey=account,sourceKey=selectedSource,savedAt=snapshot?.saved_at) { return `keke-role-build-v16:${encodeURIComponent(accountKey)}:${encodeURIComponent(sourceKey)}${sourceKey==='native'?':'+encodeURIComponent(savedAt||'unknown'):''}`; }
  function loadPlans(accountKey=account,sourceKey=selectedSource,savedAt) {
    try { const value=JSON.parse(localStorage.getItem(plansKey(accountKey,sourceKey,savedAt))||'{}');return value&&typeof value==='object'?value:{}; }
    catch { return {}; }
  }
  function savePlans() { if(account&&selectedSource)localStorage.setItem(plansKey(),JSON.stringify(snapshot?.saved_plans||{})); }

  function freezePlanItems(plan,context){
    const ids=new Set([plan.core,...(plan.modules||[]).map(row=>row.id)]);
    return {account_uid:context.account_uid,saved_at:context.saved_at,
      items:JSON.parse(JSON.stringify((context.items||[]).filter(item=>ids.has(item.id))))};
  }
  function refreshSavedView(){
    const context=calculationSnapshot||snapshot||{items:[],account,source_id:selectedSource};
    const plans=loadPlans(account,selectedSource,context.saved_at),items=new Map();let migrated=false;
    for(const plan of Object.values(plans)){
      // Older plans stored only IDs. Hydrate once from the calculation cache;
      // game view itself never fetches or substitutes current inventory data.
      if(!plan.saved_snapshot){plan.saved_snapshot=freezePlanItems(plan,context);migrated=true;}
      const byId=new Set((plan.saved_snapshot.items||[]).map(item=>item.id));
      if(!byId.has(plan.core)||!Array.isArray(plan.modules)||plan.modules.some(row=>!byId.has(row.id))){
        plan.valid=false;plan.reason='保存方案的装备资料不完整，请返回计算配装重新计算并保存';
      }
      for(const item of plan.saved_snapshot.items||[])items.set(item.id,item);
    }
    snapshot={...context,items:[...items.values()],saved_plans:plans,ready:Object.keys(plans).length>0};
    if(migrated)savePlans();
    loading=false;message='这里只显示本机已保存方案；请到计算配装创建或更新方案。';
  }
  function switchTab(next){
    if(next===tab)return;
    clearCalculation();operationPreview=null;globalNotice='';actionMessage='';++generation;
    if(next==='game'){
      calculationSnapshot=snapshot;tab='game';
      try{refreshSavedView();}catch(error){message=error.message;snapshot={items:[],saved_plans:{}};loading=false;}
      paint();
    }else{tab='calculate';snapshot=calculationSnapshot;calculationSnapshot=null;load(account,selectedSource);}
  }

  const DRIVER_ASSET_BOUNDS = {"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type2-h.webp":[55,89,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type2-v.webp":[89,54,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-h.webp":[30,93,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-lb.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-lt.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-rb.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-l-rt.webp":[55,55,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type3-v.webp":[92,33,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-h.webp":[18,92,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-v.webp":[97,19,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-z-h.webp":[34,63,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/blue/type4-z-v.webp":[63,33,131,192],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type2-h.webp":[55,88,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type2-v.webp":[89,53,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-h.webp":[30,92,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-lb.webp":[54,54,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-lt.webp":[54,54,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-rb.webp":[55,53,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-l-rt.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type3-v.webp":[92,32,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-h.webp":[18,91,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-v.webp":[97,18,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-z-h.webp":[34,62,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/gold/type4-z-v.webp":[63,32,131,192],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_baoji.webp":[14,14,100,100],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_baojishanghai.webp":[14,14,100,100],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_fangyu.webp":[32,28,64,82],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_gongji.webp":[23,29,82,71],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_kangxing.webp":[18,25,92,78],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/icon_attri_shengming.webp":[16,22,96,84],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/Icon_attri_strength_qingxian.webp":[18,34,92,60],"data/resources/encyclopedia/driver_blocks/site/images/drivers/icons/Icon_attri_surpass.webp":[28,21,72,87],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type2-h.webp":[55,89,144,77],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type2-v.webp":[89,54,77,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-h.webp":[30,93,193,70],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-lb.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-lt.webp":[54,55,145,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-rb.webp":[55,54,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-l-rt.webp":[55,55,144,144],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type3-v.webp":[92,33,70,191],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-h.webp":[18,92,220,61],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-v.webp":[97,19,60,217],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-z-h.webp":[34,63,192,131],"data/resources/encyclopedia/driver_blocks/site/images/drivers/purple/type4-z-v.webp":[63,33,131,192]};
  const scorer = () => window.KekeCassetteScoring;
  function driveCatalog(item) {
    const shapeId=solverShapeId(item);
    return (window.driverBlockKnowledge?.items || []).find(row => shapeId ? row.id === shapeId : row.source_data?.type_geometry?.replace('EquipmentGeometry_', '') === String(item.shape).replace('EquipmentGeometry_', ''));
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
    const saved=snapshot?.saved_plans?.[role.id];
    const chosen=tab==='calculate'?proposal:saved?.valid?saved:null;
    const preview=operationPreview;
    const operationStatus=job?`<div class="rb-operation-status" role="status">${esc(job.message)}${job.completed?` · 已执行 ${esc(job.completed)} 个操作`:''}${job.running?'<button type="button" class="rb-button" data-build-cancel>停止后续输入</button>':''}${job.error?`<p>${esc(job.error)}</p>`:''}</div>`:'';
    const aliasControl=tab==='game'?`<label class="rb-alias-field">游戏内角色名（可选）<input type="text" maxlength="40" data-role-alias value="${esc(localStorage.getItem(`keke-role-alias:${role.id}`)||'')}" placeholder="OCR 名称不同于图鉴时填写"></label>`:'';
    return `<section class="rb-actions"><div class="rb-section-heading"><h3>${tab==='calculate'?'毕业配装计算':'保存方案与游戏内装配'}</h3></div>${tab==='calculate'?`<label class="rb-exclude"><input type="checkbox" data-build-exclude ${excludeOthers?'checked':''} ${disabled?'disabled':''}>不使用其他角色已装备的驱动与空幕<span>未确认装备归属的条目仍会进入候选</span></label><div class="rb-action-buttons"><button type="button" class="rb-button rb-button-primary" data-build-calculate ${disabled||!snapshot?.ready?'disabled':''}>${calculating?'正在搜索合法搭配…':'计算毕业配装'}</button>${calculating?'<button type="button" class="rb-button" data-build-stop>停止计算</button>':''}<button type="button" class="rb-button" data-build-save ${disabled||!proposal?'disabled':''}>保存该角色方案</button></div>`:`<div class="rb-action-buttons"><button type="button" class="rb-button rb-button-primary" data-build-equip ${disabled||!saved?.valid?'disabled':''}>自动装配已保存方案</button>${saved?`<button type="button" class="rb-button rb-delete-plan" data-build-delete aria-label="删除${esc(role.name)}的已保存方案" ${disabled?'disabled':''}>删除此方案</button>`:''}</div>${aliasControl}${!saved?'<p class="rb-muted">请先在计算配装中计算并保存该角色方案。</p>':!saved.valid?`<p class="rb-action-notice">${esc(saved.reason)}。请重新计算并保存。</p>`:''}`}${chosen?planView(role,chosen,tab==='game'):''}${preview?`<div class="rb-operation-preview"><h3>游戏内逐步装配确认</h3><p>将使用选中的离线快照筛选 ${preview.total} 件装备，再拖放到角色盘面。执行期间请保持异环在前台。</p><ol>${preview.items.map(item=>`<li>${esc(item.label)} · ${esc(item.name)}${item.shape?` · ${esc(item.shape)}`:''}</li>`).join('')}</ol><p class="rb-muted">自动操作开始前有 3 秒切回游戏；每次输入都会核对前台游戏窗口。相同属性的装备可能无法唯一定位，请执行前核对快照数据。</p><button class="rb-button rb-button-primary" type="button" data-build-execute ${disabled?'disabled':''}>确认并开始逐步装配</button><button class="rb-button" type="button" data-build-dismiss ${disabled?'disabled':''}>返回</button></div>`:''}${operationStatus}${actionMessage?`<p class="rb-action-notice" role="status">${esc(actionMessage)}</p>`:''}</section>`;
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
      worker.postMessage({snapshot,characterId:role.id,cassette:role.cassette,excludeOthers,driverCatalog:window.driverBlockKnowledge,tapeCatalog:window.skyCurtainKnowledge});
    }catch(error){calculating=false;actionMessage=error.message;paint();}
  }

  async function perform(action, role) {
    if(actionBusy)return;
    const current=generation, targetAccount=account, targetRole=role.id;
    actionBusy=true;actionMessage='';paint();
    try{
      if(current!==generation||selectedRoleId!==targetRole)throw Error('账号或角色已切换，请重试');
      if(action==='save'){
        if(!proposal)throw Error('请先计算方案');
        const validIds=new Set(snapshot.items.map(item=>item.id));
        if(!validIds.has(proposal.core)||proposal.modules.some(row=>!validIds.has(row.id)))throw Error('方案中的装备已不在当前快照，请重新计算');
        const saved={...proposal,valid:true,saved_at:new Date().toLocaleString('zh-CN'),source_id:selectedSource,source_saved_at:snapshot.saved_at,
          saved_snapshot:freezePlanItems(proposal,snapshot)};
        if(current===generation){snapshot.saved_plans||={};snapshot.saved_plans[role.id]=saved;savePlans();actionMessage='方案已保存在本机，可在游戏配装中逐步装配。';}
      }else if(action==='equip'){
        const saved=snapshot?.saved_plans?.[role.id];
        if(!saved?.valid)throw Error('此角色没有有效的已保存方案');
        const tape=snapshot.items.find(item=>item.id===saved.core);
        const modules=saved.modules.map(row=>({...row,item:snapshot.items.find(item=>item.id===row.id)}));
        if(!tape||modules.some(row=>!row.item))throw Error('当前历史快照中缺少方案装备，请重新计算并保存');
        const shapes=modules.map(row=>driveCatalog(row.item)?.name||sourceShape(row.item.shape)||'形状待核对');
        operationPreview={operation:'assembly',total:modules.length+1,role_id:role.id,core:saved.core,
          modules:saved.modules,items:[{label:'空幕',name:tape.name},...modules.map((row,index)=>({label:'驱动',name:row.item.name,shape:shapes[index]}))]};
      }else if(action==='delete'){
        if(!snapshot?.saved_plans?.[role.id])throw Error('该角色没有已保存方案，请刷新快照');
        if(current===generation&&selectedRoleId===targetRole){delete snapshot.saved_plans[role.id];savePlans();proposal=null;operationPreview=null;globalNotice=`${role.name} 的已保存方案已删除`;}
      }else if(action==='execute'){
        if(!operationPreview||!snapshot?.ready||!selectedSource)throw Error('请重新生成游戏装配预览');
        const modules=operationPreview.modules.map(row=>({id:row.id,row:row.row,column:row.column,
          shape_id:solverShapeId(snapshot.items.find(item=>item.id===row.id))}));
        job=await request('/inventory/ui-assembly/start',{account:targetAccount,source:selectedSource,role_id:role.id,
          role_name:role.name,role_alias:localStorage.getItem(`keke-role-alias:${role.id}`)||'',board:role.native.board,
          core:operationPreview.core,modules,source_saved_at:snapshot.saved_at},inventoryToken);
        operationPreview=null;pollOperation(targetAccount,selectedSource);
      }else if(action==='cancel'){
        job=await request('/inventory/ui-assembly/cancel',{},inventoryToken);
        pollOperation(targetAccount,selectedSource);
      }
    }catch(error){actionMessage=error.message;}
    finally{actionBusy=false;paint();}
  }

  async function pollOperation(targetAccount,targetSource,failures=0) {
    clearTimeout(pollTimer);const currentPoll=++pollGeneration;
    try{
      const current=await request('/inventory/ui-assembly/status');
      if(currentPoll!==pollGeneration)return;
      if(!current||current.account!==targetAccount||current.source!==targetSource)throw Error('操作状态已变化，请刷新后核对');
      job=current;paint();
      if(current.running)pollTimer=setTimeout(()=>pollOperation(targetAccount,targetSource),800);
    }catch(error){
      if(currentPoll!==pollGeneration)return;
      job={...job,account:targetAccount,source:targetSource,running:true,unknown:true,message:'状态查询暂不可用：'+error.message};paint();
      if(failures<4)pollTimer=setTimeout(()=>pollOperation(targetAccount,targetSource,failures+1),Math.min(1000*2**failures,5000));
    }
  }

  function details(role) {
    const saved=snapshot?.saved_plans?.[role.id];
    const deleteButton='';
    if(tab==='game'&&!saved?.valid)return `<section class="rb-detail"><header class="rb-detail-heading"><div class="rb-selected-role">${avatar(role)}<h2>${esc(role.name)}</h2></div><div class="rb-detail-side">${deleteButton}</div></header>${actions(role)}</section>`;
    const plan=tab==='calculate'?proposal:saved;
    const { items, tapes, drives, tape, driveScores, overall } = assessment(role,plan);
    return `<section class="rb-detail"><header class="rb-detail-heading"><div class="rb-selected-role">${avatar(role)}<div><h2>${esc(role.name)}</h2><span>${plan?(tab==='game'?'已保存方案':'计算结果预览'):'当前游戏快照'} · 空幕 ${tapes.length} / 驱动 ${drives.length}</span></div></div><div class="rb-detail-side"><div class="rb-build-metrics"><div><span>空幕毕业率</span><b>${tapes.length ? score(tape?.score) : '0.0'}<small>%</small></b></div><div><span>配装毕业率</span><b>${score(overall?.graduation)}<small>%</small></b></div><div class="rb-score-total"><span>总分</span><b>${score(overall?.total)}</b><small>/ 200</small>${gradeBadge(overall?.graduation)}</div></div>${deleteButton}</div></header>${actions(role)}<div class="rb-loadout-overview"><section class="rb-board-section"><h3>${plan?'方案驱动盘面':'当前驱动盘面'}</h3>${board(role, drives)}<p>${overall ? `已填 ${overall.filled} / ${overall.capacity} 格 · 驱动盘面 ${score(overall.driveScore)} / 100` : '读取快照中的摆放位置'}</p></section>${summary(items,plan?'方案装备属性汇总':'当前装备属性汇总')}</div><section class="rb-current-gear"><div class="rb-section-heading"><h3>${plan?'方案空幕':'当前空幕'} <span>${tapes.length} 件</span></h3></div>${tapes.map(item => gearRow(item, '空幕', tape)).join('') || '<p class="rb-muted">当前未装备空幕</p>'}<div class="rb-section-heading"><h3>${plan?'方案驱动':'当前驱动'} <span>${drives.length} 块</span></h3></div>${driveScores.map(entry => gearRow(entry.item, '驱动', entry)).join('') || '<p class="rb-muted">当前未装备驱动块</p>'}</section><details class="rb-scoring-help"><summary>评分规则与等级</summary><p>使用角色图鉴推荐：P1～P5 权重为 0.40 / 0.55 / 0.70 / 0.85 / 1.00，未推荐为 0。空幕主属性占 60%、副属性占 40%；驱动只按四条副属性的推荐适配度评分。品质系数：金色 ×1.00、紫色 ×0.80、蓝色 ×0.60，空幕主属性分、副属性分和驱动分分别乘对应品质系数。</p><p>驱动盘面分 = 各驱动评分 × 占格数之和 ÷ 盘面可用格数，空槽计 0 分。总分 = 空幕分 + 驱动盘面分，满分 200；配装毕业率 = 总分 ÷ 200。ACE ≥ 95%、S ≥ 85%、A ≥ 70%、B ≥ 50%，其余 C。</p><p>品质比例取自同词条的实际数值：空幕主属性、副属性以及同形驱动副属性，紫色约为金色的 80%，蓝色约为 60%。强化等级不另外加分，套装和实战收益不计分。推荐或读取数据不完整时显示待评分。毕业配装按可用背包装备搜索合法搭配，保存后可在游戏配装中预览并执行。</p></details>${!overall ? '<p class="rb-muted">总评暂不可用：请确认角色推荐、装备属性和盘面位置已完整读取。</p>' : ''}</section>`;
  }

  function paint() {
    const panel = root(); if (!panel) return;
    const rosterScrollLeft = panel.querySelector('.rb-roster')?.scrollLeft || 0;
    panel.classList.add("rb-workspace");
    const allRoles=roles(), visible=tab==='game'?allRoles.filter(role=>Object.prototype.hasOwnProperty.call(snapshot?.saved_plans||{},role.id)):allRoles;
    const filtered=visible.filter(role=>nameKey(role.name).includes(nameKey(query))||nameKey(role.id).includes(nameKey(query)));
    if(!filtered.some(role=>role.id===selectedRoleId)&&!(loading&&selectedRoleId)){clearCalculation();selectedRoleId=filtered[0]?.id||'';}
    const selected=filtered.find(role=>role.id===selectedRoleId);
    const accountOptions=accountProfiles.map(profile=>`<option value="${esc(profile.account)}" ${profile.account===account?'selected':''}>${profile.uid?`UID ${esc(profile.uid)}`:'未绑定 UID'} · ${esc(profile.note||profile.account)}</option>`).join('');
    const sourceOptionsMarkup=sourceOptions.map(source=>`<option value="${esc(source.id)}" ${source.id===selectedSource?'selected':''}>${esc(source.id==='native'?'DLL 离线快照':source.mode||source.label||'OCR')} · ${esc(source.saved_at||'时间未记录')} · ${esc(source.count||0)} 件${source.complete?' · 完整':' · 部分数据'}</option>`).join('');
    panel.innerHTML=`<header class="rb-header"><h1 id="userRoleBuildTitle">配装</h1><nav class="user-role-build-tabs rb-tabs" aria-label="角色配装功能"><button type="button" data-role-build-tab="calculate" ${actionBusy||job?.running?'disabled':''} aria-pressed="${tab==='calculate'}">计算配装</button><button type="button" data-role-build-tab="game" ${loading||actionBusy||job?.running?'disabled':''} aria-pressed="${tab==='game'}">游戏配装</button></nav><div class="rb-account"><span class="rb-status-dot${snapshot?.ready?' is-ready':''}"></span>${esc(snapshot?.account_uid?`UID ${snapshot.account_uid}`:'UID 可选')}<small>离线快照计算</small></div></header>`+
      `${tab==='calculate'?`<div class="rb-data-selectors"><label><span>账号 / UID（可选）</span><select data-account-select aria-label="选择账号 UID" ${loading?'disabled':''}>${accountOptions||`<option value="${esc(account)}">${esc(account||'默认账号')}</option>`}</select><small>可选已读取账号；UID 不会作为计算必填条件。</small></label><label><span>读取时间</span><select data-source-select aria-label="选择历史装备快照" ${loading||!sourceOptions.length?'disabled':''}>${sourceOptionsMarkup||'<option value="">该账号暂无已保存装备数据</option>'}</select><small>每个时间点独立保存方案。</small></label></div>`:''}`+
      `<div class="rb-toolbar"><label class="rb-search"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg><input type="search" data-role-search aria-label="搜索角色" placeholder="搜索角色" value="${esc(query)}"></label><button class="rb-button" type="button" data-role-refresh ${loading?'disabled':''}>${loading?'载入中…':tab==='game'?'刷新方案':'刷新快照'}</button>${tab==='calculate'?'<button class="rb-button rb-button-primary" type="button" data-go-read>读取数据</button>':''}</div>`+
      `${globalNotice?`<p class="rb-action-notice rb-global-notice" role="status">${esc(globalNotice)}</p>`:''}${tab==='calculate'&&snapshot?.ready&&!snapshot.complete?'<p class="rb-action-notice" role="status">当前快照数据不完整，计算结果仅基于已保存的装备。</p>':''}`+
      `<div class="rb-roster-heading"><span>${tab==='game'?'已保存方案':'角色列表'} <b>${visible.length}</b></span><small>${tab==='game'?'仅显示当前数据批次中保存过方案的角色':'图鉴全部角色（不含塔吉多）'}</small></div><div class="rb-roster" aria-label="${tab==='game'?'已保存方案的角色':'角色列表'}">${filtered.map(role=>{const saved=snapshot?.saved_plans?.[role.id];const result=assessment(role,tab==='game'?(saved?.valid?saved:null):(role.id===selectedRoleId?proposal:null)).overall;return `<button type="button" class="rb-role-card" data-cassette-score-role="${esc(role.id)}" aria-pressed="${role.id===selectedRoleId}">${avatar(role)}<span><b>${esc(role.name)}</b><small>${tab==='game'&&!saved?.valid?'方案需重新计算':result?'总分 '+score(result.total)+' · '+result.grade:role.cassette?'待评分':'推荐待配置'}</small></span><i aria-hidden="true"></i></button>`;}).join('')||`<div class="rb-empty">${loading?'正在载入角色数据…':tab==='game'?(visible.length?'没有匹配的已保存方案':'此账号与读取时间暂无已保存方案。请先在计算配装中保存。'):allRoles.length?'没有匹配的角色':'图鉴中暂无可配装角色。'}</div>`}</div>${selected?details(selected):''}`+
      `<footer class="rb-source">${tab==='game'?'仅展示本机已保存方案及保存时的装备资料':snapshot?.ready?`所选读取时间 · ${esc(snapshot.saved_at||'时间未记录')} · ${esc(snapshot.equipment_count??snapshot.items?.length??0)} 件装备 · ${snapshot.complete?'识别完整':'识别不完整'}`:esc(message||'选择账号与读取时间后载入已保存的装备快照。')}</footer>`;
    const roster=panel.querySelector('.rb-roster');if(roster)roster.scrollLeft=rosterScrollLeft;
    panel.querySelectorAll('[data-role-build-tab]').forEach(button=>button.onclick=()=>switchTab(button.dataset.roleBuildTab));
    panel.querySelectorAll('[data-cassette-score-role]').forEach(button=>button.onclick=()=>{clearCalculation();globalNotice='';selectedRoleId=button.dataset.cassetteScoreRole;paint();});
    panel.querySelector('[data-account-select]')?.addEventListener('change',event=>load(event.target.value,''));
    panel.querySelector('[data-source-select]')?.addEventListener('change',event=>load(account,event.target.value));
    panel.querySelector('[data-build-exclude]')?.addEventListener('change',event=>{excludeOthers=event.target.checked;clearCalculation();paint();});
    panel.querySelector('[data-build-calculate]')?.addEventListener('click',()=>selected&&calculate(selected));
    panel.querySelector('[data-build-stop]')?.addEventListener('click',()=>{clearCalculation();actionMessage='计算已停止';paint();});
    for(const action of ['save','equip','execute','cancel'])panel.querySelector(`[data-build-${action}]`)?.addEventListener('click',()=>selected&&perform(action,selected));
    panel.querySelector('[data-build-delete]')?.addEventListener('click',()=>{if(selected)openDeleteConfirmation(selected);});
    panel.querySelector('[data-build-dismiss]')?.addEventListener('click',()=>{operationPreview=null;paint();});
    panel.querySelector('[data-role-alias]')?.addEventListener('change',event=>localStorage.setItem(`keke-role-alias:${selectedRoleId}`,event.target.value.trim()));
    panel.querySelector('[data-role-search]')?.addEventListener('input',event=>{query=event.target.value;const cursor=event.target.selectionStart;paint();const input=panel.querySelector('[data-role-search]');input.focus();input.setSelectionRange(cursor,cursor);});
    panel.querySelector('[data-role-refresh]')?.addEventListener('click',()=>{if(tab==='game'){refreshSavedView();paint();}else load(account,selectedSource);});
    panel.querySelector('[data-go-read]')?.addEventListener('click',()=>window.showUserRoute?.('vision'));
  }

  async function load(targetAccount=account,targetSource=selectedSource) {
    clearCalculation();const current=++generation;loading=true;snapshot=null;message='';globalNotice='';paint();
    try {
      const status=await request('/inventory/status');
      if(current!==generation)return;
      inventoryToken=status.token||'';
      accountProfiles=Array.isArray(status.account_profiles)?status.account_profiles:[];
      const preferred=status.config?.account||status.account_profiles?.[0]?.account||'默认账号';
      account=accountProfiles.some(profile=>profile.account===targetAccount)?targetAccount:(accountProfiles.some(profile=>profile.account===preferred)?preferred:targetAccount||preferred);
      const index=await request(`/inventory/snapshot?account=${encodeURIComponent(account)}&source=none`);
      if(current!==generation)return;
      sourceOptions=(index.sources||[]).filter(source=>source.id==='native'||String(source.id||'').startsWith('ocr:'));
      const selected=sourceOptions.find(source=>source.id===targetSource)||sourceOptions.find(source=>source.complete)||sourceOptions[0];
      selectedSource=selected?.id||'';
      if(!selected){snapshot={ready:false,complete:false,account,account_uid:accountProfiles.find(profile=>profile.account===account)?.uid||null,
        source_id:'',saved_at:null,equipment_count:0,items:[],characters:[],saved_plans:{}};
        message=sourceOptions.length?'请选择一个历史装备快照':'该账号暂无已保存装备数据，请先读取 DLL 数据或进行截图扫描。';
      }else{
        const data=await request(`/inventory/snapshot?account=${encodeURIComponent(account)}&source=${encodeURIComponent(selectedSource)}`);
        if(current!==generation)return;
        const equipment=data.inventory?.equipment||{};
        const rawRecords=Array.isArray(equipment.records)?equipment.records:[];
        const candidates=rawRecords.filter(record=>record&&(record.category==='drive'||record.category==='tape'));
        const invalid=candidates.filter(record=>record.usable_for_calculation===false);
        const repaired=candidates.reduce((sum,record)=>sum+(record.stat_validation?.corrections?.length||0),0);
        const items=candidates.filter(record=>record.usable_for_calculation!==false).map(normalizeItem).filter(item=>item.id);
        if(invalid.length)globalNotice=`${invalid.length} 件装备的属性未通过图鉴核对，暂不参与计算。请在背包中核对原图并修正，或重新识别。`;
        else if(repaired)globalNotice=`已按属性图鉴修正 ${repaired} 处可确认的小数点遗漏；原图、识别原文和修正依据保留在背包数据中。`;
        const characters=data.inventory?.characters?.records||[];
        for(const item of items){
          if(item.owner!=null){
            const character=characters.find(row=>String(row.character_id)===String(item.owner));
            const role=roles().find(row=>row.id===String(item.owner)||character?.name&&nameKey(character.name)===nameKey(row.name));
            // Unknown owners still count as other characters for exclusion.
            if(role)item.owner=role.id;
          }
        }
        const profile=accountProfiles.find(row=>row.account===account);
        const complete=selected.complete===true&&equipment.coverage?.collection_complete===true&&!invalid.length;
        snapshot={ready:true,complete,account,account_uid:data.ocr_batch?.account_uid||data.account_uid||profile?.uid||null,source_id:selectedSource,
          saved_at:equipment.saved_at||selected.saved_at,equipment_count:rawRecords.length,items,characters:roles().map(role=>({character_id:role.id,name:role.name,board:role.native.board})),
          saved_plans:loadPlans(account,selectedSource,equipment.saved_at||selected.saved_at),coverage:equipment.coverage||{}};
        const validIds=new Set(items.map(item=>item.id));
        for(const plan of Object.values(snapshot.saved_plans)){
          if(!validIds.has(plan.core)||!Array.isArray(plan.modules)||plan.modules.some(row=>!validIds.has(row.id))){
            plan.valid=false;plan.reason='方案装备缺失或属性未通过图鉴核对，请修正数据后重新计算';
          }
        }
        if(!items.length)message='该快照没有可用于计算的空幕或驱动。';
      }
    }catch(error){if(current!==generation)return;snapshot={ready:false,complete:false,account,items:[],characters:[],saved_plans:{}};message=error.message;}
    if(current===generation){loading=false;paint();}
  }

  window.addEventListener?.('keke-account-deleted',event=>{
    if(event.detail?.account!==account)return;
    clearCalculation();++generation;snapshot=null;account='';selectedSource='';sourceOptions=[];selectedRoleId='';operationPreview=null;globalNotice='账号数据已删除';
    if(!root()?.hidden)load();
  });
  window.addEventListener?.('keke-source-deleted',event=>{
    if(event.detail?.account===account&&event.detail?.source===selectedSource&&!root()?.hidden){selectedSource='';load(account,'');}
  });
  window.addEventListener?.('keke-inventory-synced',()=>{if(!root()?.hidden){if(tab==='game'){refreshSavedView();paint();}else load(account,selectedSource);}});
  return {
    render() { query='';tab='calculate';load(account,selectedSource); },
    refresh() { load(account,selectedSource); }
  };
})();
