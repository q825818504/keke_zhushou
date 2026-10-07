const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const context = { window: {} };
vm.runInNewContext(fs.readFileSync("admin_bridge.js", "utf8"), context, { filename: "admin_bridge.js" });
const merge = context.window.KekeAdminBridge.mergeBrowserBackups;
const result = merge({
  team_overrides: { edits: { teamA: { id: "teamA", title: "current" }, teamB: { id: "teamB", title: "remove" } }, removed: ["teamC"] },
  character_recommendations: { roleA: { weapon: { id: "current-weapon" }, cassette: { id: "current-cassette" } } },
  character_basics: { roleA: { name: "current name", basic: { role: "主C", rating: "T0" } } },
  drive_layouts: [{ id: "roleA", data_base64: "current-image" }, { id: "roleB", data_base64: "other-image" }]
}, {
  team_overrides: { edits: { teamA: { id: "teamA", title: "imported" } }, removed: ["teamB"] },
  character_recommendations: { roleA: { weapon: { id: "imported-weapon" } } },
  character_basics: { roleA: { name: "imported name", basic: { element: "光" } } },
  drive_layouts: [{ id: "roleA", data_base64: "imported-image" }]
});

assert.equal(result.team_overrides.edits.teamA.title, "imported", "imported team should win an ID conflict");
assert.equal("teamB" in result.team_overrides.edits, false, "imported removal should win an ID conflict");
assert.deepEqual([...result.team_overrides.removed].sort(), ["teamB", "teamC"]);
assert.equal(result.character_recommendations.roleA.weapon.id, "imported-weapon");
assert.equal(result.character_recommendations.roleA.cassette.id, "current-cassette", "unmentioned recommendation kind must remain");
assert.equal(result.character_basics.roleA.name, "imported name");
assert.deepEqual(JSON.parse(JSON.stringify(result.character_basics.roleA.basic)), { role: "主C", rating: "T0", element: "光" });
assert.equal(result.drive_layouts.find(item => item.id === "roleA").data_base64, "imported-image");
assert.equal(result.drive_layouts.find(item => item.id === "roleB").data_base64, "other-image");
console.log("Admin migration merge checks passed: imported conflicts win while unmentioned fields and records are preserved.");
