const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const load = require('./team_model_fixture.cjs');
let checks = 0;
function fixture() {
  const {sandbox:s, vm} = load();
  const names = 'ABCDEFGHIJKL'.split('');
  vm.runInContext(`Object.keys(characterData).forEach(n=>delete characterData[n]); Object.keys(userTeamNameById).forEach(id=>delete userTeamNameById[id]);`,s);
  for (const [i,n] of names.entries()) vm.runInContext(`characterData['${n}']={id:'${n}',role:'${['主C','副C','辅助','治疗'][i%4]}',element:'光',rarity:'B',rating:'T4',knowledge:{mechanism_facts:{}}};userTeamNameById['${n}']='${n}';`,s);
  vm.runInContext(`userTeamOwnedNames=new Set(${JSON.stringify(names)})`,s);
  const records=[];s.window.teamGuideStore={all:()=>records};
  const record=(id,core,members,order=0)=>({id,source_core_character_id:core,member_character_ids:members.split(''),source_order:order,editorial:{active:true}});
  const add=(...args)=>{const row=record(...args);records.push(row);return row;};
  const pool=names=>vm.runInContext(`userTeamOwnedNames=new Set(${JSON.stringify(names)})`,s);
  const pairs=(locks=[],limit=3)=>s.userTeamRecommendPairs(locks,limit);
  return {s,vm,records,add,pool,pairs};
}
function valid(result,locks=[],pool=null){
  assert(result.pairs.length<=3);
  for(const {first,second} of result.pairs){
    assert.equal(new Set([...first.memberNames,...second.memberNames]).size,8);
    assert.notEqual(first.coreName,second.coreName);
    for(const p of [first,second]){assert.equal(p.memberNames.length,4);assert(p.memberNames.includes(p.coreName));assert.notEqual(p.sourceRecord.editorial.active,false);if(pool)assert(p.memberNames.every(n=>pool.includes(n)));}
    if(locks[0])assert.equal(first.coreName,locks[0]);if(locks[1])assert.equal(second.coreName,locks[1]);
  }
}
{
 const f=fixture();f.add('dead1','A','AEBC',1);f.add('dead2','A','AEBD',2);f.add('dead3','A','AECD',3);f.add('fourth','A','ABCD',4);f.add('partner','E','EFGH');
 const r=f.pairs(['A','E']);valid(r,['A','E']);assert.equal(r.pairs.length,1);assert.equal(r.pairs[0].first.id,'fourth');
 assert.equal(f.s.userTeamBuildPlans('A').length,3,'single-team truncation unchanged');checks++;
 const reverse=f.pairs(['E','A']);valid(reverse,['E','A']);assert.equal(reverse.pairs[0].second.id,'fourth');checks++;
 const one=f.pairs(['A']);valid(one,['A']);assert(one.pairs.length);checks++;
 const unlocked=f.pairs();valid(unlocked);assert.equal(unlocked.total,1,'mirror pairs removed');checks++;
 f.records.find(t=>t.id==='partner').editorial.active=false;assert.equal(f.pairs(['A','E']).reason,'second');checks++;
}
{
 const f=fixture();f.add('first','A','ABCD');f.add('second','E','EBCF');const r=f.pairs(['A','E']);assert.equal(r.reason,'conflict');assert.deepEqual(Array.from(r.conflictNames),['B','C']);assert.equal(r.pairs.length,0);checks++;
 f.pool(['A','E','F','G','H']);assert.equal(f.pairs(['A','E']).reason,'first');assert.deepEqual(Array.from(f.pairs(['A','E']).missingNames),['B','C','D']);checks++;
 f.pool(['A','B','C','D','E']);const missing=f.pairs(['A','E']);assert.equal(missing.reason,'second');assert.deepEqual(Array.from(missing.missingNames),['F']);checks++;
 assert.equal(f.pairs(['A','A']).reason,'locks');checks++;
 assert.equal(f.pairs(['L','E']).reason,'first','locked core is not substituted');checks++;
}
{
 const f=fixture();f.add('dup','A','ABBC');f.add('outside','A','BCDE');f.add('unknown','A','ABCZ');f.add('disabled','A','ABCD').editorial.active=false;f.add('good','E','EFGH');
 assert.equal(f.pairs(['A','E']).reason,'first');assert.equal(f.s.userTeamBuildPlans('A').length,0);checks++;
 f.records.length=0;assert.equal(f.pairs().pairs.length,0);assert.equal(f.s.userTeamRecommendPlans().length,0);checks++;
}
{
 const f=fixture();f.add('balanced','A','ABCD',1);f.add('unbalanced','A','AIJK',0);f.add('other','E','EFGH');
 assert.equal(f.pairs(['A','E']).pairs[0].first.id,'balanced');
 const before=JSON.stringify(f.pairs(['A','E']).pairs.map(p=>[p.id,p.weakest,p.total]));
 f.vm.runInContext("Object.values(characterData).forEach((c,i)=>{c.rarity=i%2?'S':'B';c.rating=i%2?'T0':'T4';});",f.s);
 assert.equal(JSON.stringify(f.pairs(['A','E']).pairs.map(p=>[p.id,p.weakest,p.total])),before);checks++;
}
{
 const f=fixture();f.add('first','A','ABCD',1);f.add('alternative','A','AJKL',2);f.add('other','E','EFGH');
 assert.equal(f.pairs(['A','E']).pairs[0].first.id,'first');
 f.vm.runInContext("userTeamInvestmentByCharacterId={J:{resonance:6,hasSignatureArc:true}}",f.s);
 assert.equal(f.pairs(['A','E']).pairs[0].first.id,'alternative','reported investment breaks a structural tie');checks++;
 f.add('third','A','ABCJ',3);f.add('fourth','A','ABCK',4);assert(f.pairs(['A','E']).total>3);assert.equal(f.pairs(['A','E']).pairs.length,3);assert.equal(f.pairs(['A','E'],99).pairs.length,3);checks++;
}
// Actual maintained overrides, not just imported source teams.
{
 const {sandbox:s,vm,root}=load();vm.runInContext(fs.readFileSync(path.join(root,'team_manager.js'),'utf8').split('let guideDraft =')[0],s);
 const names=vm.runInContext('Object.keys(characterData)',s);const without=Array.from(names).filter(n=>n!=='阿德勒');
 vm.runInContext(`userTeamOwnedNames=new Set(${JSON.stringify(without)})`,s);
 const missing=s.userTeamRecommendPairs(['残虹','安魂曲']);assert.equal(missing.pairs.length,0);assert.equal(missing.reason,'conflict');checks++;
 vm.runInContext(`userTeamOwnedNames=new Set(${JSON.stringify(Array.from(names))})`,s);
 const present=s.userTeamRecommendPairs(['残虹','安魂曲']);valid(present,['残虹','安魂曲']);assert(present.pairs.length);
 assert(present.pairs.some(p=>Array.from(p.second.memberNames).sort().join('|')===['安魂曲','白藏','黑羽','阿德勒'].sort().join('|')));checks++;
 for(const locks of [[],['残虹'],['残虹','安魂曲'],['安魂曲','残虹']]) {
  const r=s.userTeamRecommendPairs(locks);valid(r,locks,Array.from(names));assert.deepEqual(JSON.parse(JSON.stringify(r)),JSON.parse(JSON.stringify(s.userTeamRecommendPairs(locks))));
  const records=s.window.teamGuideStore.all(),cores=Array.from(new Set(records.filter(t=>t.editorial?.active!==false).map(t=>vm.runInContext('userTeamNameById['+JSON.stringify(t.source_core_character_id)+']',s)))).filter(Boolean);
  const first=locks[0]?[locks[0]]:cores,second=locks[1]?[locks[1]]:cores.filter(n=>n!==locks[0]);const seen=new Set();
  for(const a of first)for(const b of second){if(a===b||(!locks.length&&cores.indexOf(a)>cores.indexOf(b)))continue;
   for(const x of s.userTeamCollectPlans(a,new Set(),records))for(const y of s.userTeamCollectPlans(b,new Set(),records))
    if(!x.memberNames.some(n=>y.memberNames.includes(n)))seen.add(JSON.stringify([a,Array.from(x.memberNames).sort().join('|'),b,Array.from(y.memberNames).sort().join('|')]));
  }
  assert.equal(r.total,seen.size,'joint solver must cover every feasible maintained pair before truncation');
 }
 checks++;
}
console.log(`Joint team checks passed: ${checks} scenarios, full enumeration oracle, locked cores, fourth candidate, conflict diagnostics, balance, rarity independence, investment, and actual 残虹＋安魂曲 roster.`);
