const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const box={window:{}};vm.runInNewContext(fs.readFileSync('cassette_scoring.js','utf8'),box);
const scorer=box.window.KekeCassetteScoring,optimizer=require('../loadout_optimizer.js'),engine=require('../drive_layout_solver.js');
const driverCatalog=require('../data/knowledge/encyclopedia/driver_blocks.json');
const tapeCatalog=require('../data/knowledge/encyclopedia/sky_curtains.json');
const terminal=require('../data/knowledge/characters/canhong.json').terminal;
const cassetteInfo=tapeCatalog.items.find(row=>row.id==='shiluo-guangmang');
const requirements=cassetteInfo.set_requirements.required_drives;
const cassette={id:cassetteInfo.id,name:cassetteInfo.name,terminal,
  recommended_main_affixes:[{name:'暴击率',priority:5}],
  recommended_sub_affixes:[{name:'暴击率',priority:5},{name:'暴击伤害',priority:4},{name:'攻击力百分比',priority:3},{name:'环合强度',priority:2}]};
const good=['暴击率','暴击伤害','攻击力百分比','环合强度'].map(name=>({name}));
const weak=['防御力','生命值','防御力百分比','生命值百分比'].map(name=>({name}));
const shape=id=>engine.byId.get(id);
const drive=(id,shapeId,subs=good,owner=null)=>({id,name:id,category:'drive',cells:shape(shapeId).cells.map(cell=>[...cell]),sub_stats:subs,rarity:'ORANGE',owner});
const tape=(id,name,owner,main,subs)=>({id,name,category:'tape',owner,rarity:'ORANGE',main_stats:[{name:main}],sub_stats:subs});
const recommendedTape=tape('recommended-low',cassetteInfo.name,1,'环合强度',weak);
const foreignTape=tape('foreign-high','森林萤火之心',null,'暴击率',good);
const mandatoryDrives=requirements.map((row,index)=>drive(`required-${index}`,row.shape_id,good,index===0?1:null));
const highH2=Array.from({length:4},(_,i)=>drive(`high-h2-${i}`,'cell2_style2_1',good));
const weakH4=Array.from({length:2},(_,i)=>drive(`weak-h4-${i}`,'cell4_style1_1',weak));
const snapshot={characters:[{character_id:1,board:terminal.layout.active_slots.map(slot=>[slot.row,slot.column])}],
  items:[foreignTape,recommendedTape,...mandatoryDrives,...highH2,...weakH4]};
const run=(source=snapshot,options={})=>optimizer.optimize({snapshot:source,characterId:1,cassette,driverCatalog,tapeCatalog,...options},scorer);

let result=run();
assert.equal(result.complete,true,'the best legal set-constrained scheme is proven');
assert.equal(result.core,recommendedTape.id,'never trade away the recommended cassette for a higher scoring set');
assert.equal(result.cassette_id,cassette.id);
assert.equal(result.schemes_evaluated>1,true,'score every feasible drive-shape profile');
assert.equal(result.filled,20);
const selectedItems=result.modules.map(position=>snapshot.items.find(item=>item.id===position.id));
const selectedCounts=new Map();
for(const item of selectedItems){const id=engine.definitions.find(shape=>JSON.stringify(shape.cells)===JSON.stringify(item.cells)).id;selectedCounts.set(id,(selectedCounts.get(id)||0)+1);}
for(const requirement of requirements)assert((selectedCounts.get(requirement.shape_id)||0)>=requirement.count,`required set shape ${requirement.shape_id} must be present`);
assert.equal(selectedItems.filter(item=>item.id.startsWith('high-h2-')).length,4,'score-first ranking beats the zero-score filler profile');
assert.equal(selectedItems.filter(item=>item.id.startsWith('weak-h4-')).length,0);
assert.equal(result.total,result.tapeScore+result.driveScore);
assert.equal(result.tapeScore,scorer.scoreItem(recommendedTape,cassette,cassetteInfo).score);

// Independent exhaustive profile oracle: score every stock count and retain only legal layouts.
const drives=snapshot.items.filter(item=>item.category==='drive');
const grouped=new Map(engine.definitions.map(row=>[row.id,[]]));
for(const item of drives){
  const shapeRow=engine.definitions.find(row=>JSON.stringify(row.cells)===JSON.stringify(item.cells));
  const catalog=driverCatalog.items.find(row=>row.id===shapeRow.id);
  const score=scorer.scoreDrive(item,cassette,catalog)?.score||0;
  grouped.get(shapeRow.id).push({item,score:score*shapeRow.model});
}
for(const bucket of grouped.values())bucket.sort((a,b)=>b.score-a.score||a.item.id.localeCompare(b.item.id));
const minimum=Object.fromEntries(requirements.map(row=>[row.shape_id,row.count]));
let oracle=-Infinity;
function enumerateProfiles(index,counts,area,value){
  if(index===engine.definitions.length){
    if(!area)return;
    for(const row of requirements)if((counts[row.shape_id]||0)<row.count)return;
    const layout=engine.placementsFor({layout:{rows:5,columns:5,active_slots:snapshot.characters[0].board.map(([row,column])=>({row,column}))}},counts,{limit:1,maxNodes:100000});
    if(layout.plans.length)oracle=Math.max(oracle,value);
    return;
  }
  const definition=engine.definitions[index],bucket=grouped.get(definition.id),min=minimum[definition.id]||0;
  for(let count=min;count<=bucket.length&&area+count*definition.model<=snapshot.characters[0].board.length;count++){
    counts[definition.id]=count;
    const nextValue=bucket.slice(0,count).reduce((sum,row)=>sum+row.score,0);
    enumerateProfiles(index+1,counts,area+count*definition.model,value+nextValue);
  }
  delete counts[definition.id];
}
enumerateProfiles(0,{},0,0);
assert.equal(result.driveScore,oracle/snapshot.characters[0].board.length,'optimizer matches exhaustive legal profile scoring');

// Other sets remain ineligible even when their tape has a better stat score and is unowned.
result=run(snapshot,{excludeOthers:false});
assert.equal(result.core,recommendedTape.id);
assert.equal(result.tapeScore<scorer.scoreItem(foreignTape,cassette,cassetteInfo).score,true);

// Current-role items remain eligible, while another role's mandatory shape is excluded.
const blocked={...snapshot,items:snapshot.items.map(item=>item.id===mandatoryDrives[0].id?{...item,owner:2}:item)};
assert.throws(()=>run(blocked),/缺少.*四件套/);
result=run(blocked,{excludeOthers:false});assert.equal(result.complete,true);

// Direct set IDs are authoritative; a mismatched explicit ID cannot fall back to a matching display name.
const mismatched={...snapshot,items:snapshot.items.map(item=>item.id===recommendedTape.id?{...item,name:cassetteInfo.name,set_id:'emozhixie-zuzhou'}:item)};
assert.throws(()=>run(mismatched),/没有可用的图鉴推荐空幕/);
const direct={...snapshot,items:snapshot.items.map(item=>item.id===recommendedTape.id?{...item,name:'旧版显示名',set_id:cassetteInfo.id}:item)};
assert.equal(run(direct).core,recommendedTape.id);
const nativeSetId={...snapshot,items:snapshot.items.map(item=>item.id===recommendedTape.id?{...item,name:`【${cassetteInfo.name}】`,set_id:'Suit6'}:item)};
assert.equal(run(nativeSetId).core,recommendedTape.id,'native Suit6 must map through the cassette display name, not be compared to the catalog slug');

// Native Suit4 includes a Chinese colon that the encyclopedia slug display name omits.
const zhenhong=tapeCatalog.items.find(row=>row.id==='zhenhong-shuangshengdie');
const zhenhongCassette={...cassette,id:zhenhong.id,name:zhenhong.name};
const punctuationNameTape={...tape('suit4-item','「真红：双生蝶」',1,'暴击率',good),set_id:'Suit4'};
assert.throws(()=>optimizer.optimize({snapshot:{...snapshot,items:[punctuationNameTape]},characterId:1,cassette:zhenhongCassette,driverCatalog,tapeCatalog},scorer),/缺少「真红双生蝶」激活四件套所需的驱动形状/,
  'native Suit4 with punctuation differences must resolve to the encyclopedia cassette before drive validation');

assert.throws(()=>run({...snapshot,items:snapshot.items.filter(item=>item.id!==recommendedTape.id)}),/没有可用的图鉴推荐空幕/);
assert.throws(()=>optimizer.optimize({snapshot,characterId:1,cassette:{...cassette,id:'unknown'},driverCatalog,tapeCatalog},scorer),/未找到对应空幕图鉴数据/);
const badRequirement={...cassetteInfo,set_requirements:{required_drives:requirements.slice(0,3)}};
assert.throws(()=>optimizer.optimize({snapshot,characterId:1,cassette,driverCatalog,tapeCatalog:{items:[badRequirement]}},scorer),/四种套装驱动资料不完整/);
assert.throws(()=>run(snapshot,{maxNodes:1}),/搜索达到计算上限/);
console.log(`Loadout optimizer passed: recommended set locked, four exact shapes enforced, ${result.schemes_evaluated||'multiple'} shape profiles scored, exhaustive optimum, ownership and fail-closed data checks.`);
