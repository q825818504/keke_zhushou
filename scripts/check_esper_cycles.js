const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const knowledge = JSON.parse(fs.readFileSync(path.join(root, "data/knowledge/esper_cycles.json"), "utf8"));
const roster = JSON.parse(fs.readFileSync(path.join(root, "data/mysqil/esper-cycles/roster.json"), "utf8"));
const sha = value => crypto.createHash("sha256").update(value).digest("hex");
const raw = fs.readFileSync(path.join(root, knowledge.source.raw_snapshot));
assert.equal(sha(raw), knowledge.source.snapshot_sha256, "source snapshot integrity");
assert.equal(knowledge.cycles.length, 8);
const enhancementCount = knowledge.cycles.reduce((n, c) => n + c.enhancements.length, 0);
assert.equal(enhancementCount, 23, "1.5 新增曳尔沐等强化后应为 23 条");
assert.equal(knowledge.coverage.enhancement_count, enhancementCount, "coverage 必须与实际条数一致");
assert.equal(roster.assets.length, 26);
for (const asset of roster.assets) assert.equal(sha(fs.readFileSync(path.join(root, asset.local_path))), asset.sha256, asset.local_path + " hash");
const sourceMain = raw.toString("utf8").match(/<main\b[^>]*>([\s\S]*?)<\/main>/)[1];
const decode = text => text.replace(/&#(x[0-9a-f]+|[0-9]+);/gi, (_, value) => String.fromCodePoint(value[0].toLowerCase() === "x" ? parseInt(value.slice(1), 16) : parseInt(value, 10)))
  .replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&apos;/g, "'").replace(/&nbsp;/g, " ");
const sourceText = decode(sourceMain.replace(/<(script|style|svg)\b[^>]*>[\s\S]*?<\/\1>/gi, "").replace(/<[^>]*>/g, "")).replace(/\s+/g, "");
// 来源逐字对账只覆盖有 wiki 原文的条目；1.4/1.5 新增角色的强化单独标记为 local。
const localEnhancements = knowledge.cycles.flatMap(c => c.enhancements.filter(e => e.origin === "local"));
const importedText = [knowledge.title, knowledge.subtitle, knowledge.system_heading, knowledge.system_description,
  ...knowledge.cycles.flatMap(c => [c.name, ...c.attributes.map(a => a.name), c.description, c.enhancement_heading || "",
    ...c.enhancements.filter(e => e.origin !== "local").flatMap(e => [e.character_name, e.label, e.description])])].join("").replace(/\s+/g, "");
assert.equal(importedText, sourceText, "independent raw HTML reconciliation includes every text and numeric token");
for (const entry of localEnhancements) {
  assert.ok(entry.character_id && entry.character_name && entry.description, "本地新增强化必须自描述");
  assert.ok((entry.source_note || "").length > 20, "本地新增强化必须写明依据，不得冒充来源原文");
}
assert.equal(knowledge.coverage.local_enhancement_count, localEnhancements.length, "本地维护条目数必须与 coverage 一致");
for (const cycle of knowledge.cycles) for (const entry of cycle.enhancements) {
  assert.ok(entry.image && entry.image.local_path, `${cycle.name}/${entry.character_name} 缺少强化图标，页面渲染会崩`);
}
const sandbox = {window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,"data/knowledge/esper_cycles.js"),"utf8"),sandbox);
assert.deepEqual(JSON.parse(JSON.stringify(sandbox.window.esperCycleKnowledge)),knowledge, "browser bundle matches JSON");
const html = fs.readFileSync(path.join(root,"index.html"),"utf8");
const app = fs.readFileSync(path.join(root,"app.js"),"utf8");
assert.ok(html.indexOf("data/knowledge/esper_cycles.js") < html.indexOf('src="app.js"'));
assert.ok(app.includes("window.esperCycleKnowledge?.cycles"),"team solver consumes reference definitions");
assert.equal(knowledge.source.license, "CC BY-NC-SA 4.0");
console.log("Esper-cycle checks passed: exact independent source text, all numeric tokens, 8 reactions, 23 passives, 26 verified assets, JSON/JS parity and shared solver definitions.");
