const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "cassette_scoring.js"), "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: "cassette_scoring.js" });
const scoring = sandbox.window.KekeCassetteScoring;

assert.equal(scoring.weightForPriority(0), 0, "unselected affixes must not add weight");
assert.equal(scoring.weightForPriority(1), 0.4, "priority 1 remains positive");
assert.equal(scoring.weightForPriority(2), 0.55);
assert.equal(scoring.weightForPriority(3), 0.7);
assert.equal(scoring.weightForPriority(4), 0.85);
assert.equal(scoring.weightForPriority(5), 1);
assert.equal(scoring.canonicalAffix({ name: "攻击力", is_percent: true }), "攻击力百分比");
assert.equal(scoring.canonicalAffix({ name: "攻击力", is_percent: false }), "攻击力");
assert.equal(scoring.canonicalAffix("全伤害加成"), "通用伤害增强", "catalog and role-editor names for the generic damage stat must match");

const cassette = {
  recommended_main_affixes: [
    { name: "暴击伤害", priority: 5 },
    { name: "暴击率", priority: 4 }
  ],
  recommended_sub_affixes: [
    { name: "暴击率", priority: 5 },
    { name: "暴击伤害", priority: 4 },
    { name: "环合强度", priority: 3 },
    { name: "倾陷强度", priority: 2 },
    { name: "生命值百分比", priority: 1 },
    { name: "攻击力百分比", priority: 1 },
    { name: "防御力百分比", priority: 1 },
    { name: "攻击力", priority: 1 }
  ]
};
const catalogCassette = { sub_affix_pool: { items: [
  "暴击率", "暴击伤害", "环合强度", "倾陷强度", "生命值（% / 固定值）",
  "攻击力（% / 固定值）", "防御力（% / 固定值）"
] } };
const item = (label, main, subs) => ({
  category: "tape", label,
  main_stats: [{ name: main }],
  sub_stats: subs.map(name => ({ name, is_percent: /百分比/.test(name) }))
});
const lowSubs = ["生命值百分比", "攻击力百分比", "防御力百分比", "攻击力"];
const highSubs = ["暴击率", "暴击伤害", "环合强度", "倾陷强度"];
const main5WeakSubs = scoring.scoreItem(item("A", "暴击伤害", lowSubs), cassette, catalogCassette);
const main4StrongSubs = scoring.scoreItem(item("B", "暴击率", highSubs), cassette, catalogCassette);
assert.ok(Math.abs(main5WeakSubs.idealSubWeight - 3.1) < 1e-9, "the denominator must use the four best legal unique sub affixes");
assert.ok(Math.abs(main5WeakSubs.score - 80.6451612903) < 1e-6, "P5 main plus four P1 subs should score about 80.6");
assert.equal(main4StrongSubs.score, 91, "P4 main plus P5/P4/P3/P2 subs should score 91");
assert.ok(main4StrongSubs.score > main5WeakSubs.score, "stronger sub affixes can overcome a one-tier main difference");
assert.equal(scoring.qualityMultiplier({rarity:"S"}),1,"gold/S remains the existing baseline");
assert.equal(scoring.qualityMultiplier({rarity:"Purple"}),0.8,"purple/A gear carries 80% of the corresponding gold stat value");
assert.equal(scoring.qualityMultiplier({rarity:"B"}),0.6,"blue/B gear carries 60% of the corresponding gold stat value");
const purpleTape=scoring.scoreItem({...item("P","暴击伤害",lowSubs),rarity:"Epic"},cassette,catalogCassette);
const blueTape=scoring.scoreItem({...item("B","暴击伤害",lowSubs),rarity:"Rare"},cassette,catalogCassette);
assert.ok(Math.abs(purpleTape.score-main5WeakSubs.score*0.8)<1e-9,"cartridge main and sub score both scale to the purple stat values");
assert.ok(Math.abs(blueTape.score-main5WeakSubs.score*0.6)<1e-9,"cartridge main and sub score both scale to the blue stat values");
assert.ok(Math.abs(purpleTape.mainPoints-48)<1e-9 && Math.abs(purpleTape.subPoints-main5WeakSubs.subPoints*0.8)<1e-9,"the 60:40 components expose quality-adjusted values");

const offListMain = item("C", "生命值百分比", highSubs);
const ranked = scoring.rank([item("drive", "暴击率", highSubs), offListMain, item("A", "暴击伤害", lowSubs)], cassette, catalogCassette);
assert.equal(ranked.candidates.length, 2, "when a recommended main exists, only those items belong to the primary ranking");
assert.equal(ranked.candidates[0].item.label, "drive", "primary candidates must be sorted by score");
assert.equal(ranked.fallback.length, 1, "other main stats remain available as a separate fallback list");
assert.equal(ranked.fallback[0].mainPoints, 0, "an unselected main stat adds no score");
assert.equal(ranked.fallbackMode, false);

const noMainHit = scoring.rank([offListMain], cassette, catalogCassette);
assert.equal(noMainHit.fallbackMode, true, "all items become fallback candidates when no recommended main is owned");
assert.equal(noMainHit.candidates[0].mainPoints, 0);
assert.equal(noMainHit.candidates[0].subPoints, 40);
assert.equal(scoring.rank([{ category: "drive" }], cassette, catalogCassette).total, 0, "drive blocks must not be scored by the cassette 60:40 rule");

const publicBuilder = fs.readFileSync(path.join(__dirname, "..", "desktop", "prepare_public.py"), "utf8");
assert.match(publicBuilder, /cassette_scoring\.js/ , "the local user EXE build must copy the shared scorer");
const publicScriptOrder = publicBuilder.split(/\r?\n/).find(line => line.includes('scripts = "".join')) || "";
assert.ok(publicScriptOrder.indexOf('"cassette_scoring.js"') < publicScriptOrder.indexOf('"role_build.js"'), "the user bundle must load scoring before role build");

const driveCatalog = require('../data/knowledge/encyclopedia/driver_blocks.json').items[0];
const full = scoring.scoreDrive({sub_stats:highSubs.map(name=>({name}))},cassette,driveCatalog);
assert.equal(full.score,100);
assert.equal(scoring.scoreDrive({rarity:"purple",sub_stats:highSubs.map(name=>({name}))},cassette,driveCatalog).score,80,"purple drive substats scale by their measured 80% value");
assert.equal(scoring.scoreDrive({rarity:"blue",sub_stats:highSubs.map(name=>({name}))},cassette,driveCatalog).score,60,"blue drive substats scale by their measured 60% value");
assert.equal(scoring.scoreDrive({sub_stats:[]},cassette,driveCatalog),null);
const repeated = scoring.scoreDrive({sub_stats:Array(4).fill({name:'暴击率'})},cassette,driveCatalog);
assert.ok(repeated.score<33,'duplicate affixes cannot inflate scores');
const board = [[1,1],[1,2],[1,3],[1,4]];
const placed = (cells,column,score=100)=>({item:{cells,placement:{row:1,column}},score});
const result = scoring.scoreLoadout(100,[placed([[0,0],[0,1]],1)],board);
assert.equal(result.driveScore,50,'empty slots must lower graduation');
assert.equal(result.total,150);
assert.equal(result.graduation,75);
assert.equal(result.grade,'A');
assert.equal(scoring.scoreLoadout(100,[placed([[0,0],[0,1]],1),placed([[0,0],[0,1]],3)],board).total,200);
assert.equal(scoring.scoreLoadout(100,[placed([[0,0],[0,1],[0,2],[0,3]],1)],board).total,200,'partitioning the same cells into small blocks gives no extra points');
assert.equal(scoring.scoreLoadout(100,[placed([[0,0],[0,1]],1),placed([[0,0],[0,1]],2)],board),null,'overlap invalidates overall score');
assert.equal(scoring.scoreLoadout(100,[placed([[0,0],[0,1]],4)],board),null,'off-board cells invalidate overall score');
for(const [value,grade] of [[95,'ACE'],[94.99,'S'],[85,'S'],[70,'A'],[50,'B'],[49.99,'C']])assert.equal(scoring.grade(value),grade);
assert.equal(scoring.grade(undefined),null);
console.log('Scoring checks passed: existing 60:40 weights, drive affix normalization, duplicate handling, cell-weighted board, missing/invalid data and grade boundaries.');
