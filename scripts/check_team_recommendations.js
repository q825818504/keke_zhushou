const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
for (const [, file] of html.matchAll(/<script\s+src="([^"]+)"/g)) {
  if (file.startsWith('data/knowledge/') || ['character_recommendations.js','reactions.js'].includes(file)) vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), sandbox);
}

// Load only the data model and pure solver functions; no DOM or browser startup.
vm.runInContext(app.slice(0, app.indexOf("const userTeamSavedState")), sandbox);
vm.runInContext(app.slice(app.indexOf("const userTeamElementRing"), app.indexOf("function notify(")), sandbox);
vm.runInContext(`
  const userTeamNameById = Object.fromEntries(Object.entries(characterData).map(([name, data]) => [data.id, name]));
  let userTeamOwnedNames = new Set(Object.keys(characterData));
  let userTeamInvestmentByCharacterId = {};

`, sandbox);
vm.runInContext(app.slice(app.indexOf("function userTeamRoleKind("), app.indexOf("function userTeamMemberCard(")), sandbox);

const recommend = sandbox.userTeamRecommendPlans;
const setPool = (names) => vm.runInContext("userTeamOwnedNames = new Set(" + JSON.stringify(names) + ")", sandbox);
const allNames = Object.values(sandbox.window.characterKnowledge).map((record) => record.name);
const firstPlans = recommend();
assert.equal(firstPlans.length, 3, "no lock must still produce multiple candidates");
for (const plan of firstPlans) {
  assert.equal(plan.memberNames.length, 4);
  assert.ok(plan.memberNames.includes(plan.coreName));
  assert.ok(sandbox.userTeamCanPin(plan.coreName), "automatic core must be eligible");
  assert.equal(new Set(plan.memberNames).size, 4);
  assert.ok(plan.memberNames.every((name) => allNames.includes(name)));
  const blocked = new Set(plan.memberNames);
  const secondPlans = recommend("", blocked);
  for (const second of secondPlans) {
    assert.equal(second.memberNames.length, 4);
    assert.ok(second.memberNames.every((name) => !blocked.has(name)), "teams must not share members");
  }
}

const lockedFirst = recommend("真红", new Set(["小吱"]));
assert.ok(lockedFirst.every((plan) => plan.coreName === "真红" && !plan.memberNames.includes("小吱")));
if(lockedFirst.length){
 const lockedSecond = recommend("小吱", new Set(lockedFirst[0].memberNames));
 assert.ok(lockedSecond.every((plan) => plan.coreName === "小吱" && plan.memberNames.every((name) => !lockedFirst[0].memberNames.includes(name))));
}

setPool([]);
assert.equal(recommend().length, 0, "empty pool must not imply ownership of every character");
setPool(["真红"]);
assert.equal(recommend().length, 0, "a partial pool must not invent a candidate");
setPool(["阿德勒", "早雾", "伊洛伊", "哈尼娅"]);
assert.equal(recommend().length, 0, "support-only roster must not invent a main DPS");
setPool(["真红", "早雾", "阿德勒", "浔"]);
const limited = recommend();
assert.ok(limited.every((plan) => plan.candidateKind === "source" && plan.sourceRecord && plan.memberNames.every((name) => ["真红", "早雾", "阿德勒", "浔"].includes(name))));
setPool(allNames);
const fixtureNames=allNames.slice(0,8);
const record=(names,id)=>({id,source_core_character_id:vm.runInContext('characterData['+JSON.stringify(names[0])+'].id',sandbox),member_character_ids:names.map(n=>vm.runInContext('characterData['+JSON.stringify(n)+'].id',sandbox)),editorial:{active:true}});
const fixtures=[record(fixtureNames.slice(0,4),'fixture-first'),record(fixtureNames.slice(4),'fixture-second')];
sandbox.window.teamGuideStore={all:()=>fixtures};
const one=recommend(fixtureNames[0])[0];assert.equal(one.id,'fixture-first');
const two=recommend(fixtureNames[4],new Set(one.memberNames))[0];assert.equal(two.id,'fixture-second');assert(two.memberNames.every(n=>!one.memberNames.includes(n)));
fixtures[0].editorial.active=false;assert.equal(recommend(fixtureNames[0]).length,0);
sandbox.window.teamGuideStore={all:()=>[]};assert.equal(recommend().length,0,'no maintenance records must mean no generated teams');

console.log("Team recommendation checks passed: maintained sources only, dual-team exclusion, locks, inactive records and no empty/partial fallback.");
