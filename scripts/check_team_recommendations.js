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
  if (file !== "app.js") vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), sandbox);
}

// Load only the data model and pure solver functions; no DOM or browser startup.
vm.runInContext(app.slice(0, app.indexOf("const userTeamSavedState")), sandbox);
vm.runInContext(app.slice(app.indexOf("const userTeamElementRing"), app.indexOf("function notify(")), sandbox);
vm.runInContext(`
  const userTeamNameById = Object.fromEntries(Object.entries(characterData).map(([name, data]) => [data.id, name]));
  let userTeamOwnedNames = new Set(Object.keys(characterData));
  let userTeamInvestmentByCharacterId = {};
  let userTeamGoal = "均衡";
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
  assert.ok(secondPlans.length > 0, "each first candidate must allow a remaining second team in the full roster");
  for (const second of secondPlans) {
    assert.equal(second.memberNames.length, 4);
    assert.ok(second.memberNames.every((name) => !blocked.has(name)), "teams must not share members");
  }
}

const lockedFirst = recommend("真红", new Set(["小吱"]));
assert.ok(lockedFirst.length);
assert.ok(lockedFirst.every((plan) => plan.coreName === "真红" && !plan.memberNames.includes("小吱")));
const lockedSecond = recommend("小吱", new Set(lockedFirst[0].memberNames));
assert.ok(lockedSecond.length);
assert.ok(lockedSecond.every((plan) => plan.coreName === "小吱" && plan.memberNames.every((name) => !lockedFirst[0].memberNames.includes(name))));

for (const goal of ["均衡", "速切", "生存"]) {
  vm.runInContext("userTeamGoal = " + JSON.stringify(goal), sandbox);
  assert.ok(recommend().every((plan) => plan.memberNames.length === 4));
}
setPool([]);
assert.equal(recommend().length, 0, "empty pool must not imply ownership of every character");
setPool(["真红"]);
assert.equal(recommend()[0].missing, 3, "one owned core must produce an honest partial candidate");
setPool(["阿德勒", "早雾", "伊洛伊", "哈尼娅"]);
assert.equal(recommend().length, 0, "support-only roster must not invent a main DPS");
setPool(["真红", "早雾", "阿德勒", "浔"]);
const limited = recommend();
assert.ok(limited.length);
assert.ok(limited.every((plan) => plan.candidateKind === "rule" && plan.memberNames.every((name) => ["真红", "早雾", "阿德勒", "浔"].includes(name))));

console.log("Team recommendation checks passed: automatic cores, two-team exclusion, manual locks, preferences, empty/partial/support-only pools, and rule fallback.");
