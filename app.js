const characterData = {
  真红: {
    id: "char_zenhong",
    position: "主 C · 驻场输出",
    version: "5.1.0",
    mode: "站场",
    summaryTitle: "真红是一个「站场输出核心」",
    summary: "来自本地角色资料的基础概览，技能、倍率、觉醒和养成数据均可继续展开查看。",
    reaction: "盈蓄",
    metrics: ["12 → 14", "6 → 8", "18 / 18"],
    slots: [
      ["主输出", "能力完全匹配", "100%", "green"],
      ["反应核心", "强化模式匹配", "92%", "green"],
      ["破韧副位", "缺少破韧标签", "54%", "amber"]
    ]
  },
  残虹: {
    id: "char_canhong",
    position: "副 C · 持续附着",
    version: "5.0.2",
    mode: "速切",
    summaryTitle: "残虹是一个「持续附着副位」",
    summary: "在短驻场窗口补充雷元素附着，并把剩余时间让给主输出。适配需要稳定触发失谐的反应体系。",
    reaction: "失谐",
    metrics: ["9 → 11", "5 → 7", "17 / 18"],
    slots: [
      ["副输出", "站场时间匹配", "96%", "green"],
      ["反应触发", "附着条件匹配", "89%", "green"],
      ["主输出", "站场时间不足", "38%", "amber"]
    ]
  },
  盈蓄: {
    id: "char_yingxu",
    position: "辅助 · 全队增益",
    version: "5.1.0",
    mode: "后台",
    summaryTitle: "盈蓄是一个「后台增益辅助」",
    summary: "通过后台持续提供全队增益，放大体系的反应收益。自身不需要占用主输出的站场窗口。",
    reaction: "盈蓄",
    metrics: ["16 → 18", "8 → 10", "18 / 18"],
    slots: [
      ["增益辅助", "全队增益匹配", "100%", "green"],
      ["反应核心", "强化模式匹配", "94%", "green"],
      ["主输出", "不承担输出", "22%", "amber"]
    ]
  },
  霜鹭: {
    id: "char_shuanglu",
    position: "辅助 · 护盾保护",
    version: "4.9.1",
    mode: "后台",
    summaryTitle: "霜鹭是一个「后台保护辅助」",
    summary: "用护盾和抗打断保护主输出完成完整循环，适合容错要求高、需要稳定站场的体系。",
    reaction: "冻结",
    metrics: ["8 → 9", "4 → 5", "18 / 18"],
    slots: [
      ["保护辅助", "护盾能力匹配", "100%", "green"],
      ["反应辅助", "元素条件匹配", "81%", "green"],
      ["主输出", "不承担输出", "18%", "amber"]
    ]
  }
};

const importedKnowledge = window.characterKnowledge?.zhenhong || null;
const importedAssetUrl = (asset) => {
  const path = asset?.local_path || "";
  return path.startsWith("data/") ? path : "data/mysqil/characters/zhenhong/" + path;
};
if (importedKnowledge) {
  const facts = importedKnowledge.mechanism_facts || {};
  const basic = importedKnowledge.basic || {};
  const manual = importedKnowledge.manual_review || [];
  const element = basic.element || manual.find((item) => item.field === "attribute")?.value || "待确认";
  const portrait = importedKnowledge.assets?.find((asset) => asset.type === "character_portrait");
  const icon = importedKnowledge.assets?.find((asset) => asset.type === "character_icon" && asset.local_path.endsWith("zhenhong-icon.webp"));

  characterData.真红 = {
    ...characterData.真红,
    id: importedKnowledge.id,
    position: "主 C · 驻场输出",
    rarity: basic.rarity || "S",
    cassetteType: basic.cassette_type || "—",
    rating: basic.rating || "—",
    station: "站场",
    version: "待审核",
    mode: "站场",
    summaryTitle: "真红是一个「光属性盈蓄核心」",
    summary: "这是从本地知识样板加载的真红资料。真红是光属性站场输出，技能、倍率和盈蓄强化均已导入。",
    reaction: facts.primary_reaction || "盈蓄",
    element,
    portrait: portrait ? importedAssetUrl(portrait) : "",
    icon: icon ? importedAssetUrl(icon) : "",
    reactionText: facts.reaction_enhancement_text || "暂无本地反应强化原文",
    reactionChain: facts.reaction_chain || [],
    requiredAttributes: facts.required_teammate_attributes || [],
    sourceUrl: importedKnowledge.provenance?.source_url || "",
    assets: importedKnowledge.assets || [],
    metrics: ["9", "34", "6"],
    slots: [
      ["基础资料", "稀有度、属性、弧盘类型、定位", "已导入", "green"],
      ["技能与倍率", "9 个技能条目、34 组参数", "已导入", "green"],
      ["觉醒与养成", "6 个觉醒、11 种材料", "已导入", "green"],
      ["推荐配置", "武器与卡带", "已导入", "green"],
      ["来源快照", "原始页面与图片本地保存", "已保存", "green"]
    ]
  };
}
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const toast = $("#toast");
const toastText = $("#toastText");
let toastTimer;
let selectedCharacter = "真红";
let currentMode = "站场";

function notify(message) {
  toastText.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

function setText(selector, text) {
  const element = $(selector);
  if (element) element.textContent = text;
}

function readBasicPreviewValues() {
  return {
    name: $("#roleName")?.value.trim() || "未命名角色",
    rarity: $("#roleRarity")?.value || "—",
    element: $("#roleElement")?.value || "—",
    cassetteType: $("#roleCassetteType")?.value.trim() || "—",
    position: $("#rolePosition")?.value || "—",
    station: $("#roleStation")?.value || "—",
    rating: $("#roleRating")?.value.trim() || "—"
  };
}

function syncPublicPreview() {
  const values = readBasicPreviewValues();
  setText("#editorCharacterName", values.name);
  const quickFacts = $("#quickFacts");
  if (!quickFacts) return;
  quickFacts.innerHTML = '<div><span>稀有度</span><b>' + values.rarity + '</b></div><div><span>属性</span><b>' + values.element + '</b></div><div><span>弧盘类型</span><b>' + values.cassetteType + '</b></div><div><span>定位</span><b>' + values.position + '</b></div><div><span>站位</span><b>' + values.station + '</b></div><div><span>强度评级</span><b>' + values.rating + '</b></div>';
}

function bindBasicPreview() {
  ["#roleName", "#roleRarity", "#roleElement", "#roleCassetteType", "#rolePosition", "#roleStation", "#roleRating", "#roleVersion"].forEach((selector) => {
    const element = $(selector);
    if (!element) return;
    ["input", "change"].forEach((eventName) => element.addEventListener(eventName, () => {
      syncPublicPreview();
      setText("#draftLabel", "草稿未保存");
    }));
  });
}
function updateSlotList(slots) {
  const list = $("#slotList");
  list.innerHTML = slots.map(([name, reason, score, tone]) => `
    <div class="slot-row">
      <span class="slot-name"><i class="slot-dot ${tone}"></i>${name}</span>
      <span class="slot-reason">${reason}</span>
      <b class="slot-score ${tone === "amber" ? "muted" : ""}">${score}</b>
    </div>`).join("");
}

function renderRecommended(knowledge) {
  const recommended = knowledge.recommended || {};
  const weapon = $("#recommendedWeapon");
  if (weapon && recommended.weapon) {
    weapon.innerHTML = `<div class="recommendation-card"><img src="${importedAssetUrl({ local_path: recommended.weapon.asset })}" alt="${recommended.weapon.name}"><div><span>推荐武器 · ${recommended.weapon.rating}</span><b>${recommended.weapon.name}</b><small>来源：角色详情页</small></div></div>`;
  }
  const cassette = $("#recommendedCassette");
  if (cassette && recommended.cassette) {
    const data = recommended.cassette;
    cassette.innerHTML = `<div class="recommendation-card"><img src="${importedAssetUrl({ local_path: data.icon })}" alt="${data.name}"><div><span>推荐卡带 · ${data.category} · ${data.element}</span><b>${data.name}</b><small>${data.cassette_type} · 2/4 件套效果已录入</small></div></div>`;
  }
}

function renderBaseStats(knowledge) {
  const target = $("#baseStats");
  if (!target) return;
  const stats = knowledge.base_stats?.stats || [];
  const levels = [1, 30, 50, 70, 80];
  target.innerHTML = `<div class="stats-table"><div class="stats-row stats-head"><span>属性</span>${levels.map((level) => `<span>Lv.${level}</span>`).join("")}</div>${stats.map((stat) => `<div class="stats-row"><b>${stat.name}</b>${levels.map((level) => `<span>${Number(stat.values[level - 1]).toLocaleString()}</span>`).join("")}</div>`).join("")}</div>`;
}

function renderSkills(knowledge) {
  const target = $("#skillsList");
  if (!target) return;
  target.innerHTML = (knowledge.skills || []).map((skill, index) => `
    <details class="skill-details" ${index === 0 ? "open" : ""}>
      <summary><span class="skill-category">${skill.category}</span><b>${skill.name}</b><small>${skill.parameters.length} 个倍率参数${skill.level_cap ? ` · Lv.${skill.level_cap}` : ""}</small></summary>
      <div class="skill-content">
        ${(skill.description_parts || []).map((part) => `<p><b>${part.name}</b>${part.text}</p>`).join("")}
        ${skill.parameters.length ? `<div class="parameter-table"><div class="parameter-head"><span>倍率/参数</span><span>Lv.1 → Lv.${skill.level_cap || 1}</span></div>${skill.parameters.map((parameter) => `<div class="parameter-row"><span>${parameter.label}</span><small>${parameter.values.join(" → ")}</small></div>`).join("")}</div>` : ""}
      </div>
    </details>`).join("");
}

function renderAwakenings(knowledge) {
  const target = $("#awakeningList");
  if (!target) return;
  target.innerHTML = (knowledge.awakenings || []).map((awakening, index) => `
    <article class="awakening-card"><img src="${importedAssetUrl({ local_path: awakening.asset })}" alt="觉醒 ${index + 1}"><div><b>${index + 1}. ${awakening.name}</b><p>${awakening.description}</p></div></article>`).join("");
}

function materialAsset(knowledge, id) {
  const icon = knowledge.cultivation?.material_catalog?.[id]?.icon;
  if (!icon) return "";
  const filename = icon.split("/").pop();
  const asset = (knowledge.assets || []).find((item) => item.local_path.endsWith(`/items/${filename}.webp`));
  return asset ? importedAssetUrl(asset) : "";
}

function skillTargetOptions(skill) {
  const levels = [...new Set([
    ...((skill.levels?.[0]?.level || 1) > 1 ? [1] : []),
    ...(skill.levels || []).map((step) => step.level)
  ])].sort((a, b) => a - b);
  return levels.length ? levels : [1];
}

function renderSkillTargets(knowledge) {
  const target = $("#skillTargets");
  if (!target) return;
  const skills = knowledge.cultivation?.skills || [];
  target.innerHTML = '<div class="skill-targets-head"><div><b>技能目标等级</b><small>每个技能单独设定，默认按该技能最高等级计算</small></div><span>' + skills.length + ' 项技能</span></div>' +
    '<div class="skill-target-grid">' + skills.map((skill, index) => {
      const levels = skillTargetOptions(skill);
      const max = Math.max(...levels);
      const fixed = levels.length === 1;
      return '<label class="skill-target-row"><span><b>' + skill.name + '</b><small>' + (fixed ? '固定等级 / 觉醒节点' : '独立目标 · 最高 Lv.' + max) + '</small></span><select data-skill-target="' + index + '"' + (fixed ? ' disabled' : '') + '>' +
        levels.map((level) => '<option value="' + level + '"' + (level === max ? ' selected' : '') + '>Lv.' + level + '</option>').join('') +
        '</select></label>';
    }).join('') + '</div>';
  target.querySelectorAll('select[data-skill-target]').forEach((select) => {
    select.addEventListener('change', () => calculateMaterials(knowledge));
  });
}

function readSkillTargets(knowledge) {
  return (knowledge.cultivation?.skills || []).map((skill, index) => {
    const levels = skillTargetOptions(skill);
    const select = document.querySelector('[data-skill-target="' + index + '"]');
    return {
      name: skill.name,
      target: Number(select?.value || Math.max(...levels)),
      max: Math.max(...levels)
    };
  });
}

function calculateMaterials(knowledge) {
  const targetLevel = Number($("#targetLevel")?.value || 80);
  const skillTargets = readSkillTargets(knowledge);
  const totals = new Map();
  const add = (id, amount) => totals.set(id, (totals.get(id) || 0) + amount);
  (knowledge.cultivation?.ascension || []).filter((step) => step.level <= targetLevel).forEach((step) => step.items.forEach((item) => add(item.id, item.amount)));
  (knowledge.cultivation?.skills || []).forEach((skill, index) => {
    const targetSkillLevel = skillTargets[index]?.target || 1;
    skill.levels.filter((step) => step.level <= targetSkillLevel).forEach((step) => step.items.forEach((item) => add(item.id, item.amount)));
  });
  const catalog = knowledge.cultivation?.material_catalog || {};
  const entries = [...totals.entries()].map(([id, amount]) => ({ id, amount, name: catalog[id]?.name || id, icon: materialAsset(knowledge, id) }));
  const target = $("#materialSummary");
  if (target) {
    const goalSummary = skillTargets.map((skill) => '<span>' + skill.name + ' Lv.' + skill.target + '</span>').join('');
    target.innerHTML = '<div class="material-summary-head"><span>目标：角色 Lv.' + targetLevel + ' · 各技能独立目标</span><b>' + entries.length + ' 种材料</b></div><div class="skill-goal-summary">' + goalSummary + '</div><div class="material-grid">' + entries.map((entry) => '<div class="material-card">' + (entry.icon ? '<img src="' + entry.icon + '" alt="' + entry.name + '">' : '') + '<div><b>' + entry.name + '</b><span>' + entry.amount.toLocaleString() + '</span></div></div>').join('') + '</div>';
  }
  setText("#impactSummary", 'Lv.' + targetLevel + ' / ' + skillTargets.length + ' 项技能独立计算');
  setText("#analysisState", "已汇总");
  setText("#metricMaterials", String(entries.length));
  return entries;
}

function recommendedAffixes(cassette, kind) {
  return cassette?.["recommended_" + kind + "_affixes"] || [];
}

function rankAffixes(items) {
  const groups = [];
  [...items].sort((a, b) => Number(b.priority) - Number(a.priority)).forEach((item) => {
    const priority = Number(item.priority) || 1;
    const group = groups.find((entry) => entry.priority === priority);
    if (group) group.names.push(item.name);
    else groups.push({ priority, names: [item.name] });
  });
  return groups;
}

function renderAffixRanking(items) {
  const groups = rankAffixes(items);
  if (!groups.length) return '<span class="affix-empty">尚未设置推荐</span>';
  return groups.map((group, index) => '<span class="affix-rank-group">' + group.names.join(" ≈ ") + '</span>' + (index < groups.length - 1 ? '<b class="affix-rank-separator">＞</b>' : '')).join('');
}

function readRecommendedAffixes(root, kind) {
  return [...root.querySelectorAll('[data-affix-option="' + kind + '"].is-selected')].map((button) => {
    const row = button.closest(".affix-editor-row");
    const input = row ? row.querySelector("[data-affix-priority]") : null;
    const priority = Math.min(9, Math.max(1, Number(input?.value) || 1));
    return { name: button.dataset.affixName, priority };
  });
}

function syncCassetteRecommendations(knowledge, root, rerenderEditor = false) {
  const cassette = knowledge.recommended?.cassette;
  if (!cassette || !root) return;
  cassette.recommended_main_affixes = readRecommendedAffixes(root, "main");
  cassette.recommended_sub_affixes = readRecommendedAffixes(root, "sub");
  renderCassette(knowledge);
  setText("#draftLabel", "草稿未保存");
  if (rerenderEditor) renderCassetteRecommendationEditor(knowledge);
}

function renderCassetteRecommendationEditor(knowledge) {
  const target = $("#cassetteRecommendationEditor");
  const cassette = knowledge.recommended?.cassette;
  if (!target || !cassette) return;
  const buildGroup = (kind, title, pool) => {
    const selected = new Map(recommendedAffixes(cassette, kind).map((item) => [item.name, item.priority]));
    return '<div class="affix-editor-group"><div class="affix-editor-group-head"><div><b>' + title + '</b><small>点击词条选择，再设置优先级</small></div><span>' + selected.size + ' 项已选</span></div><div class="affix-editor-options">' +
      pool.map((name) => {
        const isSelected = selected.has(name);
        const priority = selected.get(name) || 1;
        return '<div class="affix-editor-row"><button type="button" class="affix-choice pressable' + (isSelected ? ' is-selected' : '') + '" data-affix-option="' + kind + '" data-affix-name="' + name + '" aria-pressed="' + isSelected + '">' + (isSelected ? '✓ ' : '+ ') + name + '</button><label class="affix-priority"><span>优先级</span><input data-affix-priority type="number" min="1" max="9" value="' + priority + '"' + (isSelected ? '' : ' disabled') + '></label></div>';
      }).join("") + '</div></div>';
  };
  target.innerHTML = '<div class="affix-editor-note">这里只维护推荐，不改变原站记录的随机可出现词条池。</div>' +
    buildGroup("main", "推荐主属性", cassette.main_affix_pool || []) +
    buildGroup("sub", "推荐副属性", cassette.sub_affix_pool || []);
  if (target.dataset.bound === "true") return;
  target.dataset.bound = "true";
  target.addEventListener("click", (event) => {
    const button = event.target.closest("[data-affix-option]");
    if (!button) return;
    button.classList.toggle("is-selected");
    button.setAttribute("aria-pressed", button.classList.contains("is-selected") ? "true" : "false");
    const input = button.closest(".affix-editor-row")?.querySelector("[data-affix-priority]");
    if (input) input.disabled = !button.classList.contains("is-selected");
    syncCassetteRecommendations(knowledge, target, true);
  });
  target.addEventListener("change", (event) => {
    if (!event.target.matches("[data-affix-priority]")) return;
    syncCassetteRecommendations(knowledge, target);
  });
}

function renderCassette(knowledge) {
  const target = $("#cassetteDetails");
  const data = knowledge.recommended?.cassette;
  if (!target || !data) return;
  const terminal = data.terminal;
  const terminalMarkup = terminal ? '<section class="terminal-card"><div class="terminal-visual" aria-hidden="true">' + '<i></i>'.repeat(20) + '</div><div class="terminal-copy"><span class="terminal-kicker">终端</span><b>' + terminal.name + '</b><p>' + terminal.description + '</p><span class="terminal-effect">' + (terminal.effects || []).join(" · ") + '</span></div></section>' : '';
  target.innerHTML = '<div class="cassette-summary"><img src="' + importedAssetUrl({ local_path: data.icon }) + '" alt="' + data.name + '"><div><b>' + data.name + '</b><span>' + data.category + ' · ' + data.cassette_type + ' · ' + data.element + '属性</span><small>' + data.acquisition + '</small></div></div><div class="set-effects">' + data.set_effects.map((effect) => '<div><b>' + effect.pieces + '件套</b><span>' + effect.description + '</span></div>').join("") + '</div><div class="recommended-affixes"><div class="affix-section"><b>推荐主属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "main")) + '</div></div><div class="affix-section"><b>推荐副属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "sub")) + '</div></div><small class="affix-source-note">推荐结果由维护者配置；原始随机词条池仅作为编辑参考。</small></div>' + terminalMarkup + '<div class="quality-note">' + data.structure.main_affix_count + ' 个主属性 + ' + data.structure.sub_affix_count + ' 个副属性 · 词条不可洗练 · 金/紫/蓝只影响数值上限</div>';
}
function updateImportedPanel(data) {
  const knowledge = importedKnowledge && data === characterData.真红 ? importedKnowledge : null;
  if (!knowledge) return;

  const basic = knowledge.basic || {};
  const portrait = knowledge.assets?.find((asset) => asset.type === "character_portrait");
  const icon = knowledge.assets?.find((asset) => asset.type === "character_icon" && asset.local_path.endsWith("zhenhong-icon.webp"));
  const portraitElement = $("#characterPortrait");
  const listIcon = $("#characterListAvatar");
  if (portraitElement && portrait) portraitElement.src = importedAssetUrl(portrait);
  if (listIcon && icon) listIcon.src = importedAssetUrl(icon);

  const sourceLink = $("#sourcePageLink");
  if (sourceLink) sourceLink.href = knowledge.provenance?.source_url || "#";
  setText("#reactionSelect b", "盈蓄");
  setText("#reactionSelect small", "角色技能中的环合强化 · 本地原文已保存");
  setText("#metricSlots", String(knowledge.skills?.length || 0));
  setText("#metricTeams", String((knowledge.skills || []).reduce((sum, skill) => sum + skill.parameters.length, 0)));
  setText("#metricGold", String(knowledge.awakenings?.length || 0));  setText("#metricMaterials", String(Object.keys(knowledge.cultivation?.material_catalog || {}).length));
  syncPublicPreview();

  renderRecommended(knowledge);
  renderBaseStats(knowledge);
  renderSkills(knowledge);
  renderAwakenings(knowledge);
  renderSkillTargets(knowledge);
  renderCassetteRecommendationEditor(knowledge);
  renderCassette(knowledge);
  calculateMaterials(knowledge);

  const gallery = $("#assetStrip");
  if (gallery) {
    gallery.innerHTML = (knowledge.assets || []).map((asset) => {
      const filename = asset.local_path.split("/").pop();
      return `<figure class="asset-card"><img src="${importedAssetUrl(asset)}" alt="${asset.type}" loading="lazy"><figcaption><b>${asset.type}</b><small>${filename}</small></figcaption></figure>`;
    }).join("");
  }
}
function applyCharacter(name) {
  const data = characterData[name];
  if (!data) return;
  selectedCharacter = name;
  currentMode = data.mode;
  $$(".character-card").forEach((card) => card.classList.toggle("is-active", card.dataset.character === name));
  setText("#editorCharacterName", name);
  const importedBasic = importedKnowledge && name === "真红" ? importedKnowledge.basic || {} : {};
  $("#roleName").value = name;
  $("#roleId").value = data.id;
  $("#roleRarity").value = data.rarity || importedBasic.rarity || "S";
  $("#roleElement").value = data.element || importedBasic.element || "光";
  $("#roleCassetteType").value = data.cassetteType || importedBasic.cassette_type || "—";
  $("#rolePosition").value = data.position || "主 C · 驻场输出";
  $("#roleStation").value = data.station || data.mode || "站场";
  $("#roleRating").value = data.rating || importedBasic.rating || "—";
  $("#roleVersion").value = data.version || "待审核";
  syncPublicPreview();
  setText("#draftLabel", "草稿未保存");
  setText("#understandingTitle", data.summaryTitle);
  setText("#understandingCopy", data.summary);
  setText("#slotCount", String(data.slots.length));
  setText("#metricSlots", data.metrics[0]);
  setText("#metricTeams", data.metrics[1]);
  setText("#metricGold", data.metrics[2]);
  updateSlotList(data.slots);
  $$(".segment").forEach((segment) => segment.classList.toggle("is-active", segment.dataset.mode === data.mode));
  setText("#reactionSelect b", data.reaction);
  setText("#reactionSelect small", data === characterData.真红 ? "角色技能中的环合强化 · 本地原文" : "提高反应伤害 · 作用于全队");
  updateImportedPanel(data);
  notify(`已切换到 ${name} 的知识草稿`);
}
function bindCharacterCards() {
  $$(".character-card").forEach((card) => card.addEventListener("click", () => applyCharacter(card.dataset.character)));
}

function bindNavigation() {
  $$("[data-nav]").forEach((item) => item.addEventListener("click", () => {
    $$("[data-nav]").forEach((nav) => nav.classList.remove("is-active"));
    item.classList.add("is-active");
    if (item.dataset.nav !== "角色管理") notify(`「${item.dataset.nav}」模块将在下一阶段接入`);
  }));
}

function bindSearch() {
  const search = $("#characterSearch");
  search.addEventListener("input", () => {
    const keyword = search.value.trim().toLowerCase();
    $$(".character-card").forEach((card) => {
      const name = card.dataset.character.toLowerCase();
      const content = card.textContent.toLowerCase();
      card.hidden = Boolean(keyword && !name.includes(keyword) && !content.includes(keyword));
    });
  });
}

function bindModes() {
  $$(".segment").forEach((segment) => segment.addEventListener("click", () => {
    $$(".segment").forEach((item) => item.classList.remove("is-active"));
    segment.classList.add("is-active");
    currentMode = segment.dataset.mode;
    setText("#draftLabel", "草稿未保存");
    setText("#analysisState", "需重新分析");
    notify(`站场模式已切换为「${currentMode}」`);
  }));
}

function bindSave() {
  const save = () => {
    setText("#draftLabel", "已保存刚刚");
    setText(".updated-time", "最后保存刚刚");
    notify(`${selectedCharacter} 的草稿已保存`);
  };
  $("#saveDraftButton").addEventListener("click", save);
  $("#roleName").addEventListener("input", () => setText("#draftLabel", "草稿未保存"));
}

function bindImpact() {
  const runButton = $("#runImpactButton");
  if (!runButton) return;
  runButton.addEventListener("click", () => {
    if (importedKnowledge) {
      calculateMaterials(importedKnowledge);
      notify("已按当前目标汇总养成材料");
    }
  });
}
function bindMisc() {
  const optionalBindings = [
    ["#workspaceSwitch", () => notify("当前工作区：角色资料库")],
    ["#profileButton", () => notify("林维护者 · 编辑权限")],
    ["#previewButton", () => notify("角色资料预览已准备")],
    ["#explainButton", () => notify("概览来自基础资料、技能和觉醒数据")],
    ["#moreButton", () => notify("更多操作：停用、复制为新角色、查看历史版本")],
    ["#reactionSelect", () => notify("当前显示真红技能中的环合强化资料")],
    ["#submitReviewButton", () => { setText("#draftLabel", "待审核"); notify("已提交角色资料审核"); }],
    ["#recalculateButton", () => importedKnowledge && calculateMaterials(importedKnowledge)]
  ];
  optionalBindings.forEach(([selector, handler]) => { const element = $(selector); if (element) element.addEventListener("click", handler); });
  ["#targetLevel"].forEach((selector) => { const element = $(selector); if (element) element.addEventListener("change", () => importedKnowledge && calculateMaterials(importedKnowledge)); });
}
bindCharacterCards();
bindNavigation();
bindSearch();
bindModes();
bindSave();
bindImpact();
bindMisc();
applyCharacter(selectedCharacter);






