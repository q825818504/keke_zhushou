const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const scriptPaths = [...html.matchAll(/<script\s+src=["']([^"']+)["']/g)].map((match) => match[1]);
assert.ok(scriptPaths.length, "index.html must load its app scripts");
assert.equal(scriptPaths.at(-1), "app.js", "app.js must run after its data bundles");
assert.ok(scriptPaths.indexOf("data/knowledge/team_templates.js") < scriptPaths.indexOf("app.js"), "team templates must load before app.js");

for (const relativePath of scriptPaths) {
  const absolutePath = path.join(root, relativePath);
  assert.ok(fs.existsSync(absolutePath), `missing script: ${relativePath}`);
  new vm.Script(fs.readFileSync(absolutePath, "utf8"), { filename: relativePath });
}

const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const toastLookup = app.indexOf('const toast = $("#toast")');
assert.ok(toastLookup >= 0, "app.js must initialize its toast element");
assert.ok(app.indexOf("const $ = (selector, scope = document) => scope.querySelector(selector);") < toastLookup, "$ selector helper must exist before startup uses it");
assert.match(app, /let userTeamTeamCount = userTeamSavedState\.teamCount === 2 \? 2 : 1;/, "team count must initialize before rendering the team route");

const sandbox = { window: {} };
vm.createContext(sandbox);
for (const relativePath of scriptPaths.slice(0, -1)) {
  vm.runInContext(fs.readFileSync(path.join(root, relativePath), "utf8"), sandbox, { filename: relativePath });
}

const characters = Object.values(sandbox.window.characterKnowledge || {}).filter((entry) => entry?.name);
const teams = sandbox.window.teamTemplateKnowledge?.teams || [];
assert.ok(characters.length > 0, "local character data must not be empty");
assert.ok(sandbox.window.characterKnowledge?.zhenhong?.name === "真红", "the starter character record must be available");
assert.ok((sandbox.window.arcDriveKnowledge?.items || []).length > 0, "arc drive catalog must not be empty");
assert.ok((sandbox.window.skyCurtainKnowledge?.items || []).length > 0, "sky curtain catalog must not be empty");
assert.ok((sandbox.window.driverBlockKnowledge?.items || []).length > 0, "driver block catalog must not be empty");
assert.ok(teams.length > 0, "team template catalog must not be empty");

const characterIds = new Set(characters.map((entry) => entry.id));
const invalidTeamReferences = teams.flatMap((team) => (team.member_character_ids || []).filter((id) => !characterIds.has(id)));
assert.equal(invalidTeamReferences.length, 0, "team templates must only reference local characters");

const iconSelectorStart = app.indexOf("function findCharacterIcon(");
assert.ok(iconSelectorStart >= 0, "character icons must be selected by character identity");
const iconSelectorEnd = app.indexOf("const characterData", iconSelectorStart);
vm.runInContext(app.slice(iconSelectorStart, iconSelectorEnd), sandbox);
const selectedIconHashes = new Map();
for (const character of characters) {
  const ownIcon = character.assets?.find((asset) => asset.type === "character_icon" && path.basename(asset.local_path || "").toLowerCase().startsWith(`${character.id}-icon.`));
  assert.ok(ownIcon, `${character.name}: expected a character-specific icon asset`);
  const selectedIcon = sandbox.findCharacterIcon(character);
  assert.equal(selectedIcon?.local_path, ownIcon.local_path, `${character.name}: must use its own icon, not the first related-character icon`);
  const iconPath = path.join(root, ownIcon.local_path);
  assert.ok(fs.existsSync(iconPath), `${character.name}: icon file must exist`);
  const hash = crypto.createHash("sha256").update(fs.readFileSync(iconPath)).digest("hex");
  assert.ok(!selectedIconHashes.has(hash), `${character.name}: icon image duplicates ${selectedIconHashes.get(hash)}`);
  selectedIconHashes.set(hash, character.name);
}

// Exercise the data resolver without starting a browser or the DOM-based app.
const resolverStart = app.indexOf("function resolveRecommendedCassette(");
assert.ok(resolverStart >= 0, "recommended cassettes must resolve shared catalog data");
const resolverEnd = app.indexOf("\nfunction ", resolverStart + 1);
assert.ok(resolverEnd > resolverStart);
vm.runInContext("const skyCurtainCatalog = window.skyCurtainKnowledge;\n" + app.slice(resolverStart, resolverEnd), sandbox);
const resolveCassette = sandbox.resolveRecommendedCassette;
const curtains = sandbox.window.skyCurtainKnowledge.items;
const charactersWithCassette = characters.filter((character) => character.recommended?.cassette);
assert.ok(charactersWithCassette.length > 0);
for (const character of charactersWithCassette) {
  const original = character.recommended.cassette;
  const catalogItem = curtains.find((item) => item.id === original.id);
  assert.ok(catalogItem, `${character.name}: recommended cassette must reference the catalog`);
  const originalAcquisition = original.acquisition;
  const resolved = resolveCassette(character);
  assert.equal(resolved.acquisition, catalogItem.acquisition, `${character.name}: acquisition must match the shared catalog`);
  assert.equal(resolved.recommended_main_affixes, original.recommended_main_affixes, "character-specific affix recommendations must be preserved");
  assert.equal(original.acquisition, originalAcquisition, "resolving catalog data must not mutate the character snapshot");
}
assert.equal(resolveCassette({}), undefined, "characters without recommendations must remain supported");
assert.equal(resolveCassette({ recommended: { cassette: { id: "unlisted-cassette", acquisition: "角色页记录" } } }).acquisition, "角色页记录", "unlisted cassettes must retain their source acquisition");
assert.equal(resolveCassette({ recommended: { cassette: { id: curtains[0].id, acquisition: "旧摘要" } } }).acquisition, curtains[0].acquisition, "catalog acquisition must take precedence over stale character summaries");

console.log(`Smoke check passed: ${characters.length} characters, ${teams.length} team templates, all scripts resolve and parse.`);
console.log(`Character icon checks passed: ${selectedIconHashes.size} unique, existing, identity-matched icon files.`);
console.log(`Cassette acquisition checks passed: ${charactersWithCassette.length} character recommendations match the shared catalog.`);
