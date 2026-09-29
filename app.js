const allKnowledge = window.characterKnowledge || {};
const arcDriveCatalog = window.arcDriveKnowledge || { items: [], source: {} };
const skyCurtainCatalog = window.skyCurtainKnowledge || { items: [], source: {} };
const driverBlockCatalog = window.driverBlockKnowledge || { items: [], source: {}, mechanism_guide: {} };
const importedKnowledge = allKnowledge.zhenhong || null;
let activeKnowledge = importedKnowledge;
const importedAssetUrl = (asset) => asset?.local_path || "";
const characterData = Object.fromEntries(Object.values(allKnowledge).filter((knowledge) => knowledge?.name).map((knowledge) => {
  const basic = knowledge.basic || {};
  const facts = knowledge.mechanism_facts || {};
  const portrait = knowledge.assets?.find((asset) => asset.type === "character_portrait");
  const icon = knowledge.assets?.find((asset) => asset.type === "character_icon");
  const skills = knowledge.skills || [];
  const parameterCount = skills.reduce((sum, skill) => sum + (skill.parameters || []).length, 0);
  const awakenings = knowledge.awakenings || [];
  const resonance = knowledge.resonance || [];
  const materialCount = Object.keys(knowledge.cultivation?.material_catalog || {}).length;
  const summary = basic.summary || "来源页面未提供角色简介。";
  const roleLabel = basic.role || "定位待补充";
  const positionLabel = basic.position || "站位待补充";
  const statsCount = knowledge.base_stats?.stats?.length || 0;
  const cultivationAvailable = Boolean((knowledge.cultivation?.ascension || []).length || (knowledge.cultivation?.skills || []).length);
  const slots = [
    ["基础资料", "来源页记录的角色属性与定位", basic.rarity && basic.element ? "已导入" : "待补充", basic.rarity && basic.element ? "green" : "amber"],
    ["基础属性", "角色等级成长数据", statsCount ? `${statsCount} 项` : "待补充", statsCount ? "green" : "amber"],
    ["技能资料", "来源页技能描述与参数", skills.length ? `${skills.length} 项` : "待补充", skills.length ? "green" : "amber"],
    ["觉醒与共鸣", "角色节点效果", awakenings.length + resonance.length ? `${awakenings.length + resonance.length} 项` : "待补充", awakenings.length + resonance.length ? "green" : "amber"],
    ["养成材料", "突破与技能升级消耗", cultivationAvailable ? `${materialCount} 种材料` : "待补充", cultivationAvailable ? "green" : "amber"]
  ];
  return [knowledge.name, {
    id: knowledge.id,
    knowledgeId: knowledge.id,
    mode: "站场",
    rarity: basic.rarity || "—",
    element: basic.element || "—",
    cassetteType: basic.cassette_type || "—",
    rating: basic.rating || "—",
    role: basic.role || "",
    sourcePosition: basic.position || "",
    position: `${roleLabel} · ${positionLabel}`,
    station: basic.position || "待补充",
    version: "待补充",
    summaryTitle: `${knowledge.name} · ${roleLabel}`,
    summary,
    reaction: facts.primary_reaction || "待补充",
    portrait: portrait ? importedAssetUrl(portrait) : "",
    icon: icon ? importedAssetUrl(icon) : "",
    sourceUrl: knowledge.provenance?.source_url || "",
    localSnapshot: knowledge.provenance?.raw_snapshot || "",
    metrics: [String(skills.length), String(parameterCount), String(awakenings.length)],
    slots,
    knowledge
  }];
}));
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const toast = $("#toast");
const toastText = $("#toastText");
let toastTimer;
let selectedCharacter = "真红";
let currentMode = "站场";
let selectedArcDriveId = arcDriveCatalog.items?.[0]?.id || "";
let arcDriveRarityFilter = "all";
let arcDriveTypeFilter = "all";
let arcDriveSearchQuery = "";
let selectedArcDriveLevel = 80;
let selectedArcDriveRank = 1;
let selectedSkyCurtainId = skyCurtainCatalog.items?.[0]?.id || "";
let skyCurtainCategoryFilter = "all";
let skyCurtainElementFilter = "all";
let skyCurtainSearchQuery = "";
let selectedDriverBlockId = driverBlockCatalog.items?.[0]?.id || "";
let selectedDriverBlockQuality = "gold";
let selectedDriverBlockLevel = 20;
let driverBlockModelFilter = "all";
let driverBlockSearchQuery = "";
let selectedSkyCurtainQuality = "gold";
let userActiveTab = "overview";
let userCharacterSearchQuery = "";
let userTargetLevel = 80;
let userSkillTargets = {};
let userCarouselCursor = 0;
let userCarouselDrag = null;
let userCarouselDragOffset = 0;
let userCarouselSuppressClick = false;

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

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function emptyState(message) {
  return `<p class="empty-state">${escapeHtml(message)}</p>`;
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
  quickFacts.innerHTML = '<div><span>稀有度</span><b>' + escapeHtml(values.rarity) + '</b></div><div><span>属性</span><b>' + escapeHtml(values.element) + '</b></div><div><span>弧盘类型</span><b>' + escapeHtml(values.cassetteType) + '</b></div><div><span>定位</span><b>' + escapeHtml(values.position) + '</b></div><div><span>站位</span><b>' + escapeHtml(values.station) + '</b></div><div><span>强度评级</span><b>' + escapeHtml(values.rating) + '</b></div>';
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
  if (weapon) {
    const data = recommended.weapon;
    weapon.innerHTML = data ? `<div class="recommendation-card">${data.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: data.asset }))}" alt="${escapeHtml(data.name)}">` : '<span class="asset-placeholder">武</span>'}<div><span>推荐武器 · ${escapeHtml(data.rating || "评级待补充")}</span><b>${escapeHtml(data.name)}</b><small>来源：角色详情页</small></div></div>` : emptyState("来源页未提供可导入的推荐武器");
  }
  const cassette = $("#recommendedCassette");
  if (cassette) {
    const data = recommended.cassette;
    cassette.innerHTML = data ? `<div class="recommendation-card">${data.icon ? `<img src="${escapeHtml(importedAssetUrl({ local_path: data.icon }))}" alt="${escapeHtml(data.name)}">` : '<span class="asset-placeholder">带</span>'}<div><span>推荐卡带 · ${escapeHtml(data.category || "类型待补充")} · ${escapeHtml(data.element || "属性待补充")}</span><b>${escapeHtml(data.name)}</b><small>${escapeHtml(data.cassette_type || "卡带类型待补充")}${data.set_effects?.length ? ` · ${data.set_effects.length} 条套装效果` : ""}</small></div></div>` : emptyState("来源页未提供可导入的推荐卡带");
  }
}

function renderBaseStats(knowledge) {
  const target = $("#baseStats");
  if (!target) return;
  const stats = knowledge.base_stats?.stats || [];
  if (!stats.length) { target.innerHTML = emptyState("来源页未提供结构化基础属性成长数据"); return; }
  const maxLevel = Math.max(...stats.map((stat) => (stat.values || []).length));
  const levels = [1, 30, 50, 70, 80].filter((level) => level <= maxLevel);
  target.innerHTML = `<div class="stats-table"><div class="stats-row stats-head"><span>属性</span>${levels.map((level) => `<span>Lv.${level}</span>`).join("")}</div>${stats.map((stat) => `<div class="stats-row"><b>${escapeHtml(stat.name)}</b>${levels.map((level) => `<span>${stat.values?.[level - 1] == null ? "—" : Number(stat.values[level - 1]).toLocaleString()}</span>`).join("")}</div>`).join("")}</div>`;
}

function renderSkills(knowledge) {
  const target = $("#skillsList");
  if (!target) return;
  const skills = knowledge.skills || [];
  if (!skills.length) { target.innerHTML = emptyState("来源页未提供可解析的技能条目"); return; }
  target.innerHTML = skills.map((skill, index) => {
    const parameters = skill.parameters || [];
    return `
    <details class="skill-details" ${index === 0 ? "open" : ""}>
      <summary><span class="skill-category">${escapeHtml(skill.category || "Skill")}</span><b>${escapeHtml(skill.name)}</b><small>${parameters.length ? `${parameters.length} 个倍率参数` : "暂无等级倍率"}${skill.level_cap ? ` · Lv.${skill.level_cap}` : ""}</small></summary>
      <div class="skill-content">
        ${(skill.description_parts || []).map((part) => `<p><b>${escapeHtml(part.name)}</b>${escapeHtml(part.text)}</p>`).join("")}
        ${parameters.length ? `<div class="parameter-table"><div class="parameter-head"><span>倍率/参数</span><span>Lv.1 → Lv.${skill.level_cap || 1}</span></div>${parameters.map((parameter) => `<div class="parameter-row"><span>${escapeHtml(parameter.label)}</span><small>${(parameter.values || []).map(escapeHtml).join(" → ")}</small></div>`).join("")}</div>` : ""}
      </div>
    </details>`;
  }).join("");
}

function renderAwakenings(knowledge) {
  const target = $("#awakeningList");
  if (!target) return;
  const awakenings = knowledge.awakenings || [];
  target.innerHTML = awakenings.length ? awakenings.map((awakening, index) => `
    <article class="awakening-card">${awakening.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: awakening.asset }))}" alt="觉醒 ${index + 1}">` : '<span class="asset-placeholder awakening-placeholder">?</span>'}<div><b>${index + 1}. ${escapeHtml(awakening.name || "未命名节点")}</b><p>${escapeHtml(awakening.description)}</p></div></article>`).join("") : emptyState("来源页未提供觉醒节点");
}

function renderResonance(knowledge) {
  const target = $("#resonanceList");
  if (!target) return;
  const entries = knowledge.resonance || [];
  target.innerHTML = entries.length ? entries.map((entry) => `
    <article class="awakening-card">${entry.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: entry.asset }))}" alt="${escapeHtml(entry.name || "共鸣")}">` : '<span class="asset-placeholder awakening-placeholder">共</span>'}<div><b>${entry.level ? `Lv.${entry.level} · ` : ""}${escapeHtml(entry.name || "共鸣")}</b><p>${escapeHtml(entry.description)}</p></div></article>`).join("") : emptyState("来源页未提供共鸣节点");
}

function materialAsset(knowledge, id) {
  const icon = knowledge.cultivation?.material_catalog?.[id]?.icon;
  if (!icon) return "";
  const filename = icon.split("/").pop();
  const asset = (knowledge.assets || []).find((item) => item.local_path?.endsWith(`/items/${filename}.webp`));
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
  if (!skills.length) { target.innerHTML = emptyState("来源页未提供结构化技能养成节点"); return; }
  target.innerHTML = '<div class="skill-targets-head"><div><b>技能目标等级</b><small>每个技能单独设定，默认按该技能最高等级计算</small></div><span>' + skills.length + ' 项技能</span></div>' +
    '<div class="skill-target-grid">' + skills.map((skill, index) => {
      const levels = skillTargetOptions(skill);
      const max = Math.max(...levels);
      const fixed = levels.length === 1;
      return '<label class="skill-target-row"><span><b>' + escapeHtml(skill.name) + '</b><small>' + (fixed ? '固定等级 / 觉醒节点' : '独立目标 · 最高 Lv.' + max) + '</small></span><select data-skill-target="' + index + '"' + (fixed ? ' disabled' : '') + '>' +
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
  if (!knowledge || (!(knowledge.cultivation?.ascension || []).length && !(knowledge.cultivation?.skills || []).length)) {
    const target = $("#materialSummary");
    if (target) target.innerHTML = emptyState("来源页未提供结构化养成材料数据");
    setText("#impactSummary", "养成数据待补充");
    setText("#analysisState", "待补充");
    setText("#metricMaterials", "0");
    return [];
  }
  const targetLevel = Number($("#targetLevel")?.value || 80);
  const skillTargets = readSkillTargets(knowledge);
  const totals = new Map();
  const add = (id, amount) => totals.set(id, (totals.get(id) || 0) + amount);
  (knowledge.cultivation?.ascension || []).filter((step) => step.level <= targetLevel).forEach((step) => (step.items || []).forEach((item) => add(item.id, item.amount)));
  (knowledge.cultivation?.skills || []).forEach((skill, index) => {
    const targetSkillLevel = skillTargets[index]?.target || 1;
    (skill.levels || []).filter((step) => step.level <= targetSkillLevel).forEach((step) => (step.items || []).forEach((item) => add(item.id, item.amount)));
  });
  const catalog = knowledge.cultivation?.material_catalog || {};
  const entries = [...totals.entries()].map(([id, amount]) => ({ id, amount, name: catalog[id]?.name || id, icon: materialAsset(knowledge, id) }));
  const target = $("#materialSummary");
  if (target) {
    const goalSummary = skillTargets.map((skill) => '<span>' + escapeHtml(skill.name) + ' Lv.' + skill.target + '</span>').join('');
    target.innerHTML = '<div class="material-summary-head"><span>目标：角色 Lv.' + targetLevel + ' · 各技能独立目标</span><b>' + entries.length + ' 种材料</b></div><div class="skill-goal-summary">' + goalSummary + '</div><div class="material-grid">' + entries.map((entry) => '<div class="material-card">' + (entry.icon ? '<img src="' + escapeHtml(entry.icon) + '" alt="' + escapeHtml(entry.name) + '">' : '') + '<div><b>' + escapeHtml(entry.name) + '</b><span>' + entry.amount.toLocaleString() + '</span></div></div>').join('') + '</div>';
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
  return groups.map((group, index) => '<span class="affix-rank-group">' + group.names.map(escapeHtml).join(" ≈ ") + '</span>' + (index < groups.length - 1 ? '<b class="affix-rank-separator">＞</b>' : '')).join('');
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

function renderTerminalDiagram(layout) {
  const rows = Number(layout?.rows);
  const columns = Number(layout?.columns);
  if (!Number.isInteger(rows) || !Number.isInteger(columns) || rows < 1 || columns < 1 || rows > 12 || columns > 12) return "";
  const activeSlots = new Set((layout.active_slots || [])
    .filter((slot) => Number.isInteger(Number(slot.row)) && Number.isInteger(Number(slot.column)) && Number(slot.row) >= 1 && Number(slot.row) <= rows && Number(slot.column) >= 1 && Number(slot.column) <= columns)
    .map((slot) => `${Number(slot.row)}:${Number(slot.column)}`));
  if (!activeSlots.size) return "";
  const cells = Array.from({ length: rows * columns }, (_, index) => {
    const row = Math.floor(index / columns) + 1;
    const column = index % columns + 1;
    return `<span class="terminal-layout-cell${activeSlots.has(`${row}:${column}`) ? " is-active" : ""}" aria-hidden="true"></span>`;
  }).join("");
  return `<div class="terminal-layout" role="img" aria-label="终端驱动槽位示意图" style="--terminal-columns:${columns};--terminal-rows:${rows}">${cells}</div>`;
}

function renderTerminalCard(terminal) {
  if (!terminal) return "";
  const diagram = renderTerminalDiagram(terminal.layout);
  return `<section class="terminal-card">${diagram}<div class="terminal-copy"><span class="terminal-kicker">终端 · 驱动加成</span><b>${escapeHtml(terminal.name || "卡带属性")}</b><p>${escapeHtml(terminal.description || "")}</p><span class="terminal-effect">${(terminal.effects || []).map(escapeHtml).join(" · ")}</span></div></section>`;
}

function renderCassetteRecommendationEditor(knowledge) {
  const target = $("#cassetteRecommendationEditor");
  const cassette = knowledge.recommended?.cassette;
  if (!target) return;
  if (!cassette) { target.innerHTML = emptyState("没有来源卡带可供配置推荐属性"); return; }
  const buildGroup = (kind, title, pool) => {
    const selected = new Map(recommendedAffixes(cassette, kind).map((item) => [item.name, item.priority]));
    return '<div class="affix-editor-group"><div class="affix-editor-group-head"><div><b>' + title + '</b><small>点击词条选择，再设置优先级</small></div><span>' + selected.size + ' 项已选</span></div><div class="affix-editor-options">' +
      pool.map((name) => {
        const isSelected = selected.has(name);
        const priority = selected.get(name) || 1;
        return '<div class="affix-editor-row"><button type="button" class="affix-choice pressable' + (isSelected ? ' is-selected' : '') + '" data-affix-option="' + kind + '" data-affix-name="' + escapeHtml(name) + '" aria-pressed="' + isSelected + '">' + (isSelected ? '✓ ' : '+ ') + escapeHtml(name) + '</button><label class="affix-priority"><span>优先级</span><input data-affix-priority type="number" min="1" max="9" value="' + priority + '"' + (isSelected ? '' : ' disabled') + '></label></div>';
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
    syncCassetteRecommendations(activeKnowledge, target, true);
  });
  target.addEventListener("change", (event) => {
    if (!event.target.matches("[data-affix-priority]")) return;
    syncCassetteRecommendations(activeKnowledge, target);
  });
}

function renderCassette(knowledge) {
  const target = $("#cassetteDetails");
  const data = knowledge.recommended?.cassette;
  if (!target) return;
  const terminalMarkup = renderTerminalCard(knowledge.terminal || data?.terminal);
  if (!data) { target.innerHTML = terminalMarkup || emptyState("没有来源卡带详情"); return; }
  const effects = data.set_effects || [];
  const structure = data.structure || {};
  target.innerHTML = '<div class="cassette-summary">' + (data.icon ? '<img src="' + escapeHtml(importedAssetUrl({ local_path: data.icon })) + '" alt="' + escapeHtml(data.name) + '">' : '<span class="asset-placeholder">带</span>') + '<div><b>' + escapeHtml(data.name) + '</b><span>' + [data.category, data.cassette_type, data.element && `${data.element}属性`].filter(Boolean).map(escapeHtml).join(" · ") + '</span><small>' + escapeHtml(data.acquisition || "获取方式待补充") + '</small></div></div><div class="set-effects">' + (effects.length ? effects.map((effect) => '<div><b>' + effect.pieces + '件套</b><span>' + escapeHtml(effect.description) + '</span></div>').join("") : emptyState("来源页未提供套装效果")) + '</div><div class="recommended-affixes"><div class="affix-section"><b>推荐主属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "main")) + '</div></div><div class="affix-section"><b>推荐副属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "sub")) + '</div></div><small class="affix-source-note">推荐结果由维护者配置；原始随机词条池仅作为编辑参考。</small></div>' + terminalMarkup + (structure.main_affix_count || structure.sub_affix_count ? '<div class="quality-note">' + (structure.main_affix_count ?? "—") + ' 个主属性 + ' + (structure.sub_affix_count ?? "—") + ' 个副属性 · ' + (structure.rerollable === false ? '词条不可洗练' : '洗练规则待补充') + '</div>' : '');
}

const DRIVE_LAYOUT_DB = "keke-character-drive-layouts";
const DRIVE_LAYOUT_STORE = "images";
const DRIVE_LAYOUT_FALLBACK_PREFIX = "keke:drive-layout:";
let driveLayoutDbPromise;
let driveLayoutObjectUrl = "";

function openDriveLayoutDb() {
  if (!window.indexedDB) return Promise.reject(new Error("浏览器不支持 IndexedDB"));
  if (driveLayoutDbPromise) return driveLayoutDbPromise;
  driveLayoutDbPromise = new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DRIVE_LAYOUT_DB, 1);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(DRIVE_LAYOUT_STORE)) database.createObjectStore(DRIVE_LAYOUT_STORE, { keyPath: "characterId" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("无法打开本地图片存储"));
    request.onblocked = () => reject(new Error("本地图片存储正在被另一个标签页占用"));
  }).catch((error) => {
    driveLayoutDbPromise = null;
    throw error;
  });
  return driveLayoutDbPromise;
}

async function getDriveLayoutRecord(characterId) {
  try {
    const database = await openDriveLayoutDb();
    const record = await new Promise((resolve, reject) => {
      const request = database.transaction(DRIVE_LAYOUT_STORE, "readonly").objectStore(DRIVE_LAYOUT_STORE).get(characterId);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error || new Error("读取摆放图失败"));
    });
    if (record) return record;
  } catch (error) {
    // Browsers without usable IndexedDB can fall back to a small data URL in localStorage.
  }
  try {
    const saved = localStorage.getItem(DRIVE_LAYOUT_FALLBACK_PREFIX + characterId);
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    return null;
  }
}

async function putDriveLayoutRecord(characterId, file) {
  const record = { characterId, blob: file, filename: file.name, mimeType: file.type, updatedAt: new Date().toISOString() };
  try {
    const database = await openDriveLayoutDb();
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(DRIVE_LAYOUT_STORE, "readwrite");
      transaction.objectStore(DRIVE_LAYOUT_STORE).put(record);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error("保存摆放图失败"));
      transaction.onabort = () => reject(transaction.error || new Error("保存摆放图已取消"));
    });
    localStorage.removeItem(DRIVE_LAYOUT_FALLBACK_PREFIX + characterId);
    return;
  } catch (indexedDbError) {
    if (file.size > 1024 * 1024) throw new Error("浏览器图片存储不可用；本地回退仅支持 1 MB 以内的图片");
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error("读取所选图片失败"));
      reader.readAsDataURL(file);
    });
    try {
      localStorage.setItem(DRIVE_LAYOUT_FALLBACK_PREFIX + characterId, JSON.stringify({ characterId, dataUrl, filename: file.name, mimeType: file.type, updatedAt: record.updatedAt }));
    } catch (storageError) {
      throw new Error("浏览器存储空间不足，图片没有保存");
    }
  }
}

async function deleteDriveLayoutRecord(characterId) {
  try {
    const database = await openDriveLayoutDb();
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(DRIVE_LAYOUT_STORE, "readwrite");
      transaction.objectStore(DRIVE_LAYOUT_STORE).delete(characterId);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error("删除摆放图失败"));
      transaction.onabort = () => reject(transaction.error || new Error("删除摆放图已取消"));
    });
  } catch (error) {
    // Still clear the fallback record below.
  }
  try { localStorage.removeItem(DRIVE_LAYOUT_FALLBACK_PREFIX + characterId); } catch (error) { /* storage may be disabled */ }
}

function driveLayoutSourceFromKnowledge(knowledge) {
  const image = knowledge.drive_layout_image;
  if (typeof image === "string" && image.trim()) return { src: image.trim(), filename: image.trim().split(/[\\/]/).pop() };
  if (image && typeof image === "object") {
    const src = image.src || image.url || image.data_url || image.local_path || image.path;
    if (src) return { src, filename: image.filename || String(src).split(/[\\/]/).pop() };
  }
  return null;
}

function renderDriveLayoutFigure(container, src, filename, alt) {
  const figure = document.createElement("figure");
  const image = document.createElement("img");
  image.src = src;
  image.alt = alt;
  image.loading = "lazy";
  const caption = document.createElement("figcaption");
  caption.textContent = filename || alt;
  figure.append(image, caption);
  container.replaceChildren(figure);
  return image;
}

async function renderDriveLayout(knowledge) {
  const editorPreview = $("#driveLayoutAdminPreview");
  const publicPanel = $("#driveLayoutPublic");
  const publicImage = $("#driveLayoutPublicImage");
  if (!editorPreview || !publicPanel || !publicImage) return;
  if (driveLayoutObjectUrl) URL.revokeObjectURL(driveLayoutObjectUrl);
  driveLayoutObjectUrl = "";
  editorPreview.replaceChildren();
  publicImage.replaceChildren();
  publicPanel.hidden = true;
  if (!knowledge?.id) return;

  let descriptor = driveLayoutSourceFromKnowledge(knowledge);
  if (!descriptor) {
    const record = await getDriveLayoutRecord(knowledge.id);
    if (activeKnowledge?.id !== knowledge.id || !record) return;
    if (record.blob instanceof Blob) {
      driveLayoutObjectUrl = URL.createObjectURL(record.blob);
      descriptor = { src: driveLayoutObjectUrl, filename: record.filename || "驱动摆放示意图" };
    } else if (typeof record.dataUrl === "string" && record.dataUrl.startsWith("data:image/")) {
      descriptor = { src: record.dataUrl, filename: record.filename || "驱动摆放示意图" };
    }
  }
  if (activeKnowledge?.id !== knowledge.id || !descriptor) return;

  const name = descriptor.filename || `${knowledge.name}驱动摆放示意图`;
  const adminImage = renderDriveLayoutFigure(editorPreview, descriptor.src, name, `${knowledge.name}驱动摆放示意图预览`);
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.dataset.removeDriveLayout = "true";
  removeButton.textContent = "移除此图片";
  editorPreview.append(removeButton);
  const publicPreview = renderDriveLayoutFigure(publicImage, descriptor.src, name, `${knowledge.name}驱动摆放位置示意图`);
  publicPanel.hidden = false;
  const hideIfBroken = () => {
    editorPreview.replaceChildren();
    publicImage.replaceChildren();
    publicPanel.hidden = true;
  };
  adminImage.addEventListener("error", hideIfBroken, { once: true });
  publicPreview.addEventListener("error", hideIfBroken, { once: true });
}

function bindDriveLayoutUpload() {
  const input = $("#driveLayoutUpload");
  const preview = $("#driveLayoutAdminPreview");
  if (!input || !preview || input.dataset.bound === "true") return;
  input.dataset.bound = "true";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    const knowledge = activeKnowledge;
    if (!file || !knowledge?.id) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      input.value = "";
      notify("请选择 PNG、JPG 或 WebP 图片");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      input.value = "";
      notify("图片不能超过 15 MB");
      return;
    }
    try {
      await putDriveLayoutRecord(knowledge.id, file);
      if (activeKnowledge?.id === knowledge.id) {
        await renderDriveLayout(knowledge);
        notify(`${knowledge.name} 的摆放图已保存在此浏览器`);
      }
    } catch (error) {
      notify(error.message || "图片保存失败");
    } finally {
      input.value = "";
    }
  });
  preview.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-remove-drive-layout]");
    if (!button || !activeKnowledge?.id) return;
    const knowledge = activeKnowledge;
    await deleteDriveLayoutRecord(knowledge.id);
    if (activeKnowledge?.id === knowledge.id) {
      knowledge.drive_layout_image = "";
      await renderDriveLayout(knowledge);
      notify(`${knowledge.name} 的摆放图已移除`);
    }
  });
}

function updateImportedPanel(data) {
  const knowledge = data.knowledge;
  if (!knowledge) return;
  activeKnowledge = knowledge;
  const portrait = knowledge.assets?.find((asset) => asset.type === "character_portrait");
  const portraitElement = $("#characterPortrait");
  if (portraitElement) {
    portraitElement.hidden = !portrait;
    if (portrait) portraitElement.src = importedAssetUrl(portrait);
    portraitElement.alt = `${knowledge.name}立绘`;
  }
  const sourceLink = $("#sourcePageLink");
  if (sourceLink) sourceLink.href = knowledge.provenance?.source_url || "#";
  const snapshotLink = $("#localSnapshotLink");
  if (snapshotLink) snapshotLink.href = knowledge.provenance?.raw_snapshot || "#";
  const reviewPill = $(".verified-pill");
  if (reviewPill) reviewPill.innerHTML = '<i></i> ' + (knowledge.manual_review?.length ? "待人工核验" : "已校验");
  const facts = knowledge.mechanism_facts || {};
  setText("#reactionSelect b", facts.primary_reaction || "待补充");
  setText("#reactionSelect small", facts.reaction_enhancement_text || (facts.primary_reaction ? "角色来源资料已保存" : "来源页未提供反应强化资料"));
  setText("#metricSlots", String(knowledge.skills?.length || 0));
  setText("#metricTeams", String((knowledge.skills || []).reduce((sum, skill) => sum + (skill.parameters || []).length, 0)));
  setText("#metricGold", String(knowledge.awakenings?.length || 0));
  setText("#metricMaterials", String(Object.keys(knowledge.cultivation?.material_catalog || {}).length));
  const statsLabel = $("#statsLevelLabel");
  if (statsLabel) statsLabel.textContent = knowledge.base_stats?.level_cap ? `等级上限 Lv.${knowledge.base_stats.level_cap}` : "来源未提供";
  const awakeningLabel = $("#awakeningCountLabel");
  if (awakeningLabel) awakeningLabel.textContent = `${knowledge.awakenings?.length || 0} 个觉醒节点`;
  const cassetteLabel = $("#cassetteSummaryLabel");
  if (cassetteLabel) cassetteLabel.textContent = knowledge.recommended?.cassette?.name || "来源未提供推荐卡带";
  const slots = data.slots || [];
  setText("#slotCount", String(slots.length));
  updateSlotList(slots);
  syncPublicPreview();
  renderRecommended(knowledge);
  renderBaseStats(knowledge);
  renderSkills(knowledge);
  renderAwakenings(knowledge);
  renderResonance(knowledge);
  renderSkillTargets(knowledge);
  renderCassetteRecommendationEditor(knowledge);
  renderCassette(knowledge);
  renderDriveLayout(knowledge);
  calculateMaterials(knowledge);

  const gallery = $("#assetStrip");
  if (gallery) {
    const assets = knowledge.assets || [];
    gallery.innerHTML = assets.length ? assets.map((asset) => {
      const filename = asset.local_path?.split("/").pop() || "";
      return `<figure class="asset-card"><img src="${escapeHtml(importedAssetUrl(asset))}" alt="${escapeHtml(asset.type)}" loading="lazy"><figcaption><b>${escapeHtml(asset.type)}</b><small>${escapeHtml(filename)}</small></figcaption></figure>`;
    }).join("") : emptyState("当前角色没有已下载的图片资源");
  }
}

function setSelectValue(selector, value) {
  const field = $(selector);
  if (!field) return;
  const normalized = value || "";
  if (![...field.options].some((option) => option.value === normalized)) {
    const option = document.createElement("option");
    option.value = normalized;
    option.textContent = normalized || "待补充";
    field.append(option);
  }
  field.value = normalized;
}

function applyCharacter(name, options = {}) {
  const data = characterData[name];
  if (!data) return;
  selectedCharacter = name;
  currentMode = data.mode;
  $$(".character-card").forEach((card) => card.classList.toggle("is-active", card.dataset.character === name));
  setText("#editorCharacterName", name);
  $("#roleName").value = name;
  $("#roleId").value = data.id || "";
  setSelectValue("#roleRarity", data.rarity);
  setSelectValue("#roleElement", data.element);
  $("#roleCassetteType").value = data.cassetteType || "";
  $("#rolePosition").value = data.role || "";
  $("#roleStation").value = data.sourcePosition || "";
  $("#roleRating").value = data.rating || "";
  $("#roleVersion").value = data.version || "待补充";
  syncPublicPreview();
  setText("#draftLabel", data.knowledge.review_status === "approved" ? "已审核" : "来源待核验");
  setText("#understandingTitle", data.summaryTitle);
  setText("#understandingCopy", data.summary);
  $$(".segment").forEach((segment) => segment.classList.toggle("is-active", segment.dataset.mode === data.mode));
  updateImportedPanel(data);
  if (options.skipUserRail) {
    renderUserHero(data.knowledge);
    renderUserTabPanel(data.knowledge);
  } else {
    renderUserExperience(data.knowledge);
  }
  if (!options.silent) notify(`已切换到 ${name} 的本地资料`);

}
function renderCharacterCards() {
  const list = $("#characterList");
  if (!list) return;
  const entries = Object.entries(characterData).sort(([nameA, a], [nameB, b]) => {
    const rarityOrder = { S: 0, A: 1, B: 2 };
    return (rarityOrder[a.rarity] ?? 3) - (rarityOrder[b.rarity] ?? 3) || nameA.localeCompare(nameB, "zh-CN");
  });
  list.replaceChildren();
  entries.forEach(([name, data], index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "character-card stagger-item";
    button.dataset.character = name;
    button.style.setProperty("--delay", `${Math.min(index * 16, 240)}ms`);
    button.setAttribute("aria-label", `打开${name}角色资料`);
    const avatar = document.createElement("span");
    avatar.className = "character-avatar";
    if (data.icon) {
      const image = document.createElement("img");
      image.src = data.icon;
      image.alt = "";
      image.loading = "lazy";
      image.addEventListener("error", () => { image.remove(); avatar.textContent = name.slice(0, 1); }, { once: true });
      avatar.append(image);
    } else {
      avatar.textContent = name.slice(0, 1);
    }
    const info = document.createElement("span");
    info.className = "character-info";
    const title = document.createElement("b");
    title.textContent = name;
    const subtitle = document.createElement("small");
    subtitle.textContent = [data.role, data.sourcePosition].filter(Boolean).join(" · ") || "定位待补充";
    info.append(title, subtitle);
    const element = document.createElement("span");
    element.className = "element-badge";
    element.textContent = data.element === "待补充" ? "?" : data.element;
    const chevron = document.createElement("span");
    chevron.className = "row-chevron";
    chevron.textContent = "›";
    button.append(avatar, info, element, chevron);
    list.append(button);
  });
  const count = $(".count-pill");
  if (count) count.textContent = `${entries.length} 个本地角色`;
  const badge = $(".local-data-badge");
  if (badge) badge.textContent = `${entries.length} 份角色资料已接入`;
}

function bindCharacterCards() {
  $("#characterList")?.addEventListener("click", (event) => {
    const card = event.target.closest(".character-card");
    if (card) applyCharacter(card.dataset.character);
  });
}

function formatArcDriveStat(value, isPercent) {
  if (value === null || value === undefined || value === "") return "—";
  const formatted = typeof value === "number" ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value) : String(value);
  return isPercent && !formatted.endsWith("%") ? `${formatted}%` : formatted;
}

function arcDriveSearchText(item) {
  return [item.name, item.rarity, item.type, item.description, item.overview, item.passive?.title, item.passive?.description_template, ...(item.passive?.rank_descriptions || [])].filter(Boolean).join(" ").toLowerCase();
}

function filteredArcDrives() {
  return (arcDriveCatalog.items || []).filter((item) => {
    if (arcDriveRarityFilter !== "all" && item.rarity !== arcDriveRarityFilter) return false;
    if (arcDriveTypeFilter !== "all" && item.type !== arcDriveTypeFilter) return false;
    return !arcDriveSearchQuery || arcDriveSearchText(item).includes(arcDriveSearchQuery);
  });
}

function renderArcDriveList() {
  const list = $("#arcDriveList");
  if (!list) return;
  const items = filteredArcDrives();
  const count = $("#arcDriveCount");
  if (count) count.textContent = `显示 ${items.length} / ${(arcDriveCatalog.items || []).length} 件`;
  list.innerHTML = items.length ? items.map((item) => `<button class="arc-drive-card${item.id === selectedArcDriveId ? " is-active" : ""}" type="button" data-arc-drive-id="${escapeHtml(item.id)}" aria-pressed="${item.id === selectedArcDriveId}"><span class="arc-drive-card-image">${item.image?.local_path ? `<img src="${escapeHtml(item.image.local_path)}" alt="">` : "弧"}</span><span class="arc-drive-card-copy"><small>${escapeHtml(item.rarity)}级 · ${escapeHtml(item.type)}类</small><b>${escapeHtml(item.name)}</b></span></button>`).join("") : emptyState("没有符合条件的弧盘");
  if (!items.some((item) => item.id === selectedArcDriveId)) selectedArcDriveId = items[0]?.id || "";
  renderArcDriveDetail();
}

function renderArcDriveDetail() {
  const target = $("#arcDriveDetail");
  const item = (arcDriveCatalog.items || []).find((entry) => entry.id === selectedArcDriveId);
  if (!target) return;
  if (!item) {
    target.innerHTML = emptyState("从左侧选择一件弧盘查看本地资料");
    return;
  }
  const stats = item.stats || {};
  const breakpoints = stats.level_breakpoints || [1, 20, 30, 40, 50, 60, 70, 80];
  const levelIndex = Math.max(0, breakpoints.indexOf(selectedArcDriveLevel));
  const statRows = stats.rows || [];
  const rankDescriptions = item.passive?.rank_descriptions || [];
  const currentEffect = rankDescriptions[selectedArcDriveRank - 1] || "来源页没有提供调弧效果数据。";
  const sourceUrl = item.source?.url || "";
  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image">${item.image?.local_path ? `<img src="${escapeHtml(item.image.local_path)}" alt="${escapeHtml(item.name)}">` : "弧"}</div><div class="arc-drive-detail-title"><span class="rarity-chip rarity-${escapeHtml(item.rarity.toLowerCase())}">${escapeHtml(item.rarity)}级 · ${escapeHtml(item.type)}类</span><h2>${escapeHtml(item.name)}</h2><p>${escapeHtml(item.overview || `${item.name} · ${item.rarity}级${item.type}类弧盘`)}</p>${sourceUrl ? `<a class="source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">打开来源详情 ↗</a>` : ""}</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>等级属性</h3><small>来源等级成长数据</small></div><label class="arc-level-select">等级<select id="arcDriveLevel">${breakpoints.map((level) => `<option value="${level}"${Number(level) === Number(selectedArcDriveLevel) ? " selected" : ""}>Lv.${level}</option>`).join("")}</select></label></div><div class="arc-stat-grid">${statRows.length ? statRows.map((row) => { const value = row.values_at_breakpoints?.[levelIndex] ?? row.current_value; return `<div class="arc-stat-card"><span>${escapeHtml(row.name || "属性")}</span><b>${escapeHtml(formatArcDriveStat(value, row.is_percent))}</b></div>`; }).join("") : emptyState("来源页没有等级属性数据")}</div></section>${item.description ? `<section class="arc-drive-description"><h3>说明</h3><p>${escapeHtml(item.description)}</p></section>` : ""}<section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>${escapeHtml(item.passive?.title || "调弧效果")}</h3><small>效果数值随调弧等级变化</small></div></div><div class="arc-rank-select" role="group" aria-label="调弧等级">${Array.from({ length: Math.max(rankDescriptions.length, 1) }, (_, index) => `<button type="button" class="${selectedArcDriveRank === index + 1 ? "is-active" : ""}" data-arc-rank="${index + 1}" aria-pressed="${selectedArcDriveRank === index + 1}">R${index + 1}</button>`).join("")}</div><p class="arc-effect-copy">${escapeHtml(currentEffect)}</p></section><section class="arc-drive-overview"><h3>图鉴概述</h3><p>${escapeHtml(item.overview || "来源页未提供概述。")}</p></section>`;
}

function initArcDriveCatalog() {
  const entries = arcDriveCatalog.items || [];
  if (!entries.some((item) => item.id === selectedArcDriveId)) selectedArcDriveId = entries[0]?.id || "";
  const source = arcDriveCatalog.source || {};
  const attribution = $("#arcDriveAttribution");
  if (attribution) {
    const indexUrl = arcDriveCatalog.source_index || "https://wiki.mysqil.com/weapons/";
    attribution.innerHTML = `资料整理自 <a href="${escapeHtml(indexUrl)}" target="_blank" rel="noreferrer">${escapeHtml(source.site || "Mysqil · 环世全鉴")}</a>；作者 ${escapeHtml(source.author || "Matsuzaka Yuki")}；许可 <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">${escapeHtml(source.license || "CC BY-NC-SA 4.0")}</a>；本地图鉴内容已从来源页提取并结构化整理。`;
  }
  renderArcDriveList();
}

function skyCurtainSearchText(item) {
  return [
    item.name,
    item.category,
    item.element,
    item.set_effects?.two_piece,
    item.set_effects?.four_piece,
    item.acquisition,
    item.main_affix_pool?.note,
    ...(item.main_affix_pool?.items || []),
    item.sub_affix_pool?.note,
    ...(item.sub_affix_pool?.items || []),
    item.quality?.role_note,
    item.quality?.source_note,
    item.quality?.note,
    ...(item.quality?.tiers || []).map((tier) => tier.description),
    item.overview
  ].filter(Boolean).join(" ").toLowerCase();
}

function filteredSkyCurtains() {
  return (skyCurtainCatalog.items || []).filter((item) => {
    if (skyCurtainCategoryFilter !== "all" && item.category !== skyCurtainCategoryFilter) return false;
    if (skyCurtainElementFilter !== "all" && item.element !== skyCurtainElementFilter) return false;
    return !skyCurtainSearchQuery || skyCurtainSearchText(item).includes(skyCurtainSearchQuery);
  });
}

function renderSkyCurtainList() {
  const list = $("#skyCurtainList");
  if (!list) return;
  const items = filteredSkyCurtains();
  const count = $("#skyCurtainCount");
  if (count) count.textContent = `显示 ${items.length} / ${(skyCurtainCatalog.items || []).length} 套`;
  list.innerHTML = items.length ? items.map((item) => {
    const image = item.images?.gold?.local_path || "";
    const context = [item.category, item.element].filter(Boolean).join(" · ");
    return `<button class="arc-drive-card${item.id === selectedSkyCurtainId ? " is-active" : ""}" type="button" data-sky-curtain-id="${escapeHtml(item.id)}" aria-pressed="${item.id === selectedSkyCurtainId}"><span class="arc-drive-card-image">${image ? `<img src="${escapeHtml(image)}" alt="">` : "幕"}</span><span class="arc-drive-card-copy"><small>${escapeHtml(context || "空幕套装")}</small><b>${escapeHtml(item.name)}</b></span></button>`;
  }).join("") : emptyState("没有符合条件的空幕");
  if (!items.some((item) => item.id === selectedSkyCurtainId)) selectedSkyCurtainId = items[0]?.id || "";
  renderSkyCurtainDetail();
}

function renderSkyCurtainDetail() {
  const target = $("#skyCurtainDetail");
  const item = (skyCurtainCatalog.items || []).find((entry) => entry.id === selectedSkyCurtainId);
  if (!target) return;
  if (!item) {
    target.innerHTML = emptyState("从左侧选择一套空幕查看本地资料");
    return;
  }
  const qualityLabels = { gold: "金", purple: "紫", blue: "蓝" };
  const image = item.images?.[selectedSkyCurtainQuality] || item.images?.gold || Object.values(item.images || {})[0];
  const sourceUrl = item.source?.url || "";
  const effects = item.set_effects || {};
  const renderPool = (title, pool) => {
    const values = pool?.items || [];
    return `<section class="arc-drive-description sky-curtain-pool"><h3>${escapeHtml(title)}</h3>${pool?.note ? `<p>${escapeHtml(pool.note)}</p>` : ""}<div class="sky-curtain-chip-list">${values.length ? values.map((value) => `<span class="sky-curtain-chip">${escapeHtml(value)}</span>`).join("") : `<span class="empty-state">来源页未提供词条池。</span>`}</div></section>`;
  };
  const tierNotes = item.quality?.tiers || [];
  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image">${image?.local_path ? `<img src="${escapeHtml(image.local_path)}" alt="${escapeHtml(item.name)}·${escapeHtml(qualityLabels[selectedSkyCurtainQuality] || "金")}">` : "幕"}</div><div class="arc-drive-detail-title"><span class="sky-curtain-category-chip">${escapeHtml(item.category || "空幕")}${item.element ? ` · ${escapeHtml(item.element)}` : ""}</span><h2>${escapeHtml(item.name)}</h2>${sourceUrl ? `<a class="source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">打开来源详情 ↗</a>` : ""}</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质图片</h3><small>来源页提供的三种品质图</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="空幕品质图片">${Object.entries(qualityLabels).map(([qualityId, label]) => `<button type="button" class="${selectedSkyCurtainQuality === qualityId ? "is-active" : ""}" data-sky-quality="${qualityId}" aria-pressed="${selectedSkyCurtainQuality === qualityId}">${label}</button>`).join("")}</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>套装效果</h3><small>来源页记录的 2 件与 4 件效果</small></div></div><div class="sky-curtain-effect-grid"><div class="sky-curtain-effect-card"><span>2 件套</span><p>${escapeHtml(effects.two_piece || "来源页未提供。")}</p></div><div class="sky-curtain-effect-card"><span>4 件套</span><p>${escapeHtml(effects.four_piece || "来源页未提供。")}</p></div></div>${item.acquisition ? `<div class="arc-drive-description"><h3>获取途径</h3><p>${escapeHtml(item.acquisition)}</p></div>` : ""}</section>${renderPool("主属性可能词条", item.main_affix_pool)}${renderPool("副属性可能词条", item.sub_affix_pool)}<section class="arc-drive-description sky-curtain-quality-note"><h3>品质说明</h3>${item.quality?.role_note ? `<p><b>品质定位：</b>${escapeHtml(item.quality.role_note)}</p>` : ""}${item.quality?.source_note ? `<p><b>品质来源：</b>${escapeHtml(item.quality.source_note)}</p>` : ""}${item.quality?.note ? `<p>${escapeHtml(item.quality.note)}</p>` : ""}${tierNotes.length ? `<ul>${tierNotes.map((tier) => `<li><b>${escapeHtml(tier.quality)}</b><span>${escapeHtml(tier.description)}</span></li>`).join("")}</ul>` : ""}</section>${item.overview ? `<section class="arc-drive-overview"><h3>套装概述</h3><p>${escapeHtml(item.overview)}</p></section>` : ""}`;
}

function initSkyCurtainCatalog() {
  const entries = skyCurtainCatalog.items || [];
  if (!entries.some((item) => item.id === selectedSkyCurtainId)) selectedSkyCurtainId = entries[0]?.id || "";
  const source = skyCurtainCatalog.source || {};
  const attribution = $("#skyCurtainAttribution");
  if (attribution) {
    const indexUrl = skyCurtainCatalog.source_index || "https://wiki.mysqil.com/cassettes/";
    attribution.innerHTML = `资料整理自 <a href="${escapeHtml(indexUrl)}" target="_blank" rel="noreferrer">${escapeHtml(source.site || "Mysqil · 环世全鉴")}</a>；作者 ${escapeHtml(source.author || "Matsuzaka Yuki")}；许可 <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">${escapeHtml(source.license || "CC BY-NC-SA 4.0")}</a>；本地图鉴内容已从来源页提取并结构化整理。`;
  }
  renderSkyCurtainList();
}

function formatDriverBlockValue(value, isPercent = false) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  const formatted = Number.isFinite(number) ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(number) : String(value);
  return `${formatted}${isPercent ? "%" : ""}`;
}

function driverBlockSearchText(item) {
  const tierText = Object.values(item.qualities || {}).flatMap((tier) => [
    tier.grade,
    ...(tier.main_stats || []).map((stat) => stat.name),
    ...(tier.random_stats || []).flatMap((stat) => [stat.name, stat.value])
  ]);
  return [item.name, item.model, item.shape, item.source_index_label, ...(item.qualities ? Object.keys(item.qualities) : []), ...tierText].filter(Boolean).join(" ").toLowerCase();
}

function filteredDriverBlocks() {
  return (driverBlockCatalog.items || []).filter((item) => {
    if (driverBlockModelFilter !== "all" && item.model !== driverBlockModelFilter) return false;
    return !driverBlockSearchQuery || driverBlockSearchText(item).includes(driverBlockSearchQuery);
  });
}

function renderDriverBlockList() {
  const list = $("#driverBlockList");
  if (!list) return;
  const items = filteredDriverBlocks();
  if (!items.some((item) => item.id === selectedDriverBlockId)) selectedDriverBlockId = items[0]?.id || "";
  const count = $("#driverBlockCount");
  if (count) count.textContent = `显示 ${items.length} / ${(driverBlockCatalog.items || []).length} 种形状 · 每种 3 档`;
  list.innerHTML = items.length ? items.map((item) => {
    const tier = item.qualities?.[selectedDriverBlockQuality] || item.qualities?.gold;
    const image = tier?.images?.[selectedDriverBlockQuality]?.local_path || tier?.images?.gold?.local_path || "";
    return `<button class="arc-drive-card driver-block-card${item.id === selectedDriverBlockId ? " is-active" : ""}" type="button" data-driver-block-id="${escapeHtml(item.id)}" aria-pressed="${item.id === selectedDriverBlockId}"><span class="arc-drive-card-image">${image ? `<img src="${escapeHtml(image)}" alt="">` : "块"}</span><span class="arc-drive-card-copy"><small>${escapeHtml(item.model)} · ${escapeHtml(item.shape || `${item.grid_count} 格`)}</small><b>${escapeHtml(item.name || "驱动块")}</b></span></button>`;
  }).join("") : emptyState("没有符合条件的驱动块");
  renderDriverBlockDetail();
}

function renderDriverBlockDetail() {
  const target = $("#driverBlockDetail");
  const item = (driverBlockCatalog.items || []).find((entry) => entry.id === selectedDriverBlockId);
  if (!target) return;
  if (!item) {
    target.innerHTML = emptyState("从左侧选择一种驱动块形状查看本地资料");
    return;
  }
  const qualityLabels = { gold: "金", purple: "紫", blue: "蓝" };
  const tier = item.qualities?.[selectedDriverBlockQuality] || item.qualities?.gold;
  if (!tier) {
    target.innerHTML = emptyState("来源页没有这档品质的数据");
    return;
  }
  const level = Math.min(tier.level?.max ?? 20, Math.max(tier.level?.min ?? 0, selectedDriverBlockLevel));
  selectedDriverBlockLevel = level;
  const levelIndex = level - (tier.level?.min ?? 0);
  const image = tier.images?.[selectedDriverBlockQuality];
  const sourceUrl = tier.source_page?.url || "";
  const mainStats = tier.main_stats || [];
  const randomStats = tier.random_stats || [];
  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image driver-block-artwork">${image?.local_path ? `<img src="${escapeHtml(image.local_path)}" alt="${escapeHtml(item.model)} ${escapeHtml(item.shape)} · ${qualityLabels[selectedDriverBlockQuality]}">` : "块"}</div><div class="arc-drive-detail-title"><span class="rarity-chip rarity-${escapeHtml(tier.grade.toLowerCase())}">${escapeHtml(item.model)} · ${escapeHtml(qualityLabels[selectedDriverBlockQuality])}色 ${escapeHtml(tier.grade)}级</span><h2>${escapeHtml(item.model)} · ${escapeHtml(item.shape || `${item.grid_count} 格`)}</h2><p>${escapeHtml(item.grid_count)} 格 · ${tier.random_slot_count} 个随机副词条槽 · ${randomStats.length} 种候选词条</p>${sourceUrl ? `<a class="source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">打开当前品质来源 ↗</a>` : ""}</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质与形状图</h3><small>来源页保留了三档品质的原图</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="驱动块品质">${Object.entries(qualityLabels).map(([qualityId, label]) => { const qualityTier = item.qualities?.[qualityId]; return `<button type="button" class="${selectedDriverBlockQuality === qualityId ? "is-active" : ""}" data-driver-quality="${qualityId}" aria-pressed="${selectedDriverBlockQuality === qualityId}">${label} ${escapeHtml(qualityTier?.grade || "")}</button>`; }).join("")}</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>固定主属性</h3><small>来源页记录的强化等级成长值</small></div><label class="driver-block-level-control">强化 +<output id="driverBlockLevelValue">${level}</output><input id="driverBlockLevel" type="range" min="${tier.level?.min ?? 0}" max="${tier.level?.max ?? 20}" value="${level}" aria-label="驱动块强化等级"></label></div><div class="arc-stat-grid">${mainStats.map((stat, index) => `<div class="arc-stat-card"><span>${escapeHtml(stat.name || "主属性")}</span><b data-driver-main-stat="${index}">${escapeHtml(formatDriverBlockValue(stat.values?.[levelIndex]))}</b></div>`).join("")}</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>随机副属性</h3><small>每块装备 ${tier.random_slot_count} 条；以下为来源页列出的候选值</small></div><span class="driver-block-pool-count">${randomStats.length} 种</span></div><div class="driver-block-stat-grid">${randomStats.map((stat) => `<div class="driver-block-stat-option">${stat.icon?.local_path ? `<img src="${escapeHtml(stat.icon.local_path)}" alt="">` : ""}<span>${escapeHtml(stat.name)}</span><b>${escapeHtml(formatDriverBlockValue(stat.value, stat.is_percent))}</b></div>`).join("")}</div></section>`;
}

function renderDriverBlockGuide() {
  const target = $("#driverBlockGuideContent");
  if (!target) return;
  const guide = driverBlockCatalog.mechanism_guide || {};
  const sections = guide.sections || [];
  const renderBlock = (block) => {
    if (block.type === "paragraph") return `<p>${escapeHtml(block.text)}</p>`;
    if (block.type === "heading") return `<h4>${escapeHtml(block.text)}</h4>`;
    if (block.type === "list") return `<ul>${(block.items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    if (block.type === "table") {
      const [head, ...rows] = block.rows || [];
      return `<div class="driver-block-guide-table-wrap"><table><thead><tr>${(head || []).map((cell) => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    return "";
  };
  target.innerHTML = sections.length ? sections.map((section) => `<section class="driver-block-guide-section"><h3>${escapeHtml(section.title)}</h3>${(section.content || []).map(renderBlock).join("")}</section>`).join("") : `<p class="empty-state">机制说明快照暂不可用。</p>`;
  const sourceNotes = guide.secondary_source_notes || [];
  if (sourceNotes.length) target.insertAdjacentHTML("beforeend", `<p class="driver-block-guide-note">${sourceNotes.map(escapeHtml).join("<br>")}</p>`);
}

function initDriverBlockCatalog() {
  const entries = driverBlockCatalog.items || [];
  if (!entries.some((item) => item.id === selectedDriverBlockId)) selectedDriverBlockId = entries[0]?.id || "";
  const source = driverBlockCatalog.source || {};
  const indexUrl = driverBlockCatalog.source_index || "https://wiki.mysqil.com/drivers";
  const guideUrl = driverBlockCatalog.mechanism_guide?.source?.url || "https://wiki.mysqil.com/cassettes/drivers";
  const attribution = $("#driverBlockAttribution");
  if (attribution) {
    attribution.innerHTML = `资料整理自 <a href="${escapeHtml(indexUrl)}" target="_blank" rel="noreferrer">${escapeHtml(source.site || "Mysqil · 环世全鉴")}</a>，机制说明见<a href="${escapeHtml(guideUrl)}" target="_blank" rel="noreferrer">攻略原文</a>；作者 ${escapeHtml(source.source_author || "Matsuzaka Yuki")}；许可 <a href="${escapeHtml(source.source_license_url || "https://creativecommons.org/licenses/by-nc-sa/4.0/")}" target="_blank" rel="noreferrer">${escapeHtml(source.source_license || "CC BY-NC-SA 4.0")}</a>；本地图鉴从来源页提取并结构化，攻略页列出的二级资料来源与“以游戏内为准”说明已保留。`;
  }
  renderDriverBlockList();
  renderDriverBlockGuide();
}

function showRoleManagement() {
  document.body.classList.remove("user-mode");
  $("#userExperienceView").hidden = true;
  $("#adminTopbarActions").hidden = false;
  $("#userTopbarActions").hidden = true;
  $("#roleManagementView").hidden = false;
  $("#encyclopediaView").hidden = true;
  $("#previewButton").hidden = false;
  $("#saveDraftButton").hidden = false;
  setText("#activeBreadcrumb", "角色管理");
  $("[data-nav='角色管理']")?.classList.add("is-active");
  $("#encyclopediaNavTrigger")?.classList.remove("is-active");
  $$('[data-encyclopedia-kind]').forEach((item) => item.classList.remove("is-active"));
}
function showEncyclopediaCategory(kind) {
  document.body.classList.remove("user-mode");
  $("#userExperienceView").hidden = true;
  $("#adminTopbarActions").hidden = true;
  $("#userTopbarActions").hidden = true;

  const labels = { "arc-drives": "弧盘", cassettes: "空幕", "drive-blocks": "驱动块" };
  const label = labels[kind] || "图鉴";
  const hasArcDriveCatalog = kind === "arc-drives";
  const hasSkyCurtainCatalog = kind === "cassettes";
  const hasDriverBlockCatalog = kind === "drive-blocks";
  const hasCatalog = hasArcDriveCatalog || hasSkyCurtainCatalog || hasDriverBlockCatalog;
  $$("[data-nav]").forEach((item) => item.classList.remove("is-active"));
  $("#encyclopediaNavTrigger")?.classList.add("is-active");
  $$("[data-encyclopedia-kind]").forEach((item) => item.classList.toggle("is-active", item.dataset.encyclopediaKind === kind));
  $("#roleManagementView").hidden = true;
  $("#encyclopediaView").hidden = false;
  $("#previewButton").hidden = true;
  $("#saveDraftButton").hidden = true;
  $("#arcCatalogPanel").hidden = !hasArcDriveCatalog;
  $("#skyCurtainPanel").hidden = !hasSkyCurtainCatalog;
  $("#driverBlockPanel").hidden = !hasDriverBlockCatalog;
  $("#encyclopediaEmptyState").hidden = hasCatalog;
  setText("#activeBreadcrumb", `图鉴 · ${label}`);
  setText("#encyclopediaTitle", label);
  setText("#encyclopediaCount", hasArcDriveCatalog ? `${(arcDriveCatalog.items || []).length} 件本地资料` : hasSkyCurtainCatalog ? `${(skyCurtainCatalog.items || []).length} 套本地资料` : hasDriverBlockCatalog ? `${(driverBlockCatalog.items || []).length} 种形状 · ${driverBlockCatalog.page_count || 0} 档品质` : "资料待接入");
  setText("#encyclopediaDescription", hasArcDriveCatalog ? "浏览弧盘属性、等级成长与调弧效果。" : hasSkyCurtainCatalog ? "浏览空幕套装效果、可能词条与品质图片。" : hasDriverBlockCatalog ? "查看驱动块形状、三档品质成长、4 槽随机词条与来源机制说明。" : `${label}分类入口已建立；本地资料接入后会在这里展示。`);
  setText("#emptyCategoryTitle", label);
}

function bindArcDriveCatalog() {
  $("#arcDriveSearch")?.addEventListener("input", (event) => {
    arcDriveSearchQuery = event.target.value.trim().toLowerCase();
    renderArcDriveList();
  });
  $$('[data-arc-rarity]').forEach((button) => button.addEventListener("click", () => {
    arcDriveRarityFilter = button.dataset.arcRarity;
    $$('[data-arc-rarity]').forEach((item) => item.classList.toggle("is-active", item === button));
    renderArcDriveList();
  }));
  $$('[data-arc-type]').forEach((button) => button.addEventListener("click", () => {
    arcDriveTypeFilter = button.dataset.arcType;
    $$('[data-arc-type]').forEach((item) => item.classList.toggle("is-active", item === button));
    renderArcDriveList();
  }));
  $("#arcDriveList")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-arc-drive-id]");
    if (!card) return;
    selectedArcDriveId = card.dataset.arcDriveId;
    selectedArcDriveLevel = 80;
    selectedArcDriveRank = 1;
    renderArcDriveList();
  });
  $("#arcDriveDetail")?.addEventListener("change", (event) => {
    if (event.target.id !== "arcDriveLevel") return;
    selectedArcDriveLevel = Number(event.target.value);
    renderArcDriveDetail();
  });
  $("#arcDriveDetail")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-arc-rank]");
    if (!button) return;
    selectedArcDriveRank = Number(button.dataset.arcRank);
    renderArcDriveDetail();
  });
}

function bindSkyCurtainCatalog() {
  $("#skyCurtainSearch")?.addEventListener("input", (event) => {
    skyCurtainSearchQuery = event.target.value.trim().toLowerCase();
    renderSkyCurtainList();
  });
  $$('[data-sky-category]').forEach((button) => button.addEventListener("click", () => {
    skyCurtainCategoryFilter = button.dataset.skyCategory;
    $$('[data-sky-category]').forEach((item) => item.classList.toggle("is-active", item === button));
    renderSkyCurtainList();
  }));
  $$('[data-sky-element]').forEach((button) => button.addEventListener("click", () => {
    skyCurtainElementFilter = button.dataset.skyElement;
    $$('[data-sky-element]').forEach((item) => item.classList.toggle("is-active", item === button));
    renderSkyCurtainList();
  }));
  $("#skyCurtainList")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-sky-curtain-id]");
    if (!card) return;
    selectedSkyCurtainId = card.dataset.skyCurtainId;
    selectedSkyCurtainQuality = "gold";
    renderSkyCurtainList();
  });
  $("#skyCurtainDetail")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sky-quality]");
    if (!button) return;
    selectedSkyCurtainQuality = button.dataset.skyQuality;
    renderSkyCurtainDetail();
  });
}

function bindDriverBlockCatalog() {
  $("#driverBlockSearch")?.addEventListener("input", (event) => {
    driverBlockSearchQuery = event.target.value.trim().toLowerCase();
    renderDriverBlockList();
  });
  $$('[data-driver-model]').forEach((button) => button.addEventListener("click", () => {
    driverBlockModelFilter = button.dataset.driverModel;
    $$('[data-driver-model]').forEach((item) => item.classList.toggle("is-active", item === button));
    renderDriverBlockList();
  }));
  $("#driverBlockList")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-driver-block-id]");
    if (!card) return;
    selectedDriverBlockId = card.dataset.driverBlockId;
    selectedDriverBlockQuality = "gold";
    selectedDriverBlockLevel = 20;
    renderDriverBlockList();
  });
  $("#driverBlockDetail")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-driver-quality]");
    if (!button) return;
    selectedDriverBlockQuality = button.dataset.driverQuality;
    selectedDriverBlockLevel = 20;
    renderDriverBlockList();
  });
  $("#driverBlockDetail")?.addEventListener("input", (event) => {
    if (event.target.id !== "driverBlockLevel") return;
    selectedDriverBlockLevel = Number(event.target.value);
    const item = driverBlockCatalog.items.find((entry) => entry.id === selectedDriverBlockId);
    const tier = item?.qualities?.[selectedDriverBlockQuality];
    const levelIndex = selectedDriverBlockLevel - (tier?.level?.min ?? 0);
    const output = $("#driverBlockLevelValue");
    if (output) output.value = String(selectedDriverBlockLevel);
    (tier?.main_stats || []).forEach((stat, index) => {
      const value = $(`[data-driver-main-stat="${index}"]`);
      if (value) value.textContent = formatDriverBlockValue(stat.values?.[levelIndex]);
    });
  });
}

function bindEncyclopediaNavigation() {
  const trigger = $("#encyclopediaNavTrigger");
  const submenu = $("#encyclopediaSubnav");
  trigger?.addEventListener("click", () => {
    const expanded = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", String(!expanded));
    submenu.hidden = expanded;
  });
  $$("[data-encyclopedia-kind]").forEach((button) => button.addEventListener("click", () => showEncyclopediaCategory(button.dataset.encyclopediaKind)));
}

function bindNavigation() {
  $$("[data-nav]").forEach((item) => item.addEventListener("click", () => {
    $$("[data-nav]").forEach((nav) => nav.classList.remove("is-active"));
    item.classList.add("is-active");
    if (item.dataset.nav === "角色管理") showRoleManagement();
    else notify(`「${item.dataset.nav}」模块将在下一阶段接入`);
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
    if (activeKnowledge) {
      calculateMaterials(activeKnowledge);
      notify("已按当前目标汇总养成材料");
    }
  });
}
function bindMisc() {
  const optionalBindings = [
    ["#workspaceSwitch", () => notify("当前工作区：角色资料库")],
    ["#profileButton", () => notify("林维护者 · 编辑权限")],
    ["#previewButton", showUserExperience],
    ["#explainButton", () => notify("概览来自基础资料、技能和觉醒数据")],
    ["#moreButton", () => notify("更多操作：停用、复制为新角色、查看历史版本")],
    ["#reactionSelect", () => notify(activeKnowledge?.mechanism_facts?.reaction_enhancement_text || "当前角色来源页未提供反应强化资料")],
    ["#submitReviewButton", () => { setText("#draftLabel", "待审核"); notify("已提交角色资料审核"); }],
    ["#recalculateButton", () => activeKnowledge && calculateMaterials(activeKnowledge)]
  ];
  optionalBindings.forEach(([selector, handler]) => { const element = $(selector); if (element) element.addEventListener("click", handler); });
  ["#targetLevel"].forEach((selector) => { const element = $(selector); if (element) element.addEventListener("change", () => activeKnowledge && calculateMaterials(activeKnowledge)); });
}
renderCharacterCards();
bindCharacterCards();
bindNavigation();
bindEncyclopediaNavigation();
initArcDriveCatalog();
bindArcDriveCatalog();
initSkyCurtainCatalog();
bindSkyCurtainCatalog();
initDriverBlockCatalog();
bindDriverBlockCatalog();
bindSearch();
bindBasicPreview();
bindModes();
bindSave();
bindImpact();
bindMisc();
bindDriveLayoutUpload();
bindUserExperience();
showUserExperience();
applyCharacter(selectedCharacter);

function userAsset(knowledge, type) {
  const asset = (knowledge.assets || []).find((item) => item.type === type);
  return asset ? importedAssetUrl(asset) : "";
}

function userMediaMarkup(src, alt, fallback) {
  return src ? `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy">` : `<span class="user-media-fallback">${escapeHtml(fallback)}</span>`;
}

function userSkillTargetValue(knowledge, skill, index, targets = userSkillTargets) {
  const levels = skillTargetOptions(skill);
  const key = `${knowledge?.id || "unknown"}:${index}`;
  const selected = Number(targets?.[key]);
  return levels.includes(selected) ? selected : Math.max(...levels);
}

function userMaterialEntries(knowledge, targetLevel, targets = userSkillTargets) {
  const totals = new Map();
  const add = (id, amount) => totals.set(id, (totals.get(id) || 0) + amount);
  (knowledge.cultivation?.ascension || []).filter((step) => step.level <= targetLevel).forEach((step) => (step.items || []).forEach((item) => add(item.id, item.amount)));
  (knowledge.cultivation?.skills || []).forEach((skill, index) => {
    const skillTargetLevel = userSkillTargetValue(knowledge, skill, index, targets);
    (skill.levels || []).filter((step) => step.level <= skillTargetLevel).forEach((step) => (step.items || []).forEach((item) => add(item.id, item.amount)));
  });
  const catalog = knowledge.cultivation?.material_catalog || {};
  return [...totals.entries()].map(([id, amount]) => ({ id, amount, name: catalog[id]?.name || id, icon: materialAsset(knowledge, id) }));
}

function userCharacterEntries() {
  const entries = Object.entries(characterData).sort(([nameA, a], [nameB, b]) => {
    const rarityOrder = { S: 0, A: 1, B: 2 };
    return (rarityOrder[a.rarity] ?? 3) - (rarityOrder[b.rarity] ?? 3) || nameA.localeCompare(nameB, "zh-CN");
  });
  return entries.filter(([name, data]) => {
    if (!userCharacterSearchQuery) return true;
    return [name, data.role, data.element, data.sourcePosition].filter(Boolean).join(" ").toLowerCase().includes(userCharacterSearchQuery);
  });
}

function userCarouselNormalize(index, length) {
  return ((index % length) + length) % length;
}

function userCarouselSetPosition(animate = true) {
  const viewport = $("#userCharacterCarouselViewport");
  const track = $("#userCharacterCarouselTrack");
  const firstCard = track?.querySelector(".user-character-card");
  if (!viewport || !track || !firstCard) return;
  const cardWidth = firstCard.offsetWidth;
  const gap = Number.parseFloat(getComputedStyle(track).gap) || 12;
  const offset = viewport.clientWidth / 2 - (userCarouselCursor * (cardWidth + gap) + cardWidth / 2) + userCarouselDragOffset;
  if (animate) track.style.removeProperty("transition");
  else track.style.transition = "none";
  track.style.transform = `translate3d(${offset}px, 0, 0)`;
  if (!animate) window.requestAnimationFrame(() => {
    if (!userCarouselDrag && track.isConnected) track.style.removeProperty("transition");
  });
}

function userCarouselUpdateActive(entries) {
  const track = $("#userCharacterCarouselTrack");
  if (!track || !entries.length) return;
  const activeIndex = userCarouselNormalize(userCarouselCursor, entries.length);
  track.querySelectorAll("[data-user-character]").forEach((card) => {
    const position = Number(card.dataset.carouselPosition);
    const isActive = position === userCarouselCursor;
    const isNear = Math.abs(position - userCarouselCursor) <= 2;
    card.classList.toggle("is-active", isActive);
    card.classList.toggle("is-near", !isActive && isNear);
    card.setAttribute("aria-pressed", String(isActive));
  });

}

function renderUserCharacterRail() {
  const rail = $("#userCharacterRail");
  if (!rail) return;
  const entries = userCharacterEntries();
  const totalEntries = Object.keys(characterData).length;
  setText("#userCharacterCount", `${entries.length} / ${totalEntries} 位角色`);
  if (!entries.length) {
    rail.innerHTML = `<div class="user-empty user-carousel-empty">没有找到匹配的角色。</div>`;
    return;
  }
  const selectedIndex = Math.max(0, entries.findIndex(([name]) => name === selectedCharacter));
  userCarouselCursor = entries.length + selectedIndex;
  const cards = [...entries, ...entries, ...entries].map(([name, data], position) => `
    <button class="user-character-card" type="button" data-user-character="${escapeHtml(name)}" data-carousel-position="${position}" aria-pressed="false" aria-label="打开${escapeHtml(name)}角色资料">
      <span class="user-character-avatar">${data.icon ? `<img src="${escapeHtml(data.icon)}" alt="" loading="lazy">` : escapeHtml(name.slice(0, 1))}</span>
      <span class="user-character-copy"><b>${escapeHtml(name)}</b><span>${escapeHtml([data.role, data.sourcePosition].filter(Boolean).join(" · ") || "定位待补充")}</span></span>
      <span class="user-character-element">${escapeHtml(data.element || "?")}</span>
    </button>`).join("");
  rail.innerHTML = `<button class="user-carousel-arrow pressable" type="button" data-user-carousel="prev" aria-label="上一个角色"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m14.5 5-7 7 7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="user-character-carousel-viewport" id="userCharacterCarouselViewport"><div class="user-character-carousel-track" id="userCharacterCarouselTrack">${cards}</div></div><button class="user-carousel-arrow pressable" type="button" data-user-carousel="next" aria-label="下一个角色"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9.5 5 7 7-7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>`;
  window.requestAnimationFrame(() => {
    userCarouselSetPosition(false);
    userCarouselUpdateActive(entries);
  });
}

function userCarouselCommit(entries, cursor) {
  const [name] = entries[userCarouselNormalize(cursor, entries.length)];
  applyCharacter(name, { skipUserRail: true, silent: true });
  userCarouselUpdateActive(entries);
}

function userCarouselMove(direction) {
  const entries = userCharacterEntries();
  if (entries.length < 2 || !direction) return;
  const length = entries.length;
  if (direction > 0 && userCarouselCursor >= length * 2 - 1) {
    userCarouselCursor = length - 1;
    userCarouselSetPosition(false);
  } else if (direction < 0 && userCarouselCursor <= length) {
    userCarouselCursor = length * 2;
    userCarouselSetPosition(false);
  }
  userCarouselCursor += direction;
  userCarouselDragOffset = 0;
  userCarouselSetPosition(true);
  userCarouselCommit(entries, userCarouselCursor);
}

function userCarouselMoveTo(position) {
  const entries = userCharacterEntries();
  if (entries.length < 2) return;
  const targetIndex = userCarouselNormalize(Number(position), entries.length);
  const currentIndex = userCarouselNormalize(userCarouselCursor, entries.length);
  let delta = targetIndex - currentIndex;
  if (delta > entries.length / 2) delta -= entries.length;
  if (delta < -entries.length / 2) delta += entries.length;
  if (!delta) return;
  if (Math.abs(delta) === 1) {
    userCarouselMove(Math.sign(delta));
    return;
  }
  userCarouselCursor = entries.length + targetIndex;
  userCarouselDragOffset = 0;
  userCarouselSetPosition(true);
  userCarouselCommit(entries, userCarouselCursor);
}

function userCarouselSelectCard(name) {
  const entries = userCharacterEntries();
  if (entries.length < 2 || !name) return;
  const targetIndex = entries.findIndex(([entryName]) => entryName === name);
  if (targetIndex < 0) return;
  const currentIndex = userCarouselNormalize(userCarouselCursor, entries.length);
  if (targetIndex === currentIndex && name === selectedCharacter) return;
  userCarouselCursor = entries.length + targetIndex;
  userCarouselDragOffset = 0;
  userCarouselSetPosition(true);
  userCarouselCommit(entries, userCarouselCursor);
}
function bindUserCarouselPointer() {
  const rail = $("#userCharacterRail");
  if (!rail) return;
  const finish = (event) => {
    if (!userCarouselDrag || event.pointerId !== userCarouselDrag.pointerId) return;
    const drag = userCarouselDrag;
    const dx = event.clientX - drag.startX;
    const elapsed = Math.max(1, performance.now() - drag.startTime);
    const velocity = (dx / elapsed) * 1000;
    const viewport = $("#userCharacterCarouselViewport");
    const threshold = Math.max(28, (viewport?.clientWidth || 320) * 0.08);
    const direction = Math.abs(dx) >= threshold || Math.abs(velocity) >= 420 ? (dx < 0 ? 1 : -1) : 0;
    userCarouselDrag = null;
    userCarouselDragOffset = 0;
    rail.querySelector(".user-character-carousel-track")?.classList.remove("is-dragging");
    if (rail.hasPointerCapture?.(event.pointerId)) rail.releasePointerCapture(event.pointerId);
    if (drag.moved) {
      userCarouselSuppressClick = true;
      window.setTimeout(() => { userCarouselSuppressClick = false; }, 0);
      if (direction) userCarouselMove(direction);
      else {
        userCarouselSetPosition(true);
        userCarouselUpdateActive(userCharacterEntries());
      }
    } else if (drag.tapName) {
      userCarouselSelectCard(drag.tapName);
    }
  };
  rail.addEventListener("pointerdown", (event) => {
    const viewport = event.target.closest(".user-character-carousel-viewport");
    if (!viewport || (event.pointerType === "mouse" && event.button !== 0)) return;
    const track = viewport.querySelector(".user-character-carousel-track");
    userCarouselDrag = { pointerId: event.pointerId, startX: event.clientX, startTime: performance.now(), moved: false, tapName: event.target.closest("[data-user-character]")?.dataset.userCharacter || "" };
    userCarouselDragOffset = 0;
    rail.setPointerCapture?.(event.pointerId);
    track?.classList.add("is-dragging");
  });
  rail.addEventListener("pointermove", (event) => {
    if (!userCarouselDrag || event.pointerId !== userCarouselDrag.pointerId) return;
    const dx = event.clientX - userCarouselDrag.startX;
    if (Math.abs(dx) < 8 && !userCarouselDrag.moved) return;
    userCarouselDrag.moved = true;
    userCarouselDragOffset = dx;
    userCarouselSetPosition(false);
  });
  rail.addEventListener("pointerup", finish);
  rail.addEventListener("pointercancel", finish);
}

function renderUserHero(knowledge) {
  const target = $("#userHeroCard");
  if (!target || !knowledge) return;
  const basic = knowledge.basic || {};
  const facts = knowledge.mechanism_facts || {};
  const portrait = userAsset(knowledge, "character_portrait");
  const tags = [basic.element, basic.role, basic.position, basic.cassette_type].filter(Boolean);
  target.innerHTML = `<div class="user-hero-copy"><span class="user-hero-kicker"><i></i>${escapeHtml(basic.rarity || "角色")} · ${escapeHtml(basic.rating || "资料已整理")}</span><h2>${escapeHtml(knowledge.name)}</h2><p>${escapeHtml(basic.summary || "从技能机制、推荐配装到养成材料，查看这名角色的完整资料。")}</p><div class="user-hero-tags">${tags.map((tag) => `<span class="user-hero-tag">${escapeHtml(tag)}</span>`).join("")}</div><div class="user-hero-actions"><button class="user-hero-action pressable" type="button" data-user-action="build">查看推荐配装</button><button class="user-hero-action secondary pressable" type="button" data-user-action="skills">${escapeHtml(facts.primary_reaction || "查看技能机制")}</button></div></div><div class="user-hero-art">${portrait ? `<img src="${escapeHtml(portrait)}" alt="${escapeHtml(knowledge.name)}立绘">` : `<span class="user-hero-art-fallback">${escapeHtml(knowledge.name.slice(0, 1))}</span>`}</div>`;
}

function userBuildCard(data, type, fallback, extra = "") {
  if (!data) return `<div class="user-empty">暂无${escapeHtml(type)}建议。</div>`;
  const image = data.asset || data.icon || "";
  return `<article class="user-build-card">${userMediaMarkup(image, data.name || type, fallback)}<div class="user-build-card-copy"><span>${escapeHtml(type)}${data.rating ? ` · ${escapeHtml(data.rating)}级` : ""}</span><b>${escapeHtml(data.name || "待补充")}</b><small>${escapeHtml(extra || data.description || data.cassette_type || "来源资料已整理")}</small></div></article>`;
}

function factsForUser(knowledge) {
  const facts = knowledge.mechanism_facts || {};
  return facts.primary_reaction ? `${knowledge.name}围绕「${facts.primary_reaction}」展开。` : `${knowledge.name}的技能和养成资料已准备好。`;
}

function renderUserOverview(knowledge) {
  const basic = knowledge.basic || {};
  const skills = knowledge.skills || [];
  const materials = userMaterialEntries(knowledge, knowledge.base_stats?.level_cap || 80, userSkillTargets);
  const recommended = knowledge.recommended || {};
  return `<section class="user-section-heading"><div><span class="user-section-kicker">角色概览</span><h2>先知道怎么用，再决定怎么养。</h2><p>${escapeHtml(factsForUser(knowledge))}</p></div></section><div class="user-overview-grid"><article class="user-metric-card"><span>定位</span><b>${escapeHtml(basic.role || "待补充")}</b><small>${escapeHtml(basic.position || "站位待补充")}</small></article><article class="user-metric-card"><span>技能资料</span><b>${skills.length}</b><small>项结构化技能</small></article><article class="user-metric-card"><span>养成材料</span><b>${materials.length}</b><small>种材料汇总</small></article><article class="user-metric-card"><span>等级上限</span><b>Lv.${knowledge.base_stats?.level_cap || "—"}</b><small>基础属性成长</small></article></div><div class="user-overview-columns"><section class="user-surface"><div class="user-section-heading"><div><span class="user-section-kicker">推荐起点</span><h2>先从这套配置开始。</h2></div><button class="user-text-action pressable" type="button" data-user-action="build">查看完整配装 →</button></div><div class="user-build-grid">${userBuildCard(recommended.weapon, "推荐武器", "武", recommended.weapon?.rating ? `${recommended.weapon.rating}级推荐` : "来源资料已整理")}${userBuildCard(recommended.cassette, "推荐空幕", "幕", recommended.cassette?.acquisition || "获取方式待补充")}</div></section><section class="user-surface user-highlight-card"><span class="user-section-kicker">玩法提示</span><div><h3>${escapeHtml(basic.role || "这个角色")}的核心是把机制用在正确时机。</h3><p>进入技能页查看完整描述，再到养成页按你的实际目标规划材料。</p></div><div class="user-highlight-foot"><span>资料来源</span><strong>本地知识包</strong></div></section></div>`;
}

function userSkillCard(skill, index) {
  const summary = skill.description_parts?.map((part) => `${part.name || ""}${part.text || ""}`).join(" ") || skill.raw_text || "来源页未提供技能摘要。";
  const parameters = skill.parameters || [];
  return `<article class="user-skill-card"><div class="user-skill-card-head"><div><span>${escapeHtml(skill.category || `技能 ${index + 1}`)}</span><b>${escapeHtml(skill.name || "未命名技能")}</b></div><span class="user-skill-level">${skill.level_cap ? `Lv.${skill.level_cap}` : "机制"}</span></div><p>${escapeHtml(summary.slice(0, 180))}</p>${parameters.length ? `<div class="user-skill-parameters">${parameters.slice(0, 3).map((parameter) => `<span class="user-skill-parameter">${escapeHtml(parameter.label)} · ${escapeHtml(parameter.current_value || parameter.values?.[0] || "—")}</span>`).join("")}</div>` : ""}</article>`;
}

function renderUserSkills(knowledge) {
  const skills = knowledge.skills || [];
  return `<section class="user-section-heading"><div><span class="user-section-kicker">技能资料</span><h2>把机制讲清楚。</h2><p>先看每项技能的作用，再展开完整倍率和升级信息。</p></div></section>${skills.length ? `<div class="user-skills-grid">${skills.map((skill, index) => userSkillCard(skill, index)).join("")}</div>` : `<div class="user-empty">当前角色暂无可展示的技能资料。</div>`}`;
}

function renderUserBuild(knowledge) {
  const recommended = knowledge.recommended || {};
  const cassette = recommended.cassette;
  const mainAffixes = renderAffixRanking(recommendedAffixes(cassette, "main"));
  const subAffixes = renderAffixRanking(recommendedAffixes(cassette, "sub"));
  return `<section class="user-section-heading"><div><span class="user-section-kicker">配装建议</span><h2>从一套舒服的配置开始。</h2><p>推荐属性按优先级排列；同一优先级代表近似选择，不等于唯一答案。</p></div></section><div class="user-build-layout"><section class="user-surface user-build-large"><div class="user-build-grid">${userBuildCard(recommended.weapon, "推荐武器", "武", recommended.weapon?.rating ? `${recommended.weapon.rating}级推荐` : "来源资料已整理")}${userBuildCard(cassette, "推荐空幕", "幕", cassette?.acquisition || "获取方式待补充")}</div><div class="user-affix-groups"><div class="user-affix-group"><span>推荐主属性</span><div class="user-affix-ranking">${mainAffixes}</div></div><div class="user-affix-group"><span>推荐副属性</span><div class="user-affix-ranking">${subAffixes}</div></div></div><div class="user-source-note"><i></i><span>原始可能词条池与维护者推荐已分开保存。</span></div></section><div class="user-surface user-empty">终端与细节资料请在来源页核对。</div></div>`;
}

function renderUserCultivation(knowledge) {
  const levelCap = knowledge.base_stats?.level_cap || 80;
  const levelOptions = [...new Set([30, 40, 50, 60, 70, levelCap].filter((level) => level <= levelCap))];
  if (!levelOptions.includes(Number(userTargetLevel))) userTargetLevel = levelOptions[levelOptions.length - 1] || levelCap;
  const entries = userMaterialEntries(knowledge, userTargetLevel, userSkillTargets);
  const skills = knowledge.cultivation?.skills || [];
  const skillTargetMarkup = skills.length ? `<div class="user-skill-targets"><div class="user-skill-targets-head"><div><span>技能目标</span><b>每项技能单独规划</b><small>默认按各技能最高等级计算，调整后材料会立即更新。</small></div><em>${skills.length} 项</em></div><div class="user-skill-target-grid">${skills.map((skill, index) => { const levels = skillTargetOptions(skill); const selected = userSkillTargetValue(knowledge, skill, index); const fixed = levels.length === 1; return `<label class="user-skill-target-row"><span><b>${escapeHtml(skill.name || `技能 ${index + 1}`)}</b><small>${fixed ? "固定节点" : `可选至 Lv.${Math.max(...levels)}`}</small></span><select data-user-skill-target="${index}" ${fixed ? "disabled" : ""}>${levels.map((level) => `<option value="${level}"${level === selected ? " selected" : ""}>Lv.${level}</option>`).join("")}</select></label>`; }).join("")}</div></div>` : `<div class="user-skill-targets user-empty">当前角色暂无结构化技能养成节点。</div>`;
  return `<section class="user-section-heading"><div><span class="user-section-kicker">养成规划</span><h2>知道还差多少。</h2><p>角色等级与每项技能目标分开设置，材料汇总会跟着你的选择变化。</p></div><label class="user-level-control"><span>角色目标</span><select id="userTargetLevel">${levelOptions.map((level) => `<option value="${level}"${level === userTargetLevel ? " selected" : ""}>Lv.${level}</option>`).join("")}</select></label></section><div class="user-cultivation-layout"><section class="user-surface"><div class="user-section-heading"><div><span class="user-section-kicker">材料清单</span><h2>${entries.length} 种材料</h2></div></div>${skillTargetMarkup}${entries.length ? `<div class="user-material-grid">${entries.map((entry) => `<article class="user-material-card">${userMediaMarkup(entry.icon, entry.name, "材")}<div><b>${escapeHtml(entry.name)}</b><span>${entry.amount.toLocaleString()}</span></div></article>`).join("")}</div>` : `<div class="user-empty">来源页暂未提供结构化养成材料。</div>`}</section><aside class="user-surface user-cultivation-summary"><span class="user-section-kicker">目标状态</span><h3>Lv.${userTargetLevel}</h3><p>角色等级与 ${skills.length || 0} 项技能目标已分别计入材料汇总。</p><ul><li><span>角色等级上限</span><b>Lv.${levelCap}</b></li><li><span>技能目标</span><b>${skills.length ? `${skills.length} 项已设置` : "暂无"}</b></li><li><span>预计材料种类</span><b>${entries.length} 种</b></li></ul></aside></div>`;
}

function renderUserTabPanel(knowledge) {
  const panel = $("#userTabPanel");
  if (!panel || !knowledge) return;
  $$('[data-user-tab]').forEach((button) => button.classList.toggle('is-active', button.dataset.userTab === userActiveTab));
  panel.innerHTML = userActiveTab === "skills" ? renderUserSkills(knowledge) : userActiveTab === "build" ? renderUserBuild(knowledge) : userActiveTab === "cultivation" ? renderUserCultivation(knowledge) : renderUserOverview(knowledge);
}

function renderUserExperience(knowledge) {
  if (!knowledge) return;
  renderUserCharacterRail();
  renderUserHero(knowledge);
  renderUserTabPanel(knowledge);
}

function showUserExperience() {
  document.body.classList.add("user-mode");
  $("#userExperienceView").hidden = false;
  $("#roleManagementView").hidden = true;
  $("#encyclopediaView").hidden = true;
  $("#adminTopbarActions").hidden = true;
  $("#userTopbarActions").hidden = false;
  setText("#activeBreadcrumb", "用户端");
  $$('[data-nav]').forEach((item) => item.classList.remove('is-active'));
  $("#encyclopediaNavTrigger")?.classList.remove('is-active');
  $$('[data-encyclopedia-kind]').forEach((item) => item.classList.remove('is-active'));
}

function bindUserExperience() {
  $("#userCharacterSearch")?.addEventListener("input", (event) => {
    userCharacterSearchQuery = event.target.value.trim().toLowerCase();
    const entries = userCharacterEntries();
    if (entries.length && !entries.some(([name]) => name === selectedCharacter)) applyCharacter(entries[0][0], { skipUserRail: true, silent: true });
    renderUserCharacterRail();
  });
  $("#userCharacterRail")?.addEventListener("click", (event) => {
    if (userCarouselSuppressClick) {
      userCarouselSuppressClick = false;
      return;
    }
    const carouselAction = event.target.closest("[data-user-carousel]");
    if (carouselAction) {
      userCarouselMove(carouselAction.dataset.userCarousel === "next" ? 1 : -1);
      return;
    }
    const card = event.target.closest("[data-user-character]");
    if (!card) return;
    userCarouselSelectCard(card.dataset.userCharacter);
  });
  bindUserCarouselPointer();
  window.addEventListener("resize", () => userCarouselSetPosition(false), { passive: true });
  $("#userTabNav")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-user-tab]");
    if (!button) return;
    userActiveTab = button.dataset.userTab;
    renderUserTabPanel(activeKnowledge);
  });
  $("#userTabPanel")?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-user-action]");
    if (!action) return;
    userActiveTab = action.dataset.userAction;
    renderUserTabPanel(activeKnowledge);
    $("#userTabNav")?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("#userTabPanel")?.addEventListener("change", (event) => {
    if (event.target.matches("[data-user-skill-target]")) {
      const index = Number(event.target.dataset.userSkillTarget);
      const skill = activeKnowledge?.cultivation?.skills?.[index];
      const options = skill ? skillTargetOptions(skill) : [];
      const value = Number(event.target.value);
      if (activeKnowledge && skill && options.includes(value)) userSkillTargets[`${activeKnowledge.id}:${index}`] = value;
      renderUserTabPanel(activeKnowledge);
      return;
    }
    if (event.target.id !== "userTargetLevel") return;
    userTargetLevel = Number(event.target.value) || 80;
    renderUserTabPanel(activeKnowledge);
  });
  $("#userHeroCard")?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-user-action]");
    if (!action) return;
    userActiveTab = action.dataset.userAction;
    renderUserTabPanel(activeKnowledge);
    $("#userTabNav")?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("#userAdminButton")?.addEventListener("click", showRoleManagement);
  $("#userEncyclopediaButton")?.addEventListener("click", () => showEncyclopediaCategory("arc-drives"));
}
