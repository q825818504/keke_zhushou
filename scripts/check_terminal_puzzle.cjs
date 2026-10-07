const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{},localStorage:{getItem:()=>null}};vm.createContext(ctx);
for(const f of ['data/knowledge/characters/zhenhong.js','data/knowledge/characters/other_characters.js','data/knowledge/character_overrides.js','data/knowledge/encyclopedia/sky_curtains.js','character_recommendations.js','drive_layout_solver.js','terminal_puzzle.js'])vm.runInContext(fs.readFileSync(f,'utf8'),ctx);
const p=ctx.window.TerminalPuzzle,plans={};let variants=0;
const zhenhong=ctx.window.characterKnowledge.zhenhong;
const correctTerminal='每装配一个Ⅲ型驱动，使暴击伤害增加16%';
assert.equal(zhenhong.terminal.description,correctTerminal,'Zhenhong source terminal must match the live guide');
assert.equal(zhenhong.recommended.cassette.terminal.description,correctTerminal,'nested cassette terminal must stay in sync');
const effectiveZhenhong=ctx.window.CharacterRecommendations.createKnowledge(zhenhong);
assert.equal(effectiveZhenhong.terminal.description,correctTerminal,'maintainer override must apply to the user-facing terminal');
assert.equal(effectiveZhenhong.recommended.cassette.terminal.description,correctTerminal,'saved recommendation cannot restore stale terminal copy');
const staleZhenhong=structuredClone(zhenhong);staleZhenhong.terminal.description='每装配一个亚型驱动，使暴击伤害增加16%';staleZhenhong.recommended.cassette.terminal.description=staleZhenhong.terminal.description;
const correctedAfterReimport=ctx.window.CharacterRecommendations.createKnowledge(staleZhenhong);assert.equal(correctedAfterReimport.terminal.description,correctTerminal,'maintainer correction must survive stale imported data');assert.equal(correctedAfterReimport.recommended.cassette.terminal.description,correctTerminal,'stale recommendation copy must not reintroduce incorrect wording');
for(const raw of Object.values(ctx.window.characterKnowledge)){
 const k=ctx.window.CharacterRecommendations.createKnowledge(raw),t=p.terminalOf(k);if(!t)continue;
 if(p.cassetteOf(k)) {
 const plan=p.solveFor(k),s=p.validate(t,plan);assert(s.valid,k.name);assert.equal(s.filled,s.total,k.name);assert(p.setStatus(k,plan).complete,k.name);plans[k.id]=plan;
 const before=JSON.stringify(k);p.resolve(k);assert.equal(JSON.stringify(k),before);
 const seeded=p.solveFor(k,plan.preferred_model,[plan.pieces[0]]);assert(seeded);assert.deepEqual(seeded.pieces[0],plan.pieces[0]);assert(p.setStatus(k,seeded).complete);
 const missing=structuredClone(plan);const required=p.requirements(k)[0].shape_id;missing.pieces=missing.pieces.filter(x=>x.shape_id!==required);assert.equal(p.setStatus(k,missing).complete,false);
 const legacy={...k,recommended:{...k.recommended,terminal_puzzle:{...plan,cassette_id:'old-set'}}};assert.equal(p.resolve(legacy).cassette_id,k.recommended.cassette.id);
 } else assert.equal(p.solveFor(k),null,"unconfigured cassette must not fabricate activation");
 // Each terminal / all 12 sets, with exact geometry and four-shape requirements.
 for(const cassette of ctx.window.skyCurtainKnowledge.items){
   const alternative={...k,recommended:{...k.recommended,cassette:{id:cassette.id}}},candidate=p.solveFor(alternative);
   assert(candidate,k.name+'/'+cassette.name);assert(p.setStatus(alternative,candidate).complete);assert.equal(p.validate(t,candidate).filled,20);variants++;
 }
}
const lost=ctx.window.skyCurtainKnowledge.items.find(x=>x.id==='shiluo-guangmang');
const k={...ctx.window.characterKnowledge.canhong,recommended:{cassette:{id:lost.id}}},lostPlan=p.solveFor(k);assert.equal(p.validate(k.terminal,lostPlan).counts[3],4,'lost set requires II and IV; upper bound is four III');
const generic={layout:{rows:1,columns:4,active_slots:[1,2,3,4].map(column=>({row:1,column}))}};
assert.equal(p.solve(generic,3,[],[{shape_id:'cell4_style2_1',count:1}]),null,'never silently relax impossible set');
assert.equal(p.setStatus({recommended:{cassette:{id:'unknown'}}},lostPlan).known,false);
fs.mkdirSync('build/terminal-qa',{recursive:true});fs.writeFileSync('build/terminal-qa/plans.json',JSON.stringify(plans));
console.log(`Set solver passed: ${Object.keys(plans).length} defaults and ${variants} terminal/set pairings fully filled and four-shape complete; missing requirements, stale set IDs and impossible constraints checked.`);
