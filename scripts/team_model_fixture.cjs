// Shared isolated data model for single and joint-team acceptance checks.
module.exports = function loadTeamModel() {
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const sandbox = { window: {}, localStorage: { getItem: () => null } };
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


return { sandbox, vm, app, root };
};
