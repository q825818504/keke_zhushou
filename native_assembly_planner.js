/* Native inventory adapter for the existing shape/layout engine; no DOM or RPC. */
(function(root,factory){
 const api=factory(typeof module==='object'&&module.exports?require('./drive_layout_solver.js'):root.DriveLayoutSolver);
 if(typeof module==='object'&&module.exports)module.exports=api;else root.NativeAssemblyPlanner=api;
})(typeof window!=='undefined'?window:globalThis,engine=>{
 const shapeKey=cells=>JSON.stringify((cells||[]).map(p=>[...p]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]));
 const shapeOf=item=>item&&engine.definitions.find(s=>shapeKey(s.cells)===shapeKey(item.cells));
 function plan(info,characterId,itemIds){
  const target=info.characters.find(c=>c.character_id===characterId);
  if(!target?.board)throw Error('当前角色缺少已核实的原生终端盘面');
  if(!Array.isArray(itemIds)||itemIds.length>10||new Set(itemIds).size!==itemIds.length)throw Error('驱动清单无效或重复');
  const selected=itemIds.map(id=>info.items.find(i=>i.id===id&&i.category==='drive')),counts={};
  for(const item of selected){const shape=shapeOf(item);if(!shape)throw Error('所选驱动实例或形状不受支持');counts[shape.id]=(counts[shape.id]||0)+1;}
  if(!selected.length)return [];
  const terminal={layout:{rows:5,columns:5,active_slots:target.board.map(([row,column])=>({row,column}))}};
  const result=engine.placementsFor(terminal,counts,{limit:1,maxNodes:100000}),layout=result.plans[0];
  if(!layout)throw Error(result.complete?'所选驱动无法同时放入该角色盘面，请调整形状组合':'摆放搜索达到限制，请减少驱动或手动指定位置');
  const used=new Set();
  return layout.pieces.map(piece=>{
   const item=selected.find(i=>!used.has(i.id)&&shapeOf(i).id===piece.shape_id);
   if(!item)throw Error('摆法与所选装备不一致');used.add(item.id);
   return {id:item.id,row:piece.row,column:piece.column};
  });
 }
 return {shapeOf,plan};
});
