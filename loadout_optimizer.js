/* Exact account-inventory optimizer constrained by the role's cassette set. */
(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./drive_layout_solver.js'):root.DriveLayoutSolver);
  if(typeof module==='object'&&module.exports)module.exports=api;else root.KekeLoadoutOptimizer=api;
})(typeof window!=='undefined'?window:globalThis,engine=>{
  // Native suit labels may include punctuation omitted by encyclopedia names,
  // e.g. 「真红：双生蝶」 vs 真红双生蝶.
  const nameKey=value=>String(value||'').normalize('NFKC').replace(/[\s\p{P}\p{S}]/gu,'').toLowerCase();
  const shapeKey=cells=>JSON.stringify((cells||[]).map(([row,column])=>[Number(row),Number(column)]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]));

  function catalogIdForTape(item,catalogItems){
    const directCassetteId=item?.cassette_id??item?.source_data?.cassette_id;
    if(directCassetteId!=null&&String(directCassetteId).trim())return String(directCassetteId).trim();
    // NTE's native adapter exposes `set_id` as a game key such as `Suit6`,
    // while the encyclopedia uses slugs. Only accept it directly if it is
    // already a catalog ID; otherwise resolve the game's display name below.
    const nativeSetId=item?.set_id??item?.source_data?.set_id;
    const setMatch=catalogItems.find(row=>String(row.id)===String(nativeSetId));
    if(setMatch)return String(setMatch.id);
    const key=nameKey(item?.name);
    return key?String(catalogItems.find(row=>nameKey(row.name)===key)?.id||''):'';
  }

  function optimize({snapshot,characterId,cassette,driverCatalog,tapeCatalog,excludeOthers=true,protectedOwners=[],maxNodes=2000000,maxMs=15000},scorer){
    const role=snapshot.characters.find(row=>String(row.character_id)===String(characterId));
    if(!role?.board?.length)throw Error('请先读取角色盘面');
    if(!cassette?.id)throw Error('该角色尚未在图鉴中配置推荐空幕，无法计算毕业配装');
    if(!cassette.recommended_main_affixes?.length||!cassette.recommended_sub_affixes?.length)throw Error('请先为推荐空幕配置角色主、副属性优先级');

    const catalogItems=tapeCatalog?.items||[],recommendedTape=catalogItems.find(row=>String(row.id)===String(cassette.id));
    if(!recommendedTape)throw Error(`角色图鉴推荐空幕「${cassette.name||cassette.id}」未找到对应空幕图鉴数据`);
    const required=recommendedTape.set_requirements?.required_drives;
    const distinctRequired=new Set((required||[]).map(row=>row?.shape_id));
    if(!Array.isArray(required)||required.length!==4||distinctRequired.size!==4||required.some(row=>!row||!engine.byId.has(row.shape_id)||row.count!==1))
      throw Error(`推荐空幕「${recommendedTape.name||cassette.name||cassette.id}」的四种套装驱动资料不完整，暂时无法计算`);

    const terminal={layout:{rows:5,columns:5,active_slots:role.board.map(([row,column])=>({row:Number(row),column:Number(column)}))}};
    const capacity=engine.board(terminal)?.cells.length;
    if(!capacity)throw Error('角色驱动盘面无效');
    const protectedRoles=new Set(protectedOwners.map(String));
    const available=snapshot.items.filter(item=>{
      const own=item.owner!=null&&String(item.owner)===String(characterId);
      return (own||item.owner==null||!protectedRoles.has(String(item.owner)))&&(!excludeOthers||item.owner==null||own);
    });
    let tape=null,tapeScore=-1,tapeIsOwn=false,skipped=0;
    for(const item of available){
      if(item.category!=='tape'||catalogIdForTape(item,catalogItems)!==String(cassette.id))continue;
      if(!(item.main_stats||item.main_attributes)?.length||!(item.sub_stats||item.sub_attributes)?.length){skipped++;continue;}
      const value=scorer.scoreItem(item,cassette,recommendedTape).score;
      const isOwn=item.owner!=null&&String(item.owner)===String(characterId);
      if(!tape||value>tapeScore||value===tapeScore&&Number(isOwn)>Number(tapeIsOwn)||value===tapeScore&&isOwn===tapeIsOwn&&String(item.id).localeCompare(String(tape.id))<0){
        tape=item;tapeScore=value;tapeIsOwn=isOwn;
      }
    }
    if(!tape)throw Error(`背包与本角色当前装备中没有可用的图鉴推荐空幕「${recommendedTape.name||cassette.name||cassette.id}」`);

    const shapes=new Map(engine.definitions.map(shape=>[shapeKey(shape.cells),shape]));
    const inventory=[],driveByUid=new Map(),eligibleCounts=new Map();
    for(const item of available){
      if(item.category!=='drive')continue;
      const shape=shapes.get(shapeKey(item.cells||[])),catalog=(driverCatalog?.items||[]).find(row=>row.id===shape?.id);
      const result=shape&&scorer.scoreDrive(item,cassette,catalog);
      if(!result||item.id==null){skipped++;continue;}
      // Keep equipped pieces ahead of transfers when their scores are tied.
      const own=item.owner!=null&&String(item.owner)===String(characterId),uid=`${own?'0':'1'}:${String(item.id)}`;
      const row={uid,shape_id:shape.id,value:result.score*shape.model};
      inventory.push(row);driveByUid.set(uid,{item,value:result.score*shape.model});
      eligibleCounts.set(shape.id,(eligibleCounts.get(shape.id)||0)+1);
    }

    const missing=required.filter(row=>(eligibleCounts.get(row.shape_id)||0)<row.count);
    if(missing.length){
      const labels=missing.map(row=>engine.byId.get(row.shape_id).label).join('、');
      throw Error(`缺少「${recommendedTape.name||cassette.name}」激活四件套所需的驱动形状：${labels}`);
    }

    const search=engine.generateCandidates({
      terminal,
      required,
      preferredModel:engine.preference(cassette.terminal),
      inventory,
      scoreItem:item=>item.value,
      limit:1,
      maxNodes,
      allowPartial:true,
      rankBy:'score_first'
    });
    const best=search.candidates[0];
    if(!best){
      if(search.status==='infeasible')throw Error(`没有能在当前盘面合法摆放并满足「${recommendedTape.name||cassette.name}」四件套的驱动方案`);
      throw Error('驱动摆法搜索达到计算上限，未能找到已验证的完整套装方案');
    }
    const validation=engine.validate(terminal,best.plan);
    if(!validation.valid||required.some(row=>(best.shape_counts[row.shape_id]||0)<row.count))throw Error('驱动方案没有通过套装形状或盘面校验，请重试');

    const modules=best.plan.pieces.map(piece=>{
      const selected=driveByUid.get(piece.inventory_uid);
      if(!selected)throw Error('驱动方案与背包实例对应失败，请刷新快照后重试');
      return {id:selected.item.id,row:piece.row,column:piece.column};
    });
    const driveScore=best.metrics.equipmentScore/capacity;
    return {core:tape.id,modules,exclude_others:excludeOthers,complete:search.optimalityProven===true,skipped,
      nodes:search.nodes,tapeScore,driveScore,total:tapeScore+driveScore,filled:best.metrics.filled,capacity,
      cassette_id:String(cassette.id),schemes_evaluated:search.generatedProfiles,schemes_checked:search.examinedProfiles};
  }
  return {optimize};
});
