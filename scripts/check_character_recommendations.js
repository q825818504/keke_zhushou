const assert = require("node:assert/strict");
const { chromium } = require(process.env.KEKE_PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const reload = async () => { await page.reload(); await page.waitForLoadState("networkidle"); };
    const edit = async () => {
      await page.locator("#userAdminButton").click();
      await page.locator(".recommendation-editor summary").click();
    };
    await page.goto("file:///D:/keke_zhushou/index.html");
    await page.waitForLoadState("networkidle");
    const sourceDefaults = await page.evaluate(() => JSON.parse(JSON.stringify(window.characterKnowledge)));
const defaults = await page.evaluate(() => Object.fromEntries(Object.values(characterData).map(data => [data.id, JSON.parse(JSON.stringify(data.knowledge))])));
    const correctTerminal = "每装配一个Ⅲ型驱动，使暴击伤害增加16%";
    assert.equal(sourceDefaults.zhenhong.terminal.description, correctTerminal, "Zhenhong source terminal must match the live guide");
    assert.equal(defaults.zhenhong.terminal.description, correctTerminal, "Zhenhong effective terminal must match the live guide");
    assert.equal(sourceDefaults.zhenhong.recommended.cassette.terminal.description, correctTerminal, "nested source terminal must be corrected too");
    assert.equal(defaults.zhenhong.recommended.cassette.terminal.description, correctTerminal, "nested effective terminal must be corrected too");
    assert.equal(Object.keys(defaults).length, 25, "all 25 effective role defaults must load");
    await page.evaluate(() => localStorage.setItem("keke-character-builds-v1", JSON.stringify({ zhenhong: { weapon: null, cassette: null } })));
    await reload();
    assert.deepEqual(await page.evaluate(() => Object.fromEntries(Object.values(characterData).map(data => [data.id, data.knowledge]))), defaults, "rolled-back overrides cannot clear defaults");
    await edit();
    assert.equal(await page.locator("#roleVersion, [data-mode], #submitReviewButton").count(), 0);
    const alternatives = await page.evaluate(() => ({
      weapon: arcDriveCatalog.items.find(item => item.id !== activeKnowledge.recommended.weapon.id),
      cassette: skyCurtainCatalog.items.find(item => item.id !== activeKnowledge.recommended.cassette.id)
    }));
    await page.locator('[data-recommendation-kind="weapon"]').selectOption(alternatives.weapon.id);
    assert.deepEqual(await page.evaluate(() => activeKnowledge.recommended.cassette), defaults.zhenhong.recommended.cassette, "editing weapon cannot change cassette");
    await reload();
    assert.deepEqual(await page.evaluate(() => activeKnowledge.recommended), defaults.zhenhong.recommended, "unsaved preview must not overwrite defaults");
    await edit();
    await page.locator('[data-recommendation-kind="weapon"]').selectOption(alternatives.weapon.id);
    await page.locator("[data-save-recommendation]").click();
    await reload();
    assert.equal(await page.evaluate(() => activeKnowledge.recommended.weapon.id), alternatives.weapon.id);
    assert.deepEqual(await page.evaluate(() => activeKnowledge.recommended.cassette), defaults.zhenhong.recommended.cassette);
    await edit();
    await page.locator('[data-recommendation-kind="cassette"]').selectOption(alternatives.cassette.id);
    await page.locator("[data-save-recommendation]").click();
    await reload();
    assert.equal(await page.evaluate(() => activeKnowledge.recommended.cassette.id), alternatives.cassette.id);
    assert.equal(await page.evaluate(() => activeKnowledge.recommended.weapon.id), alternatives.weapon.id);
    assert.ok((await page.locator("#userTabPanel").innerText()).includes(alternatives.cassette.name));
    const effective = await page.evaluate(() => Object.fromEntries(Object.values(characterData).map(data => [data.id, data.knowledge])));
    for (const [id, original] of Object.entries(defaults)) {
      if (id !== "zhenhong") assert.deepEqual(effective[id], original, `${id}: untouched role remains identical`);
      else assert.deepEqual({ ...effective[id], recommended: original.recommended }, original, "only recommended equipment may change");
    }
    assert.deepEqual(await page.evaluate(() => window.characterKnowledge), sourceDefaults, "imported source data must never mutate");
    await edit();
    await page.locator("[data-reset-recommendation]").click();
    assert.deepEqual(await page.evaluate(() => activeKnowledge.recommended), defaults.zhenhong.recommended, "restore must recover every default field, including affixes and terminal");
    await reload();
    assert.deepEqual(await page.evaluate(() => activeKnowledge.recommended), defaults.zhenhong.recommended);
    await page.locator("#userAdminButton").click();
    const reactions = await page.evaluate(() => Object.values(allKnowledge).map(character => ({
      name: character.name,
      entries: window.esperCycleKnowledge.cycles.flatMap(cycle => cycle.enhancements.filter(entry => entry.character_id === character.id).map(entry => ({ name: cycle.name, description: entry.description })))
    })));
    for (const role of reactions) {
      await page.locator(`[data-character="${role.name}"]`).click();
      const text = await page.locator("#roleReactionEnhancements").innerText();
      if (!role.entries.length) assert.equal(text.trim(), "无", role.name);
      else for (const entry of role.entries) assert.ok(text.includes(entry.name) && text.includes(entry.description), role.name);
    }
    assert.deepEqual(await page.evaluate(() => window.characterKnowledge), sourceDefaults, "reaction display cannot rewrite character facts");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".recommendation-editor summary").click();
    assert.equal(await page.locator('[data-recommendation-kind="weapon"]').isVisible(), true);
    await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error("quota"); }; });
    await page.locator('[data-recommendation-kind="weapon"]').selectOption(alternatives.weapon.id);
    await page.locator("[data-save-recommendation]").click();
    assert.equal(await page.locator("#recommendationStatus").innerText(), "保存失败");
    assert.deepEqual(errors, []);
    console.log("Recommendation checks passed: 25 unchanged defaults, old overrides ignored, explicit edit/save/reload, unsaved preview, untouched equipment/characters, exact reset including affixes and terminal, 25 reaction displays, narrow controls and storage error feedback.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
