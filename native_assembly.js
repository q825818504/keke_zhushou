/* Independent native assembly UI, sharing the existing DriveLayoutSolver engine. */
window.KekeAssembly=(()=>{
 const planner=window.NativeAssemblyPlanner;
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const shapeOf=planner.shapeOf;
 let character='',core='keep',slots=[],placementMode='auto';
 const owner=(item,info)=>item.owner?(info.characters.find(c=>c.character_id===item.owner)?.name||item.owner):'背包';
 const describe=(item,info)=>`${item.label} · ${item.name} · +${item.level??'?'} · ${item.category==='tape'?'空幕':shapeOf(item)?.label||'未知形状'} · ${owner(item,info)}`;
 const stats=item=>[...(item.main_stats||[]),...(item.sub_stats||[])].map(s=>`${s.names?.zh_cn||s.property_id} ${Number.isFinite(s.value)?Number((s.percent?s.value*100:s.value).toFixed(2)):'?'}${s.percent?'%':''}`).join(' · ');
 function chooseCharacter(info,value){
  character=String(value||'');core='keep';placementMode='auto';
  slots=info.items.filter(i=>i.category==='drive'&&i.owner===Number(character)).map(i=>({id:i.id,row:i.placement?.row||1,column:i.placement?.column||1}));
 }
 function inspected(info){chooseCharacter(info,info.characters.some(c=>String(c.character_id)===character)?character:'');}
 function render(info,disabled){
  let html='<p>选择角色最终要保留的空幕和全部驱动。自动摆放复用已有驱动块计算器；未列入清单的现有装备会卸回背包，跨角色转移会单独列出。</p>';
  if(!info)return html+'<p>先检测接口并读取当前装备，再选择背包物品。</p>';
  const tapes=info.items.filter(i=>i.category==='tape');
  html+=`<div class="inventory-settings"><label>装配角色<select id="assemblyCharacter" ${disabled?'disabled':''}><option value="">请选择角色</option>${info.characters.map(c=>`<option value="${c.character_id}" ${String(c.character_id)===character?'selected':''}>${esc(c.name)} · 驱动 ${c.drive} / 空幕 ${c.tape}</option>`).join('')}</select></label><label>目标空幕<select id="assemblyCore" ${disabled||!character?'disabled':''}><option value="keep">保留当前空幕</option><option value="none">卸下空幕，不装空幕</option>${tapes.map(i=>`<option value="${i.id}" ${i.id===core?'selected':''}>${esc(describe(i,info))}</option>`).join('')}</select></label></div>`;
  if(!character)return html;
  html+=`<label>驱动摆放方式<select id="assemblyPlacement" ${disabled?'disabled':''}><option value="auto" ${placementMode==='auto'?'selected':''}>自动计算合法位置</option><option value="manual" ${placementMode==='manual'?'selected':''}>指定行列位置</option></select></label>`;
  const options=info.items.filter(i=>i.category==='drive'&&shapeOf(i));
  html+=`<div class="assembly-slots">${slots.map((slot,index)=>{
   const chosen=info.items.find(i=>i.id===slot.id);
   return `<div class="assembly-slot"><label>驱动 ${index+1}<select data-assembly-slot="${index}" ${disabled?'disabled':''}><option value="">请选择具体驱动实例</option>${options.map(i=>`<option value="${i.id}" ${slot.id===i.id?'selected':''}>${esc(describe(i,info))}</option>`).join('')}</select></label>${placementMode==='manual'?`<div class="assembly-coordinates">${[['row','行'],['column','列']].map(([key,label])=>`<label>${label}<input type="number" min="1" max="5" value="${slot[key]}" data-assembly-coordinate="${key}" data-slot="${index}" ${disabled?'disabled':''}></label>`).join('')}</div>`:''}<button type="button" class="ghost-button" data-assembly-remove="${index}" ${disabled?'disabled':''}>移除</button><p class="inventory-hint">${chosen?esc(stats(chosen)):'尚未选择具体物品'}</p></div>`;
  }).join('')}</div><button class="ghost-button" type="button" data-assembly-add ${disabled||slots.length>=10?'disabled':''}>添加驱动</button>`;
  const selectedCore=info.items.find(i=>i.id===core||(core==='keep'&&i.category==='tape'&&i.owner===Number(character)));
  if(selectedCore)html+=`<p class="inventory-hint">空幕 ${esc(selectedCore.label)}：${esc(stats(selectedCore))}</p>`;
  return html+`<div class="inventory-actions"><button class="ghost-button" data-equipment="assemble-preview" ${disabled||slots.some(s=>!s.id)?'disabled':''}>检查并预览装配方案</button></div>`;
 }
 function bind(panel,info,changed){
  if(panel.querySelector('#assemblyCore'))panel.querySelector('#assemblyCore').value=core;
  panel.querySelector('#assemblyCharacter')?.addEventListener('change',e=>{chooseCharacter(info,e.target.value);changed();});
  panel.querySelector('#assemblyCore')?.addEventListener('change',e=>{core=e.target.value;changed();});
  panel.querySelector('#assemblyPlacement')?.addEventListener('change',e=>{placementMode=e.target.value;changed();});
  panel.querySelector('[data-assembly-add]')?.addEventListener('click',()=>{slots.push({id:'',row:1,column:1});changed();});
  panel.querySelectorAll('[data-assembly-remove]').forEach(b=>b.onclick=()=>{slots.splice(Number(b.dataset.assemblyRemove),1);changed();});
  panel.querySelectorAll('[data-assembly-slot]').forEach(s=>s.onchange=()=>{slots[Number(s.dataset.assemblySlot)].id=s.value;changed();});
  panel.querySelectorAll('[data-assembly-coordinate]').forEach(s=>s.onchange=()=>{slots[Number(s.dataset.slot)][s.dataset.assemblyCoordinate]=Number(s.value);changed();});
 }
 function payload(info){
  if(!character||slots.some(s=>!s.id))throw Error('请选择目标角色及每个驱动实例');
  if(new Set(slots.map(s=>s.id)).size!==slots.length)throw Error('同一件驱动不能重复选择');
  let modules=slots.map(({id,row,column})=>({id,row,column}));
  if(placementMode==='auto'&&slots.length){
   modules=planner.plan(info,Number(character),slots.map(s=>s.id));
  }
  // Backend validates all cells against bundled native geometry independently.
  return {selection_id:info.selection_id,character_id:Number(character),core,modules,placement_mode:'manual'};
 }
 function preview(plan){
  const cells=new Set(plan.layout.cells.map(p=>p.join(':'))),occupied=new Map();
  plan.layout.pieces.forEach((p,index)=>p.cells.forEach(([r,c])=>occupied.set(`${p.row+r}:${p.column+c}`,{label:p.label,index})));
  const grid=Array.from({length:25},(_,i)=>{const key=`${Math.floor(i/5)+1}:${i%5+1}`,p=occupied.get(key);return `<span class="assembly-cell${cells.has(key)?'':' is-disabled'}${p?' is-filled':''}" style="--piece-hue:${p?(p.index*47)%360:0}" title="${esc(p?.label||'')}">${esc(p?.label||'')}</span>`;}).join('');
  return `<div class="equipment-preview"><h3>装配预览 · ${esc(plan.characters.join('、'))}</h3><p>最终 ${plan.drive_count} 块驱动 · 空幕 ${esc(plan.core_label||'无')} · ${plan.total} 步操作${plan.transfers?' · 从其他角色转移 '+plan.transfers+' 件':''}</p><div class="assembly-board" aria-label="目标角色5乘5驱动摆法">${grid}</div>${plan.total?`<ol class="assembly-operations">${plan.items.map(i=>`<li>${i.action==='equip'?'装入':'卸下'} · ${esc(i.character_name)} · ${esc(i.label)} ${esc(i.name)}${i.placement?` · 第${i.placement.row}行${i.placement.column}列`:''}</li>`).join('')}</ol><p class="inventory-hint">请核对所有转移与卸下项。确认后逐步执行并重读核验；预览两分钟内有效。</p><button class="primary-button" data-equipment="start">确认执行 ${plan.total} 步装配</button>`:'<p>当前角色装备与方案一致，无需执行。</p>'}</div>`;
 }
 return {render,bind,payload,preview,inspected,reset(){character='';slots=[];core='keep';}};
})();
