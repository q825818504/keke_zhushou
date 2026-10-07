/* Pure drive layout engine. No DOM, role catalog, storage or image dependencies. */
(function (root, factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.DriveLayoutSolver=api;
})(typeof window!=='undefined'?window:globalThis, () => {
  const definitions = [
    ['cell2_style1_1','Ⅱ-横',2,[[0,0],[0,1]]], ['cell2_style2_1','Ⅱ-竖',2,[[0,0],[1,0]]],
    ['cell3_style1_1','Ⅲ-横',3,[[0,0],[0,1],[0,2]]], ['cell3_style2_1','Ⅲ-竖',3,[[0,0],[1,0],[2,0]]],
    ['cell3_style3_1','Ⅲ-左上',3,[[0,0],[0,1],[1,0]]], ['cell3_style4_1','Ⅲ-右上',3,[[0,0],[0,1],[1,1]]],
    ['cell3_style5_1','Ⅲ-左下',3,[[0,0],[1,0],[1,1]]], ['cell3_style6_1','Ⅲ-右下',3,[[0,1],[1,0],[1,1]]],
    ['cell4_style1_1','Ⅳ-横',4,[[0,0],[0,1],[0,2],[0,3]]], ['cell4_style2_1','Ⅳ-竖',4,[[0,0],[1,0],[2,0],[3,0]]],
    ['cell4_style5_1','Ⅳ-Z横',4,[[0,1],[0,2],[1,0],[1,1]]], ['cell4_style6_1','Ⅳ-Z竖',4,[[0,1],[1,0],[1,1],[2,0]]]
  ].map(([id,label,model,cells]) => ({id,label,model,cells}));
  const byId = new Map(definitions.map(shape => [shape.id,shape]));
  const cache = new Map();
  function terminalOf(knowledge) { return knowledge?.terminal || knowledge?.recommended?.cassette?.terminal; }
  function board(terminal) {
    const layout = terminal?.layout;
    if (!layout || !Number.isInteger(layout.rows) || !Number.isInteger(layout.columns) || layout.rows < 1 || layout.columns < 1 || layout.rows > 12 || layout.columns > 12) return null;
    const cells = [...new Map((layout.active_slots || []).filter(s => Number.isInteger(s.row) && Number.isInteger(s.column) && s.row > 0 && s.row <= layout.rows && s.column > 0 && s.column <= layout.columns).map(s => [`${s.row}:${s.column}`,{row:s.row,column:s.column}])).values()].sort((a,b) => a.row-b.row || a.column-b.column);
    // Reference terminals contain 20 slots; bound the exact bit-mask solver.
    if (!cells.length || cells.length > 24) return null;
    return {cells,keys:new Set(cells.map(s => `${s.row}:${s.column}`)), minRow:Math.min(...cells.map(s=>s.row)),maxRow:Math.max(...cells.map(s=>s.row)),minColumn:Math.min(...cells.map(s=>s.column)),maxColumn:Math.max(...cells.map(s=>s.column))};
  }
  function preference(terminal) {
    const match = (terminal?.description || '').match(/(?:每装配|每装备)[^ⅡⅢⅣ]*([ⅡⅢⅣ])型/);
    return match ? {'Ⅱ':2,'Ⅲ':3,'Ⅳ':4}[match[1]] : 0;
  }
  function pieceCells(piece) {
    return (byId.get(piece.shape_id)?.cells || []).map(([r,c]) => ({row:piece.row+r,column:piece.column+c}));
  }
  function validate(terminal,plan) {
    const b = board(terminal);
    if (!b || !plan || plan.version !== 1 || ![0,2,3,4].includes(plan.preferred_model) || !Array.isArray(plan.pieces) || plan.pieces.length > b.cells.length/2) return {valid:false,error:'摆法数据无效'};
    const used = new Set(), ids = new Set();
    for (const piece of plan.pieces) {
      if (!piece || !/^D\d{2,3}$/.test(piece.id) || ids.has(piece.id) || !byId.has(piece.shape_id) || !Number.isInteger(piece.row) || !Number.isInteger(piece.column)) return {valid:false,error:'驱动编号或形状无效'};
      ids.add(piece.id);
      for (const s of pieceCells(piece)) {
        const key = `${s.row}:${s.column}`;
        if (!b.keys.has(key) || used.has(key)) return {valid:false,error:'驱动重叠或超出可用槽位'};
        used.add(key);
      }
    }
    const counts = {2:0,3:0,4:0};
    plan.pieces.forEach(p => counts[byId.get(p.shape_id).model]++);
    return {valid:true,filled:used.size,total:b.cells.length,counts,preferred:counts[plan.preferred_model] || 0};
  }
  function solve(terminal,preferred = preference(terminal),fixed = [],required = []) {
    const b = board(terminal);
    if (!b) return null;
    const seed = {version:1,preferred_model:preferred,pieces:fixed};
    if (!validate(terminal,seed).valid) return null;
    const needs=required.flatMap(r=>Array.from({length:r.count},()=>r.shape_id));
    if(needs.length>4 || needs.some(id=>!byId.has(id))) return null;
    const key = JSON.stringify([b.cells,preferred,fixed,needs]);
    if (cache.has(key)) return JSON.parse(cache.get(key));
    const indices = new Map(b.cells.map((s,i)=>[`${s.row}:${s.column}`,i]));
    const placements = b.cells.map(()=>[]), seen = new Set();
    for (const shape of definitions) for (const slot of b.cells) for (const [dr,dc] of shape.cells) {
      const row = slot.row-dr, column = slot.column-dc;
      const ids = shape.cells.map(([r,c])=>indices.get(`${row+r}:${column+c}`));
      if (ids.some(i=>i === undefined)) continue;
      const mask = ids.reduce((m,i)=>m | (1<<i),0);
      const identity = `${shape.id}:${mask}`;
      if (seen.has(identity)) continue;
      seen.add(identity);
      const p = {shape_id:shape.id,row,column,mask,model:shape.model};
      ids.forEach(i=>placements[i].push(p));
    }
    for (const list of placements) list.sort((a,b)=>(b.model===preferred)-(a.model===preferred) || b.model-a.model || a.shape_id.localeCompare(b.shape_id));
    let available = (1<<b.cells.length)-1;
    fixed.flatMap(pieceCells).forEach(s=>{available &= ~(1<<indices.get(`${s.row}:${s.column}`));});
    let remaining=(1<<needs.length)-1;
    for(const piece of fixed) {const i=needs.findIndex((id,i)=>id===piece.shape_id && (remaining & (1<<i)));if(i>=0) remaining &= ~(1<<i);}
    const memo = new Map();
    // Required set shapes are hard constraints. Within valid completions maximize
    // occupied area, then preferred piece count, then minimize filler piece count.
    function best(mask,need) {
      if (!mask) return {score:need ? -Infinity : 0,next:0,need,piece:null};
      const state=mask*16+need;
      if (memo.has(state)) return memo.get(state);
      const bit = mask & -mask, index = 31-Math.clz32(bit);
      let result = {score:-Infinity,next:0,need,piece:null};
      for (const p of placements[index]) {
        if ((mask & p.mask) !== p.mask) continue;
        const next = mask ^ p.mask;
        const requiredIndex=needs.findIndex((id,i)=>id===p.shape_id && (need & (1<<i)));
        const nextNeed=requiredIndex>=0 ? need & ~(1<<requiredIndex) : need;
        const score = best(next,nextNeed).score + p.model*10000 + (p.model===preferred ? 100 : 0) - 1;
        if (score > result.score) result = {score,next,need:nextNeed,piece:p};
      }
      const next = mask ^ bit, score = best(next,need).score;
      if (score > result.score) result = {score,next,need,piece:null};
      memo.set(state,result);
      return result;
    }
    if(!Number.isFinite(best(available,remaining).score)) return null;
    const pieces = fixed.map(p=>({...p}));
    let counter=1;
    const ids = new Set(pieces.map(p=>p.id));
    while (available) {
      const entry=best(available,remaining);
      if (entry.piece) {
        while(ids.has(`D${String(counter).padStart(2,'0')}`)) counter++;
        const id=`D${String(counter++).padStart(2,'0')}`;
        ids.add(id);
        const {shape_id,row,column}=entry.piece;
        pieces.push({id,shape_id,row,column});
      }
      available=entry.next;remaining=entry.need;
    }
    const plan={version:1,preferred_model:preferred,pieces};
    cache.set(key,JSON.stringify(plan));
    return plan;
  }
  function profileKey(counts) {return definitions.map(s=>`${s.id}:${counts[s.id]||0}`).join('|');}
  function compareMetrics(a,b,rankBy) {
    return b.filled-a.filled || (rankBy==='equipment_first' ? b.equipmentScore-a.equipmentScore || b.preferred-a.preferred : b.preferred-a.preferred || b.equipmentScore-a.equipmentScore) || a.pieceCount-b.pieceCount;
  }
  function weightedItemScore(item,weights={}) {
    let score=0;
    for(const [stat,weight] of Object.entries(weights)) {
      if(!Number.isFinite(weight)) throw new TypeError('Weights must be finite numbers');
      const value=item.stats?.[stat] ?? 0;
      if(!Number.isFinite(value)) throw new TypeError('Stats must be normalized finite numbers');
      score+=weight*value;
    }
    if(!Number.isFinite(score)) throw new TypeError('Equipment score overflow');
    return score;
  }
  function placementsFor(terminal,shapeCounts,{fixed=[],limit=1,maxNodes=100000}={}) {
    const b=board(terminal),seed={version:1,preferred_model:0,pieces:fixed};
    if(!b || !validate(terminal,seed).valid) throw new TypeError('Invalid terminal or fixed placements');
    if(!Number.isInteger(limit)||limit<1||limit>64||!Number.isInteger(maxNodes)||maxNodes<1) throw new TypeError('Invalid search limits');
    const remaining=definitions.map(s=>shapeCounts[s.id]||0);
    for(const [id,n] of Object.entries(shapeCounts)) if(!byId.has(id)||!Number.isInteger(n)||n<0) throw new TypeError('Invalid shape counts');
    for(const piece of fixed) {const i=definitions.findIndex(s=>s.id===piece.shape_id);if(--remaining[i]<0) return {plans:[],complete:true,nodes:0};}
    const index=new Map(b.cells.map((s,i)=>[`${s.row}:${s.column}`,i]));
    const choices=b.cells.map(()=>[]);
    for(let shapeIndex=0;shapeIndex<definitions.length;shapeIndex++) {
      if(!remaining[shapeIndex]) continue;
      const shape=definitions[shapeIndex],seen=new Set();
      for(const cell of b.cells) for(const [dr,dc] of shape.cells) {
        const row=cell.row-dr,column=cell.column-dc,ids=shape.cells.map(([r,c])=>index.get(`${row+r}:${column+c}`));
        if(ids.some(i=>i===undefined)) continue;
        const mask=ids.reduce((m,i)=>m|(1<<i),0);
        if(seen.has(mask))continue;seen.add(mask);
        const placement={shapeIndex,shape_id:shape.id,row,column,mask};ids.forEach(i=>choices[i].push(placement));
      }
    }
    let available=(1<<b.cells.length)-1;
    fixed.flatMap(pieceCells).forEach(s=>{available &= ~(1<<index.get(`${s.row}:${s.column}`));});
    const plans=[],path=[],failed=new Set();let nodes=0,stopped=false;
    function visit(mask,area) {
      if(++nodes>maxNodes){stopped=true;return false;}
      if(area===0) {
        const pieces=fixed.map(p=>({...p})),ids=new Set(pieces.map(p=>p.id));let counter=1;
        for(const p of path) {while(ids.has(`D${String(counter).padStart(2,'0')}`))counter++;const id=`D${String(counter++).padStart(2,'0')}`;ids.add(id);pieces.push({id,shape_id:p.shape_id,row:p.row,column:p.column});}
        plans.push({version:1,preferred_model:0,pieces});return true;
      }
      if(!mask || area>popcount(mask))return false;
      const key=`${mask}:${remaining.join(',')}`;if(failed.has(key))return false;
      const bit=mask & -mask,i=31-Math.clz32(bit);let found=false;
      for(const p of choices[i]) {
        if(!remaining[p.shapeIndex] || (mask&p.mask)!==p.mask)continue;
        remaining[p.shapeIndex]--;path.push(p);
        found=visit(mask^p.mask,area-definitions[p.shapeIndex].model)||found;
        path.pop();remaining[p.shapeIndex]++;
        if(stopped||plans.length>=limit){stopped=true;return found;}
      }
      if(area<popcount(mask))found=visit(mask^bit,area)||found;
      if(!found&&!stopped)failed.add(key);
      return found;
    }
    const area=remaining.reduce((sum,n,i)=>sum+n*definitions[i].model,0);visit(available,area);
    return {plans,complete:!stopped,nodes};
  }
  function popcount(mask){let n=0;while(mask){mask &= mask-1;n++;}return n;}
  function generateCandidates({terminal,preferredModel=preference(terminal),required=[],fixed=[],inventoryCounts,inventory,weights={},scoreItem,excludedUids=[],limit=64,maxNodes=500000,layoutsPerProfile=1,rankBy='passive_first',allowPartial=true}={}) {
    const b=board(terminal);
    if(!b || ![0,2,3,4].includes(preferredModel) || !validate(terminal,{version:1,preferred_model:preferredModel,pieces:fixed}).valid) throw new TypeError('Invalid board, preference or fixed pieces');
    if(!Number.isInteger(limit)||limit<1||limit>256||!Number.isInteger(maxNodes)||maxNodes<1||!Number.isInteger(layoutsPerProfile)||layoutsPerProfile<1||layoutsPerProfile>64||!['passive_first','equipment_first'].includes(rankBy))throw new TypeError('Invalid candidate options');
    const minimum=definitions.map(()=>0),shapeIndex=new Map(definitions.map((s,i)=>[s.id,i]));
    if(!Array.isArray(required))throw new TypeError('Required drives must be an array');
    for(const r of required){if(!shapeIndex.has(r.shape_id)||!Number.isInteger(r.count)||r.count<1)throw new TypeError('Invalid required shape');minimum[shapeIndex.get(r.shape_id)]+=r.count;}
    const fixedCounts=definitions.map(()=>0);fixed.forEach(p=>fixedCounts[shapeIndex.get(p.shape_id)]++);
    minimum.forEach((n,i)=>{minimum[i]=Math.max(n,fixedCounts[i]);});
    const caps=definitions.map(s=>Math.floor(b.cells.length/s.model));
    if(inventoryCounts!==undefined){if(!inventoryCounts||typeof inventoryCounts!=='object'||Array.isArray(inventoryCounts))throw new TypeError('Invalid inventory counts');for(const [id,n] of Object.entries(inventoryCounts))if(!byId.has(id)||!Number.isInteger(n)||n<0)throw new TypeError('Invalid inventory count');caps.forEach((n,i)=>{caps[i]=Math.min(n,inventoryCounts[definitions[i].id]||0);});}
    let buckets=null;const reserved=new Map(),itemScores=new Map();
    if(inventory!==undefined){
      if(!Array.isArray(inventory))throw new TypeError('Inventory must be an array');
      buckets=definitions.map(()=>[]);const uids=new Set(),exclude=new Set(excludedUids),items=new Map();
      for(const item of inventory){
        if(!item||typeof item.uid!=='string'||!item.uid||uids.has(item.uid)||!byId.has(item.shape_id))throw new TypeError('Each inventory instance needs a unique UID and known shape');
        uids.add(item.uid);if(exclude.has(item.uid))continue;
        const score=scoreItem?scoreItem(item):weightedItemScore(item,weights);if(!Number.isFinite(score))throw new TypeError('Item score must be finite');
        itemScores.set(item.uid,score);items.set(item.uid,item);buckets[shapeIndex.get(item.shape_id)].push(item);
      }
      const used=new Set();
      for(const piece of fixed)if(piece.inventory_uid!==undefined){const item=items.get(piece.inventory_uid);if(!item||item.shape_id!==piece.shape_id||used.has(item.uid))throw new TypeError('Invalid fixed inventory UID');used.add(item.uid);const i=shapeIndex.get(item.shape_id);if(!reserved.has(i))reserved.set(i,[]);reserved.get(i).push(item);}
      buckets.forEach((bucket,i)=>{bucket.sort((a,b)=>itemScores.get(b.uid)-itemScores.get(a.uid)||a.uid.localeCompare(b.uid));const pinned=reserved.get(i)||[];buckets[i]=pinned.concat(bucket.filter(item=>!used.has(item.uid)));caps[i]=Math.min(caps[i],buckets[i].length);});
    }
    const empty={candidates:[],status:'infeasible',searchComplete:true,truncated:false,rankingComplete:true,nodes:0,scope:'shape_counts',rankBy};
    if(minimum.some((n,i)=>n>caps[i]))return empty;
    let nodes=0,enumerationComplete=true;const profiles=[],counts=definitions.map(()=>0);
    function enumerate(i,area) {
      if(++nodes>maxNodes){enumerationComplete=false;return;}
      if(i===definitions.length){
        if(!area)return;
        if(!allowPartial && area!==b.cells.length)return;
        const shape_counts=Object.fromEntries(definitions.map((s,j)=>[s.id,counts[j]]).filter(([,n])=>n));
        const preferred=counts.reduce((n,c,j)=>n+(definitions[j].model===preferredModel?c:0),0);
        const equipmentScore=buckets ? counts.reduce((score,n,j)=>score+buckets[j].slice(0,n).reduce((sum,item)=>sum+itemScores.get(item.uid),0),0) : 0;
        profiles.push({shape_counts,profileKey:profileKey(shape_counts),metrics:{filled:area,preferred,equipmentScore,pieceCount:counts.reduce((a,b)=>a+b,0)}});return;
      }
      const future=minimum.slice(i+1).reduce((n,c,j)=>n+c*definitions[i+1+j].model,0);
      const max=Math.min(caps[i],Math.floor((b.cells.length-area-future)/definitions[i].model));
      for(let n=minimum[i];n<=max;n++){counts[i]=n;enumerate(i+1,area+n*definitions[i].model);if(!enumerationComplete)return;}
    }
    enumerate(0,0);profiles.sort((a,b)=>compareMetrics(a.metrics,b.metrics,rankBy)||a.profileKey.localeCompare(b.profileKey));
    const candidates=[];let examined=0,unresolved=false,spatialTruncated=false;
    for(const profile of profiles){
      if(nodes>=maxNodes){unresolved=true;break;}
      const result=placementsFor(terminal,profile.shape_counts,{fixed,limit:layoutsPerProfile,maxNodes:maxNodes-nodes});nodes+=result.nodes;examined++;
      if(!result.plans.length&&!result.complete)unresolved=true;
      if(layoutsPerProfile>1 && !result.complete)spatialTruncated=true;
      for(const plan of result.plans){
        plan.preferred_model=preferredModel;
        if(buckets){const queues=buckets.map((bucket,i)=>bucket.slice(0,profile.shape_counts[definitions[i].id]||0)),used=new Set(fixed.map(p=>p.inventory_uid).filter(Boolean));
          for(const piece of plan.pieces) {if(piece.inventory_uid)continue;const queue=queues[shapeIndex.get(piece.shape_id)],item=queue.find(item=>!used.has(item.uid));piece.inventory_uid=item.uid;used.add(item.uid);}
        }
        const placementKey=plan.pieces.map(p=>`${p.shape_id}@${p.row},${p.column}`).sort().join('|');
        candidates.push({...profile,placementKey,plan});if(candidates.length>=limit)break;
      }
      if(candidates.length>=limit)break;
    }
    const searchComplete=enumerationComplete&&!unresolved&&!spatialTruncated&&examined===profiles.length;
    return {candidates,status:candidates.length?'ok':searchComplete?'infeasible':'budget_exhausted',searchComplete,truncated:!searchComplete,rankingComplete:enumerationComplete&&!unresolved,nodes,examinedProfiles:examined,generatedProfiles:profiles.length,scope:layoutsPerProfile===1?'shape_counts':'placements',rankBy};
  }
  return {definitions,byId,board,pieceCells,validate,solve,preference,terminalOf,profileKey,weightedItemScore,placementsFor,generateCandidates};
});
