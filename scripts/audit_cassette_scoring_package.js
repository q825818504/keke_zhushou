const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "build", "desktop", "public");
const output = process.env.KEKE_TEST_EXE || path.join(root, "dist", "windows", "test-v1.5", "KekeAssistant.exe");
const manifest = JSON.parse(fs.readFileSync(path.join(publicRoot, "public-manifest.json"), "utf8"));
const html = fs.readFileSync(path.join(publicRoot, "index.html"), "utf8");
const publicApp = fs.readFileSync(path.join(publicRoot, "app.js"), "utf8");
const releaseState = JSON.parse(fs.readFileSync(path.join(root, "desktop", "release-state.json"), "utf8"));

assert.equal(manifest.version, "1.5", "the generated local package manifest must use V1.5");
for (const name of ["cassette_scoring.js", "role_build.js", "app.js", "loadout_optimizer.js", "loadout_worker.js"]) {
  const file = path.join(publicRoot, name);
  assert.ok(fs.existsSync(file), `${name} must be included in the user bundle`);
  const digest = crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
  assert.equal(manifest.files[name], digest, `${name} must match the public manifest hash`);
}
assert.ok(html.indexOf('src="cassette_scoring.js"') < html.indexOf('src="role_build.js"'), "the scorer must load before the role-build page");
assert.match(publicApp, /const characterData\s*=/, "the compiled user bundle must retain role recommendations for scoring");
for (const name of ["role_build.js", "cassette_scoring.js", "loadout_optimizer.js", "loadout_worker.js"]) assert.equal(fs.readFileSync(path.join(publicRoot,name),"utf8"),fs.readFileSync(path.join(root,name),"utf8"),`${name} in the bundle must match the current source`);
assert.ok(!publicApp.includes("showRoleManagement"), "the user bundle must not include management-only functions");
assert.ok(fs.existsSync(output) && fs.statSync(output).size > 10_000_000, "the local V1.5 test EXE must be built");
assert.equal(releaseState.last_published, "1.4", "building the local test package must not publish or advance release metadata");
assert.equal(releaseState.config_revision, 14, "the public configuration revision must remain unchanged");
if(!process.env.KEKE_TEST_EXE){
  const windows=path.join(root,'dist','windows');
  const testExecutables=fs.readdirSync(windows,{withFileTypes:true})
    .filter(row=>row.isDirectory() && row.name.startsWith('test-v1.5'))
    .flatMap(row=>fs.readdirSync(path.join(windows,row.name)).filter(name=>name.endsWith('.exe')).map(name=>path.join(windows,row.name,name)));
  assert.deepEqual(testExecutables,[output],'V1.5 local testing has exactly one fixed EXE');
}
for(const name of ['data/resources/characters/ling/characters/ling-icon.webp','data/resources/encyclopedia/cassettes/shiluo-guangmang/blue.webp']){
  const image=path.join(publicRoot,name);
  assert.ok(fs.existsSync(image),`native 零 loadout image missing: ${name}`);
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(image)).digest('hex'),manifest.files[name]);
}
const buildSource=fs.readFileSync(path.join(root,'role_build.js'),'utf8');
const driverAssets=[...new Set(buildSource.match(/data\/resources\/encyclopedia\/driver_blocks\/site\/images\/drivers\/[^" ]+\.webp/g))];
assert.ok(driverAssets.length>=36,'all three qualities and supported shapes must have artwork bounds');
for(const name of driverAssets){
  assert.ok(fs.existsSync(path.join(publicRoot,name)),`driver image missing: ${name}`);
  const digest=crypto.createHash('sha256').update(fs.readFileSync(path.join(publicRoot,name))).digest('hex');
  assert.equal(manifest.files[name],digest,`driver image hash mismatch: ${name}`);
}

console.log(`Local V1.5 package audit passed: ${manifest.files ? Object.keys(manifest.files).length : 0} assets; scoring module and role data included; management code excluded; EXE ${(fs.statSync(output).size / 1024 / 1024).toFixed(1)} MiB; published release remains ${releaseState.last_published}.`);
