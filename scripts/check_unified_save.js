// Run the real save binding and recommendation store without touching user data.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('app.js', 'utf8');
const start = source.indexOf('function bindSave()');
const binding = source.slice(start, source.indexOf('\nfunction bindImpact()', start));
async function check(fail) {
  const storage = new Map(), callbacks = {}, events = [], requests = [], notices = [];
  const knowledge = {id:'nanali', name:'娜娜莉', basic:{summary:'unchanged'}, recommended:{
    weapon:{id:'w', name:'推荐弧盘'}, cassette:{id:'c',name:'推荐卡带',
      recommended_main_affixes:[{name:'暴击伤害', priority:5}], recommended_sub_affixes:[{name:'暴击率',priority:4}]}}};
  const fields = {'#roleName':'娜娜莉','#roleRarity':'S','#roleElement':'灵','#roleCassetteType':'等离子','#rolePosition':'主C','#roleStation':'前排','#roleRating':'T0'};
  const elements = Object.fromEntries(Object.entries(fields).map(([id,value])=>[id,{value}]));
  elements['#saveDraftButton'] = {disabled:false};
  elements['#editorCard'] = {inert:false};
  elements['#guideManagerView'] = {hidden:true};
  for (const [id, element] of Object.entries(elements)) element.addEventListener=(type,fn)=>callbacks[id+':'+type]=fn;
  const window = {characterKnowledge:{nanali:structuredClone(knowledge)}, characterOverrides:{characters:{}},
    dispatchEvent:e=>events.push(e.type), KekeAdminBridge:{ready:Promise.resolve(true), connected:true,
      waitForWrites:async()=>{}, saveCharacter:async(id,patch,recommended)=>{
        requests.push(structuredClone({id,patch,recommended})); if(fail)throw Error('isolated failure');
      }}};
  const context = {window, Event, selectedCharacter:'娜娜莉',characterData:{'娜娜莉':{knowledge}},allKnowledge:{nanali:{basic:{}}},
    localRoleBasicOverrides:{},roleBasicStorageKey:'basics',localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    $:id=>elements[id], renderCharacterCards:()=>{},applyCharacter:()=>{},setText:()=>{},notify:message=>notices.push(message),
    document:{body:{classList:{contains:()=>false}}}, recommendedAffixes:(cassette,kind)=>cassette['recommended_'+kind+'_affixes'],
    normalizeAffixPriority:value=>Math.min(5,Math.max(1,Math.round(value||1)))};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('character_recommendations.js','utf8'),context);
  vm.runInContext(binding+';bindSave();',context);
  await callbacks['#saveDraftButton:click']();
  assert.equal(requests.length,1);
  assert.equal(requests[0].recommended.cassette.recommended_main_affixes[0].priority,5);
  assert.equal(requests[0].recommended.cassette.recommended_sub_affixes[0].priority,4);
  assert.equal(requests[0].recommended.weapon.id,'w');
  assert.equal(elements['#saveDraftButton'].disabled,false);
  assert.equal(elements['#editorCard'].inert,false);
  if(fail){
    assert.equal(events.includes('keke-role-saved'),false);
    assert(storage.has('keke-role-recommendations-v2'));
    assert(notices.some(message=>message.includes('失败')));
  } else {
    assert(events.includes('keke-role-saved'));
    assert.equal(storage.has('keke-role-recommendations-v2'),false);
    const restarted = {window:{characterKnowledge:window.characterKnowledge,characterOverrides:window.characterOverrides},localStorage:context.localStorage};
    vm.createContext(restarted);vm.runInContext(fs.readFileSync('character_recommendations.js','utf8'),restarted);
    const loaded = restarted.window.CharacterRecommendations.createKnowledge(knowledge);
    assert.equal(loaded.recommended.cassette.recommended_main_affixes[0].priority,5);
  }
  elements['#guideManagerView'].hidden=false;
  let submitted=false;elements['#guideForm']={requestSubmit:()=>submitted=true};
  await callbacks['#saveDraftButton:click']();assert(submitted);
}
async function checkUserRefresh() {
  const handlers = {}, state = new Map();let tick,version='old',reloads=0;
  const context = {window:{addEventListener:(name,fn)=>handlers[name]=fn},document:{addEventListener:()=>{}},
    sessionStorage:{getItem:k=>state.get(k)||null,setItem:(k,v)=>state.set(k,v),removeItem:k=>state.delete(k)},
    fetch:async()=>({ok:true,json:async()=>({version})}),setInterval:fn=>tick=fn,
    userActiveRoute:'characters',selectedCharacter:'娜娜莉',userActiveTab:'build',
    location:{reload:()=>reloads++},characterData:{},applyCharacter:()=>{},showUserRoute:()=>{}};
  vm.createContext(context);vm.runInContext(fs.readFileSync('desktop/user_chrome.js','utf8'),context);
  handlers.DOMContentLoaded();await new Promise(resolve=>setImmediate(resolve));
  await tick();assert.equal(reloads,0);
  version='updated';await tick();assert.equal(reloads,1);
  assert.deepEqual(JSON.parse(state.get('keke-desktop-view')),{route:'characters',character:'娜娜莉',tab:'build'});
}
(async()=>{await check(false);await check(true);await checkUserRefresh();console.log('Unified save passed: basics + recommendations, restart, failure retention, guide submission, and user live refresh.');})().catch(error=>{console.error(error);process.exitCode=1;});
