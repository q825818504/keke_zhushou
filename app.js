const rawCharacterKnowledge = window.characterKnowledge || {};
const roleBasicStorageKey = "keke-role-basics-v1";
const localRoleBasicOverrides = (() => {
  try {
    const value = JSON.parse(localStorage.getItem(roleBasicStorageKey) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch { return {}; }
})();
const roleContentStorageKey = "keke-role-content-v1";
const localRoleContentOverrides = (() => {
  try {
    const value = JSON.parse(localStorage.getItem(roleContentStorageKey) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch { return {}; }
})();
const roleReactionStorageKey = "keke-role-reaction-enhancements-v1";
const localRoleReactionOverrides = (() => {
  try {
    const value = JSON.parse(localStorage.getItem(roleReactionStorageKey) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch { return {}; }
})();
const roleReactionDrafts = Object.create(null);
const cloneData = value => value == null ? value : JSON.parse(JSON.stringify(value));

function syncCharacterReactionEnhancements(characterId, entries, characterName = "") {
  const cycles = window.esperCycleKnowledge?.cycles || [];
  for (const cycle of cycles) {
    cycle.enhancements = (cycle.enhancements || []).filter(entry => entry.character_id !== characterId);
  }
  for (const entry of entries || []) {
    const cycle = cycles.find(item => item.id === entry.cycle_id);
    if (!cycle) continue;
    const record = cloneData(entry) || {};
    delete record.cycle_id;
    delete record.cycle_name;
    record.character_id = characterId;
    record.character_name = characterName || record.character_name || "";
    record.label = record.label || "被动技能";
    record.description = record.description || "";
    cycle.enhancements ||= [];
    cycle.enhancements.push(record);
  }
}

for (const [characterId, record] of Object.entries(window.characterOverrides?.characters || {})) {
  if (Object.prototype.hasOwnProperty.call(record, "reaction_enhancements") && Array.isArray(record.reaction_enhancements)) {
    const source = Object.values(window.characterKnowledge || {}).find(item => item.id === characterId);
    syncCharacterReactionEnhancements(characterId, record.reaction_enhancements, record.name || source?.name || "");
  }
}
for (const [characterId, entries] of Object.entries(localRoleReactionOverrides)) {
  if (!Array.isArray(entries)) continue;
  const source = Object.values(window.characterKnowledge || {}).find(item => item.id === characterId);
  syncCharacterReactionEnhancements(characterId, entries, localRoleBasicOverrides[characterId]?.name || window.characterOverrides?.characters?.[characterId]?.name || source?.name || "");
}

const allKnowledge = Object.fromEntries(Object.entries(rawCharacterKnowledge).map(([key, original]) => {
  const canonical = window.characterOverrides?.characters?.[original.id] || {};
  const local = localRoleBasicOverrides[original.id] || {};
  const localContent = localRoleContentOverrides[original.id] || {};
  return [key, {
    ...original,
    name: local.name || canonical.name || original.name,
    basic: { ...(original.basic || {}), ...(canonical.basic || {}), ...(local.basic || {}) },
    skills: cloneData(localContent.skills || canonical.skills || original.skills || []),
    awakenings: cloneData(localContent.awakenings || canonical.awakenings || original.awakenings || []),
    resonance: cloneData(localContent.resonance || canonical.resonance || original.resonance || []),
    terminal: canonical.terminal
      ? { ...(original.terminal || {}), ...canonical.terminal }
      : original.terminal,
    recommended: canonical.terminal && original.recommended?.cassette
      ? { ...original.recommended, cassette: { ...original.recommended.cassette, terminal: { ...(original.recommended.cassette.terminal || original.terminal || {}), ...canonical.terminal } } }
      : original.recommended,
    drive_layout_image: Object.prototype.hasOwnProperty.call(local, "drive_layout_image")
      ? local.drive_layout_image
      : canonical.drive_layout_image || original.drive_layout_image || ""
  }];
}));
const arcDriveCatalog = window.arcDriveKnowledge || { items: [], source: {} };
const skyCurtainCatalog = window.skyCurtainKnowledge || { items: [], source: {} };
const driverBlockCatalog = window.driverBlockKnowledge || { items: [], source: {}, mechanism_guide: {} };
const teamTemplateKnowledge = window.teamTemplateKnowledge || { teams: [], source_catalog: {} };
const importedKnowledge = allKnowledge.zhenhong || null;
let activeKnowledge = importedKnowledge;
const importedAssetUrl = (asset) => {
  const localPath = typeof asset?.local_path === "string" ? asset.local_path.trim().replace(/\\/g, "/") : "";
  if (!localPath) return "";
  let resolved;
  try { resolved = new URL(localPath, "https://keke-local.invalid/"); }
  catch { return ""; }
  if (resolved.origin !== "https://keke-local.invalid" || !resolved.pathname.startsWith("/data/") || resolved.search || resolved.hash) return "";
  return localPath;
};
function findCharacterIcon(knowledge) {
  const assets = knowledge.assets || [];
  const ownIconName = `${knowledge.id}-icon.`.toLowerCase();
  return assets.find((asset) => asset.type === "character_icon" && String(asset.local_path || "").split(/[\\/]/).pop().toLowerCase().startsWith(ownIconName))
    || assets.find((asset) => asset.type === "character_icon");
}

const characterData = Object.fromEntries(Object.values(allKnowledge).filter((knowledge) => knowledge?.name).map((knowledge) => {
  const basic = knowledge.basic || {};
  const facts = knowledge.mechanism_facts || {};
  const portrait = knowledge.assets?.find((asset) => asset.type === "character_portrait");
  const icon = findCharacterIcon(knowledge);
  const skills = knowledge.skills || [];
  const parameterCount = skills.reduce((sum, skill) => sum + (skill.parameters || []).length, 0);
  const awakenings = knowledge.awakenings || [];
  const resonance = knowledge.resonance || [];
  const materialCount = Object.keys(knowledge.cultivation?.material_catalog || {}).length;
  const summary = basic.summary || "暂无角色简介。";
  const roleLabel = basic.role || "定位待补充";
  const positionLabel = basic.position || "站位待补充";
  const statsCount = knowledge.base_stats?.stats?.length || 0;
  const cultivationAvailable = Boolean((knowledge.cultivation?.ascension || []).length || (knowledge.cultivation?.skills || []).length);
  const slots = [
    ["基础资料", "角色属性与定位", basic.rarity && basic.element ? "已导入" : "待补充", basic.rarity && basic.element ? "green" : "amber"],
    ["基础属性", "角色等级成长数据", statsCount ? `${statsCount} 项` : "待补充", statsCount ? "green" : "amber"],
    ["技能资料", "技能描述与参数", skills.length ? `${skills.length} 项` : "待补充", skills.length ? "green" : "amber"],
    ["觉醒与共鸣", "角色节点效果", awakenings.length + resonance.length ? `${awakenings.length + resonance.length} 项` : "待补充", awakenings.length + resonance.length ? "green" : "amber"],
    ["养成材料", "突破与技能升级消耗", cultivationAvailable ? `${materialCount} 种材料` : "待补充", cultivationAvailable ? "green" : "amber"]
  ];
  return [knowledge.name, {
    id: knowledge.id,
    knowledgeId: knowledge.id,
    rarity: basic.rarity || "—",
    element: basic.element || "—",
    cassetteType: basic.cassette_type || "—",
    rating: basic.rating || "—",
    role: basic.role || "",
    sourcePosition: basic.position || "",
    position: `${roleLabel} · ${positionLabel}`,
    station: basic.position || "待补充",
    summaryTitle: `${knowledge.name} · ${roleLabel}`,
    summary,
    reaction: facts.primary_reaction || "待补充",
    portrait: portrait ? importedAssetUrl(portrait) : "",
    icon: icon ? importedAssetUrl(icon) : "",
    metrics: [String(skills.length), String(parameterCount), String(awakenings.length)],
    slots,
    knowledge: window.CharacterRecommendations.createKnowledge(knowledge)
  }];
}));
const userTeamSavedState = (() => {
  try {
    const value = JSON.parse(localStorage.getItem("keke-user-team-v1") || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
})();
const userTeamNameById = Object.fromEntries(Object.entries(characterData).map(([name, data]) => [data.id, name]));
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const toast = $("#toast");
const toastText = $("#toastText");
let toastTimer;
let selectedCharacter = "真红";
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
let userActiveRoute = "characters";

let userTeamTeamCount = userTeamSavedState.teamCount === 2 ? 2 : 1;
let userArcDriveSearchQuery = "";
let userSkyCurtainSearchQuery = "";
let userDriverBlockSearchQuery = "";
let userDriverBlockModelFilter = "all";
let userSelectedArcDriveId = arcDriveCatalog.items?.[0]?.id || "";
let userSelectedSkyCurtainId = skyCurtainCatalog.items?.[0]?.id || "";
let userSelectedDriverBlockId = driverBlockCatalog.items?.[0]?.id || "";
let userSelectedDriverBlockQuality = "gold";
let userSelectedDriverBlockLevel = 20;
let userArcDriveLevel = 80;
let userArcDriveRank = 1;
let userSkyCurtainQuality = "gold";
let userTeamOwnedNames = new Set((Array.isArray(userTeamSavedState.ownedCharacterIds) ? userTeamSavedState.ownedCharacterIds : []).map((id) => userTeamNameById[id]).filter(Boolean));
let userTeamInvestmentByCharacterId = userTeamSavedState.investmentsByCharacterId && typeof userTeamSavedState.investmentsByCharacterId === "object" ? userTeamSavedState.investmentsByCharacterId : {};
let userTeamPinnedCoreNames = [...new Set((Array.isArray(userTeamSavedState.pinnedMainCIds) ? userTeamSavedState.pinnedMainCIds : []).map((id) => userTeamNameById[id]).filter(Boolean))].slice(0, 2);
let userTeamExpandedInvestmentNames = new Set(userTeamPinnedCoreNames);
let userTeamSelectedCandidateIndexes = [0, 0];
let userTeamGenerated = false;
const userRouteLabels = { characters: "角色", team: "自动配队", "arc-drives": "弧盘", cassettes: "空幕", "drive-blocks": "驱动块", "role-build": "角色配装", "role-build-plus": "角色配装 PLUS", inventory: "背包数据", vision: "读取数据" };
const userTeamElementRing = ["光", "灵", "咒", "暗", "魂", "相"];
const userTeamReactionRules = (window.esperCycleKnowledge?.cycles || []).map(cycle => ({ name: cycle.name, attrs: cycle.attributes.map(attribute => attribute.name) }));

function feedbackTone(message) {
  const value = String(message || "");
  if (/失败|错误|无法|未能|异常/.test(value)) return "error";
  if (/待保存|尚未写入|仅保存在|仅在当前|来源待核验|草稿未保存|待补充|未配置/.test(value)) return "warning";
  if (/已保存|已写入|已审核|已汇总|重置成功|处理完成|成功/.test(value)) return "success";
  if (/正在|连接中|处理中|检查中/.test(value)) return "working";
  return "info";
}

function notify(message) {
  toastText.textContent = message;
  toast.dataset.tone = feedbackTone(message);
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

function setText(selector, text) {
  const element = $(selector);
  if (element) {
    element.textContent = text;
    if (["#recommendationStatus", "#draftLabel", ".updated-time", "#analysisState"].includes(selector)) {
      element.dataset.tone = feedbackTone(text);
    }
  }
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
  ["#roleName", "#roleRarity", "#roleElement", "#roleCassetteType", "#rolePosition", "#roleStation", "#roleRating"].forEach((selector) => {
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
    weapon.innerHTML = data ? `<div class="recommendation-card">${data.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: data.asset }))}" alt="${escapeHtml(data.name)}">` : '<span class="asset-placeholder">武</span>'}<div><span>推荐武器 · ${escapeHtml(data.rating || "评级待补充")}</span><b>${escapeHtml(data.name)}</b></div></div>` : emptyState("暂无推荐武器记录");
  }
  const cassette = $("#recommendedCassette");
  if (cassette) {
    const data = recommended.cassette;
    cassette.innerHTML = data ? `<div class="recommendation-card">${data.icon ? `<img src="${escapeHtml(importedAssetUrl({ local_path: data.icon }))}" alt="${escapeHtml(data.name)}">` : '<span class="asset-placeholder">带</span>'}<div><span>推荐卡带 · ${escapeHtml(data.category || "类型待补充")} · ${escapeHtml(data.element || "属性待补充")}</span><b>${escapeHtml(data.name)}</b><small>${escapeHtml(data.cassette_type || "卡带类型待补充")}${data.set_effects?.length ? ` · ${data.set_effects.length} 条套装效果` : ""}</small></div></div>` : emptyState("暂无推荐卡带记录");
  }
  renderRecommendationControls(knowledge);
}

function renderRecommendationControls(knowledge) {
  const root = $("#recommendationControls");
  const select = (kind, title, catalog) => {
    const selected = knowledge.recommended?.[kind];
    const defaults = allKnowledge[knowledge.id]?.recommended?.[kind];
    const items = [...(catalog.items || [])];
    if (selected && !items.some(item => item.id === selected.id)) items.unshift(selected);
    return `<label class="field"><span>${title}</span><select data-recommendation-kind="${kind}" aria-label="${title}">${selected ? "" : '<option value="" selected disabled>请选择</option>'}${items.map(item => `<option value="${escapeHtml(item.id)}"${selected?.id === item.id ? " selected" : ""}>${escapeHtml(item.name)}${item.id === defaults?.id ? "（默认）" : ""}</option>`).join("")}</select></label>`;
  };
  root.innerHTML = select("weapon", "修改推荐弧盘", arcDriveCatalog) + select("cassette", "修改推荐卡带", skyCurtainCatalog) + '<div class="recommendation-actions"><button type="button" class="outline-button pressable" data-save-recommendation>保存推荐</button><button type="button" class="text-button pressable" data-reset-recommendation>恢复默认</button><span id="recommendationStatus" role="status" aria-live="polite" data-tone="info">当前配置</span></div>';
  if (root.dataset.bound) return;
  root.dataset.bound = "true";
  root.addEventListener("change", event => {
    const field = event.target.closest("[data-recommendation-kind]");
    if (!field) return;
    window.CharacterRecommendations.select(activeKnowledge, field.dataset.recommendationKind, field.value);
    refreshRecommendationPreview(activeKnowledge);
    setText("#recommendationStatus", "已修改，待保存");
  });
  root.addEventListener("click", async event => {
    if (event.target.closest("[data-save-recommendation]")) {
      $("#saveDraftButton").click();
      return;
    }
    if (event.target.closest("[data-reset-recommendation]")) {
      if (!window.CharacterRecommendations.reset(activeKnowledge)) { notify("恢复失败，请检查浏览器存储权限"); return; }
      refreshRecommendationPreview(activeKnowledge);
      try {
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistCharacterRecommendations();
        setText("#recommendationStatus", connected ? "默认推荐已写入项目" : "默认推荐仅在当前浏览器恢复");
        notify(connected ? "已恢复默认推荐并写入项目" : "已在当前浏览器恢复默认；尚未写入项目");
      } catch (error) {
        setText("#recommendationStatus", "浏览器已恢复，项目写入失败");
        notify(`浏览器状态已更新，但写入项目失败：${error.message}`);
      }
    }
  });
}

function refreshRecommendationPreview(knowledge) {
  renderRecommended(knowledge);
  renderCassetteRecommendationEditor(knowledge);
  renderCassette(knowledge);
  window.TerminalPuzzleEditor?.render(knowledge);
  setText("#cassetteSummaryLabel", knowledge.recommended?.cassette?.name || "暂无推荐卡带");
  renderUserTabPanel(knowledge);
}

function renderRoleReactionEnhancements(knowledge) {
  const cycles = window.esperCycleKnowledge?.cycles || [];
  if (!Object.prototype.hasOwnProperty.call(roleReactionDrafts, knowledge.id)) {
    const canonical = window.characterOverrides?.characters?.[knowledge.id] || {};
    if (Array.isArray(localRoleReactionOverrides[knowledge.id])) roleReactionDrafts[knowledge.id] = cloneData(localRoleReactionOverrides[knowledge.id]);
    else if (Object.prototype.hasOwnProperty.call(canonical, "reaction_enhancements") && Array.isArray(canonical.reaction_enhancements)) roleReactionDrafts[knowledge.id] = cloneData(canonical.reaction_enhancements);
    else roleReactionDrafts[knowledge.id] = cycles.flatMap(cycle =>
      (cycle.enhancements || []).filter(entry => entry.character_id === knowledge.id)
        .map(entry => ({ ...cloneData(entry), cycle_id: cycle.id, cycle_name: cycle.name })));
  }
  const matches = roleReactionDrafts[knowledge.id] || [];
  const preview = $("#roleReactionEnhancements");
  if (preview) preview.innerHTML = matches.length ? matches.map(entry => {
    const cycle = cycles.find(item => item.id === entry.cycle_id);
    return `<article class="role-reaction-enhancement"><b>${escapeHtml(cycle?.name || entry.cycle_name || "未选择反应")} · ${escapeHtml(entry.label || "被动技能")}</b><p>${escapeHtml(entry.description || "")}</p></article>`;
  }).join("") : '<p class="empty-state">暂无反应强化。可在下方添加。</p>';

  const editor = $("#reactionEnhancementEditor");
  if (!editor) return;
  editor.innerHTML = matches.length ? matches.map((entry, index) => `
    <article class="role-edit-entry role-reaction-edit-entry">
      <div class="role-edit-entry-heading"><b>反应强化 ${index + 1}</b><button class="text-button role-editor-remove" type="button" data-remove-reaction="${index}">删除</button></div>
      <div class="role-edit-fields role-reaction-fields">
        <label class="field"><span>反应类型</span><select data-reaction-index="${index}" data-reaction-field="cycle_id"><option value="">选择反应</option>${cycles.filter(cycle => cycle.id === entry.cycle_id || !matches.some((other, otherIndex) => otherIndex !== index && other.cycle_id === cycle.id)).map(cycle => `<option value="${escapeHtml(cycle.id)}"${cycle.id === entry.cycle_id ? " selected" : ""}>${escapeHtml(cycle.name)}</option>`).join("")}</select></label>
        <label class="field"><span>强化标签</span><input type="text" maxlength="100" value="${escapeHtml(entry.label || "")}" data-reaction-index="${index}" data-reaction-field="label" placeholder="如：被动技能"></label>
        <label class="field role-edit-wide"><span>强化描述</span><textarea rows="3" maxlength="5000" data-reaction-index="${index}" data-reaction-field="description" placeholder="输入该角色强化反应后的具体效果">${escapeHtml(entry.description || "")}</textarea></label>
      </div>
    </article>`).join("") : '<p class="empty-state">暂无条目。添加后选择反应类型并填写效果。</p>';
}

function renderRoleContentEditors(knowledge) {
  const skillsEditor = $("#skillsEditor");
  if (skillsEditor) {
    const skills = knowledge.skills || [];
    const hadSkillEditors = skillsEditor.querySelector("[data-skill-editor-index]") != null;
    const expandedSkills = new Set([...skillsEditor.querySelectorAll("[data-skill-editor-index][open]")].map(entry => Number(entry.dataset.skillEditorIndex)));
    skillsEditor.innerHTML = skills.length ? skills.map((skill, index) => `
      <details class="role-edit-entry role-skill-edit-entry" data-skill-editor-index="${index}" ${expandedSkills.has(index) || (!hadSkillEditors && index === 0) ? "open" : ""}>
        <summary><b>${escapeHtml(skill.name || `技能 ${index + 1}`)}</b><small>${escapeHtml(skill.category || "未分类")} · ${skill.parameters?.length || 0} 个倍率参数</small></summary>
        <div class="role-edit-entry-body">
          <div class="role-edit-fields">
            <label class="field"><span>技能名称</span><input type="text" maxlength="200" value="${escapeHtml(skill.name || "")}" data-skill-index="${index}" data-skill-field="name"></label>
            <label class="field"><span>技能 ID</span><input type="text" maxlength="200" value="${escapeHtml(skill.id || "")}" data-skill-index="${index}" data-skill-field="id"></label>
            <label class="field"><span>技能分类</span><input type="text" maxlength="100" value="${escapeHtml(skill.category || "")}" data-skill-index="${index}" data-skill-field="category" placeholder="如：Melee、Skill、Ultimate"></label>
            <label class="field"><span>等级上限</span><input type="number" min="0" max="99" value="${escapeHtml(skill.level_cap ?? 1)}" data-skill-index="${index}" data-skill-field="level_cap"></label>
            <label class="field role-edit-wide"><span>技能原始描述</span><textarea rows="4" maxlength="20000" data-skill-index="${index}" data-skill-field="raw_text" placeholder="没有分段说明时，用户端会显示这段内容">${escapeHtml(skill.raw_text || "")}</textarea></label>
          </div>
          <div class="role-edit-subsection"><div class="role-edit-subsection-heading"><b>分段说明</b><button class="text-button" type="button" data-role-editor-add-part="${index}">添加说明</button></div>
            ${(skill.description_parts || []).map((part, partIndex) => `<div class="role-edit-subentry"><label class="field"><span>小标题</span><input type="text" maxlength="200" value="${escapeHtml(part.name || "")}" data-skill-index="${index}" data-skill-part-index="${partIndex}" data-skill-part-field="name"></label><label class="field"><span>说明内容</span><textarea rows="3" maxlength="5000" data-skill-index="${index}" data-skill-part-index="${partIndex}" data-skill-part-field="text">${escapeHtml(part.text || "")}</textarea></label><button class="text-button role-editor-remove" type="button" data-remove-skill-part="${index}:${partIndex}">删除说明</button></div>`).join("") || '<p class="role-data-editor-help">暂无分段说明；原始描述仍会展示。</p>'}
          </div>
          <div class="role-edit-subsection"><div class="role-edit-subsection-heading"><b>倍率与参数</b><button class="text-button" type="button" data-role-editor-add-parameter="${index}">添加参数</button></div>
            ${(skill.parameters || []).map((parameter, parameterIndex) => `<div class="role-edit-subentry role-parameter-edit-entry"><label class="field"><span>参数名称</span><input type="text" maxlength="200" value="${escapeHtml(parameter.label || "")}" data-skill-index="${index}" data-skill-parameter-index="${parameterIndex}" data-skill-parameter-field="label"></label><label class="field"><span>各等级数值（每行一条）</span><textarea rows="3" maxlength="30000" data-skill-index="${index}" data-skill-parameter-index="${parameterIndex}" data-skill-parameter-field="values">${escapeHtml((parameter.values || []).join("\n"))}</textarea></label><button class="text-button role-editor-remove" type="button" data-remove-skill-parameter="${index}:${parameterIndex}">删除参数</button></div>`).join("") || '<p class="role-data-editor-help">暂无倍率参数。</p>'}
          </div>
          <button class="text-button role-editor-remove role-editor-remove-entry" type="button" data-remove-skill="${index}">删除技能</button>
        </div>
      </details>`).join("") : '<p class="empty-state">暂无技能资料。可添加技能条目。</p>';
  }

  const awakeningsEditor = $("#awakeningsEditor");
  if (awakeningsEditor) {
    const awakenings = knowledge.awakenings || [];
    awakeningsEditor.innerHTML = awakenings.length ? awakenings.map((awakening, index) => `
      <article class="role-edit-entry">
        <div class="role-edit-entry-heading"><b>觉醒节点 ${index + 1}</b><button class="text-button role-editor-remove" type="button" data-remove-awakening="${index}">删除</button></div>
        <div class="role-edit-fields">
          <label class="field"><span>节点名称</span><input type="text" maxlength="200" value="${escapeHtml(awakening.name || "")}" data-awakening-index="${index}" data-awakening-field="name"></label>
          <label class="field"><span>图片路径</span><input type="text" maxlength="500" value="${escapeHtml(awakening.asset || "")}" data-awakening-index="${index}" data-awakening-field="asset" placeholder="data/resources/characters/..."></label>
          <label class="field role-edit-wide"><span>效果描述</span><textarea rows="3" maxlength="5000" data-awakening-index="${index}" data-awakening-field="description">${escapeHtml(awakening.description || "")}</textarea></label>
        </div>
      </article>`).join("") : '<p class="empty-state">暂无觉醒节点。可添加节点。</p>';
  }

  const resonanceEditor = $("#resonanceEditor");
  if (resonanceEditor) {
    const resonance = knowledge.resonance || [];
    resonanceEditor.innerHTML = resonance.length ? resonance.map((entry, index) => `
      <article class="role-edit-entry">
        <div class="role-edit-entry-heading"><b>共鸣节点 ${index + 1}</b><button class="text-button role-editor-remove" type="button" data-remove-resonance="${index}">删除</button></div>
        <div class="role-edit-fields">
          <label class="field"><span>共鸣等级</span><input type="number" min="1" max="6" value="${escapeHtml(entry.level ?? "")}" data-resonance-index="${index}" data-resonance-field="level" placeholder="可留空"></label>
          <label class="field"><span>节点名称</span><input type="text" maxlength="200" value="${escapeHtml(entry.name || "")}" data-resonance-index="${index}" data-resonance-field="name"></label>
          <label class="field"><span>图片路径</span><input type="text" maxlength="500" value="${escapeHtml(entry.asset || "")}" data-resonance-index="${index}" data-resonance-field="asset" placeholder="data/resources/characters/..."></label>
          <label class="field role-edit-wide"><span>效果描述</span><textarea rows="3" maxlength="5000" data-resonance-index="${index}" data-resonance-field="description">${escapeHtml(entry.description || "")}</textarea></label>
        </div>
      </article>`).join("") : '<p class="empty-state">暂无共鸣节点。可添加节点。</p>';
  }
}

function getRoleReactionDraft(knowledge) {
  return roleReactionDrafts[knowledge.id] || [];
}

function markRoleDraft() {
  setText("#draftLabel", "草稿未保存");
}

function refreshRoleContentPreview(knowledge) {
  renderSkills(knowledge);
  renderAwakenings(knowledge);
  renderResonance(knowledge);
  setText("#metricSlots", String(knowledge.skills?.length || 0));
  setText("#metricTeams", String((knowledge.skills || []).reduce((sum, skill) => sum + (skill.parameters || []).length, 0)));
  setText("#metricGold", String(knowledge.awakenings?.length || 0));
  setText("#awakeningCountLabel", `${knowledge.awakenings?.length || 0} 个觉醒节点`);
  renderUserTabPanel(knowledge);
}

function updateReactionPreview(knowledge) {
  const preview = $("#roleReactionEnhancements");
  const cycles = window.esperCycleKnowledge?.cycles || [];
  const entries = getRoleReactionDraft(knowledge);
  if (preview) preview.innerHTML = entries.length ? entries.map(entry => {
    const cycle = cycles.find(item => item.id === entry.cycle_id);
    return `<article class="role-reaction-enhancement"><b>${escapeHtml(cycle?.name || entry.cycle_name || "未选择反应")} · ${escapeHtml(entry.label || "被动技能")}</b><p>${escapeHtml(entry.description || "")}</p></article>`;
  }).join("") : '<p class="empty-state">暂无反应强化。可在下方添加。</p>';
}

function bindRoleContentEditors() {
  const editor = $("#editorCard");
  if (!editor) return;
  editor.addEventListener("input", event => {
    const field = event.target;
    const knowledge = activeKnowledge;
    if (!knowledge) return;
    if (field.matches("[data-skill-index][data-skill-field]")) {
      const skill = knowledge.skills?.[Number(field.dataset.skillIndex)];
      if (!skill) return;
      const key = field.dataset.skillField;
      skill[key] = key === "level_cap" ? Math.min(99, Math.max(0, Number(field.value) || 0)) : field.value;
      refreshRoleContentPreview(knowledge);
    } else if (field.matches("[data-skill-part-index][data-skill-part-field]")) {
      const skill = knowledge.skills?.[Number(field.dataset.skillIndex)];
      const part = skill?.description_parts?.[Number(field.dataset.skillPartIndex)];
      if (!part) return;
      part[field.dataset.skillPartField] = field.value;
      refreshRoleContentPreview(knowledge);
    } else if (field.matches("[data-skill-parameter-index][data-skill-parameter-field]")) {
      const skill = knowledge.skills?.[Number(field.dataset.skillIndex)];
      const parameter = skill?.parameters?.[Number(field.dataset.skillParameterIndex)];
      if (!parameter) return;
      if (field.dataset.skillParameterField === "values") {
        parameter.values = field.value.split(/\r?\n|→/).map(value => value.trim()).filter(Boolean);
        parameter.current_value = parameter.values[0] || "";
      } else parameter[field.dataset.skillParameterField] = field.value;
      refreshRoleContentPreview(knowledge);
    } else if (field.matches("[data-awakening-index][data-awakening-field]")) {
      const awakening = knowledge.awakenings?.[Number(field.dataset.awakeningIndex)];
      if (!awakening) return;
      awakening[field.dataset.awakeningField] = field.value;
      renderAwakenings(knowledge);
      renderUserTabPanel(knowledge);
    } else if (field.matches("[data-resonance-index][data-resonance-field]")) {
      const entry = knowledge.resonance?.[Number(field.dataset.resonanceIndex)];
      if (!entry) return;
      const key = field.dataset.resonanceField;
      if (key === "level") {
        if (field.value === "") delete entry.level;
        else entry.level = Math.min(6, Math.max(1, Number(field.value) || 1));
      } else entry[key] = field.value;
      renderResonance(knowledge);
      renderUserTabPanel(knowledge);
    } else if (field.matches("[data-reaction-index][data-reaction-field]")) {
      const entry = getRoleReactionDraft(knowledge)[Number(field.dataset.reactionIndex)];
      if (!entry) return;
      const key = field.dataset.reactionField;
      entry[key] = field.value;
      if (key === "cycle_id") entry.cycle_name = window.esperCycleKnowledge?.cycles?.find(cycle => cycle.id === field.value)?.name || "";
      updateReactionPreview(knowledge);
    } else return;
    markRoleDraft();
  });

  editor.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    const knowledge = activeKnowledge;
    if (!knowledge) return;
    let changed = false;
    const add = button.dataset.roleEditorAdd;
    if (add === "skill") {
      knowledge.skills ||= [];
      const index = knowledge.skills.length + 1;
      knowledge.skills.push({ id: `skill-${knowledge.id}-${index}`, name: `新技能 ${index}`, category: "Skill", description_parts: [], raw_text: "", level_cap: 1, parameters: [] });
      renderRoleContentEditors(knowledge);
      const newSkillEditor = $("#skillsEditor")?.lastElementChild;
      if (newSkillEditor?.matches("[data-skill-editor-index]")) newSkillEditor.open = true;
      changed = true;
    } else if (add === "awakening") {
      knowledge.awakenings ||= [];
      knowledge.awakenings.push({ name: `觉醒 ${knowledge.awakenings.length + 1}`, description: "", asset: "" });
      renderRoleContentEditors(knowledge);
      changed = true;
    } else if (add === "resonance") {
      knowledge.resonance ||= [];
      const usedLevels = new Set(knowledge.resonance.map(entry => Number(entry.level)).filter(Number.isInteger));
      const nextLevel = Array.from({ length: 6 }, (_, index) => index + 1).find(level => !usedLevels.has(level));
      knowledge.resonance.push({ ...(nextLevel ? { level: nextLevel } : {}), name: `共鸣节点 ${knowledge.resonance.length + 1}`, description: "", asset: "" });
      renderRoleContentEditors(knowledge);
      changed = true;
    } else if (add === "reaction") {
      const cycles = window.esperCycleKnowledge?.cycles || [];
      const firstCycle = cycles.find(cycle => !getRoleReactionDraft(knowledge).some(entry => entry.cycle_id === cycle.id));
      if (!firstCycle) { notify("这个角色已添加全部反应类型"); return; }
      roleReactionDrafts[knowledge.id] ||= [];
      roleReactionDrafts[knowledge.id].push({ cycle_id: firstCycle?.id || "", cycle_name: firstCycle?.name || "", character_id: knowledge.id, character_name: knowledge.name, label: "被动技能", description: "" });
      renderRoleReactionEnhancements(knowledge);
      changed = true;
    } else if (button.dataset.roleEditorAddPart != null) {
      const skill = knowledge.skills?.[Number(button.dataset.roleEditorAddPart)];
      if (skill) { skill.description_parts ||= []; skill.description_parts.push({ name: "", text: "" }); renderRoleContentEditors(knowledge); changed = true; }
    } else if (button.dataset.roleEditorAddParameter != null) {
      const skill = knowledge.skills?.[Number(button.dataset.roleEditorAddParameter)];
      if (skill) { skill.parameters ||= []; skill.parameters.push({ label: "", source_key: skill.id || skill.name || "", values: [], current_value: "" }); renderRoleContentEditors(knowledge); changed = true; }
    } else if (button.dataset.removeSkill != null) {
      knowledge.skills?.splice(Number(button.dataset.removeSkill), 1); renderRoleContentEditors(knowledge); changed = true;
    } else if (button.dataset.removeAwakening != null) {
      knowledge.awakenings?.splice(Number(button.dataset.removeAwakening), 1); renderRoleContentEditors(knowledge); changed = true;
    } else if (button.dataset.removeResonance != null) {
      knowledge.resonance?.splice(Number(button.dataset.removeResonance), 1); renderRoleContentEditors(knowledge); changed = true;
    } else if (button.dataset.removeReaction != null) {
      getRoleReactionDraft(knowledge).splice(Number(button.dataset.removeReaction), 1); renderRoleReactionEnhancements(knowledge); changed = true;
    } else if (button.dataset.removeSkillPart) {
      const [skillIndex, partIndex] = button.dataset.removeSkillPart.split(":").map(Number);
      knowledge.skills?.[skillIndex]?.description_parts?.splice(partIndex, 1); renderRoleContentEditors(knowledge); changed = true;
    } else if (button.dataset.removeSkillParameter) {
      const [skillIndex, parameterIndex] = button.dataset.removeSkillParameter.split(":").map(Number);
      knowledge.skills?.[skillIndex]?.parameters?.splice(parameterIndex, 1); renderRoleContentEditors(knowledge); changed = true;
    }
    if (changed) {
      refreshRoleContentPreview(knowledge);
      updateReactionPreview(knowledge);
      markRoleDraft();
    }
  });
}

function renderBaseStats(knowledge) {
  const target = $("#baseStats");
  if (!target) return;
  const stats = knowledge.base_stats?.stats || [];
  if (!stats.length) { target.innerHTML = emptyState("暂无基础属性成长数据"); return; }
  const maxLevel = Math.max(...stats.map((stat) => (stat.values || []).length));
  const levels = [1, 30, 50, 70, 80].filter((level) => level <= maxLevel);
  target.innerHTML = `<div class="stats-table"><div class="stats-row stats-head"><span>属性</span>${levels.map((level) => `<span>Lv.${level}</span>`).join("")}</div>${stats.map((stat) => `<div class="stats-row"><b>${escapeHtml(stat.name)}</b>${levels.map((level) => `<span>${stat.values?.[level - 1] == null ? "—" : Number(stat.values[level - 1]).toLocaleString()}</span>`).join("")}</div>`).join("")}</div>`;
}

function renderSkills(knowledge) {
  const target = $("#skillsList");
  if (!target) return;
  const skills = knowledge.skills || [];
  if (!skills.length) { target.innerHTML = emptyState("暂无技能数据"); return; }
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
    <article class="awakening-card">${awakening.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: awakening.asset }))}" alt="觉醒 ${index + 1}">` : '<span class="asset-placeholder awakening-placeholder">?</span>'}<div><b>${index + 1}. ${escapeHtml(awakening.name || "未命名节点")}</b><p>${escapeHtml(awakening.description)}</p></div></article>`).join("") : emptyState("暂无觉醒节点");
}

function renderResonance(knowledge) {
  const target = $("#resonanceList");
  if (!target) return;
  const entries = knowledge.resonance || [];
  setText("#resonanceCountLabel", `${entries.length} 个共鸣节点`);
  target.innerHTML = entries.length ? entries.map((entry) => `
    <article class="awakening-card">${entry.asset ? `<img src="${escapeHtml(importedAssetUrl({ local_path: entry.asset }))}" alt="${escapeHtml(entry.name || "共鸣")}">` : '<span class="asset-placeholder awakening-placeholder">共</span>'}<div><b>${entry.level ? `Lv.${entry.level} · ` : ""}${escapeHtml(entry.name || "共鸣")}</b><p>${escapeHtml(entry.description)}</p></div></article>`).join("") : emptyState("暂无共鸣节点");
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
  if (!skills.length) { target.innerHTML = emptyState("暂无技能养成数据"); return; }
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
    if (target) target.innerHTML = emptyState("暂无养成材料数据");
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

const CASSETTE_RECOMMENDATION_AFFIX_OPTIONS = {
  main: [
    "生命值百分比", "攻击力百分比", "防御力百分比", "暴击率", "暴击伤害",
    "环合强度", "倾陷强度", "治疗加成", "光属性异能伤害增强", "灵属性异能伤害增强",
    "咒属性异能伤害增强", "暗属性异能伤害增强", "魂属性异能伤害增强", "相属性异能伤害增强",
    "心灵伤害增强"
  ],
  sub: [
    "生命值百分比", "攻击力百分比", "防御力百分比", "生命值", "攻击力", "防御力",
    "暴击率", "暴击伤害", "环合强度", "倾陷强度", "通用伤害增强"
  ]
};

function rankAffixes(items) {
  const groups = [];
  [...items].sort((a, b) => normalizeAffixPriority(b.priority) - normalizeAffixPriority(a.priority)).forEach((item) => {
    const priority = normalizeAffixPriority(item.priority);
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

function normalizeAffixPriority(value) {
  return Math.min(5, Math.max(1, Math.round(Number(value) || 1)));
}

function readRecommendedAffixes(root, kind, knowledge) {
  const existing = new Map(recommendedAffixes(knowledge?.recommended?.cassette, kind).map(item => [item.name, item]));
  return [...root.querySelectorAll('[data-affix-option="' + kind + '"].is-selected')].map((button) => {
    const row = button.closest(".affix-editor-row");
    const input = row ? row.querySelector("[data-affix-priority]") : null;
    const name = button.dataset.affixName;
    const priority = normalizeAffixPriority(input?.value);
    return { ...existing.get(name), name, priority };
  });
}

function syncCassetteRecommendations(knowledge, root, rerenderEditor = false) {
  const cassette = knowledge.recommended?.cassette;
  if (!cassette || !root) return;
  cassette.recommended_main_affixes = readRecommendedAffixes(root, "main", knowledge);
  cassette.recommended_sub_affixes = readRecommendedAffixes(root, "sub", knowledge);
  renderCassette(knowledge);
  setText("#recommendationStatus", "已修改，待保存");
  setText("#draftLabel", "草稿未保存");
  window.dispatchEvent(new Event("keke-role-dirty"));
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

function renderTerminalCard(terminal, knowledge) {
  if (!terminal) return "";
  const diagram = knowledge && window.TerminalPuzzle ? window.TerminalPuzzle.render(knowledge) : renderTerminalDiagram(terminal.layout);
  return `<section class="terminal-card">${diagram}<div class="terminal-copy"><span class="terminal-kicker">终端 · 驱动加成</span><b>${escapeHtml(terminal.name || "卡带属性")}</b><p>${escapeHtml(terminal.description || "")}</p><span class="terminal-effect">${(terminal.effects || []).map(escapeHtml).join(" · ")}</span></div></section>`;
}

function renderCassetteRecommendationEditor(knowledge) {
  const target = $("#cassetteRecommendationEditor");
  const cassette = knowledge.recommended?.cassette;
  if (!target) return;
  const scoring = window.KekeCassetteScoring;
  const weights = scoring ? Object.entries(scoring.PRIORITY_WEIGHTS).filter(([priority]) => Number(priority) > 0) : [];
  const weightTable = weights.map(([priority, weight]) => `<tr><th>P${priority}</th><td>${Math.round(weight * 100)}%</td></tr>`).join("");
  const policy = `<aside class="cassette-scoring-policy" aria-label="空幕推荐评分规则"><div class="cassette-scoring-policy-head"><div><span>统一评分规则 · 用户端与管理端共用</span><b>空幕属性适配分：主属性 60% + 副属性 40%</b></div><span class="cassette-policy-badge">V1.5 本地测试</span></div><table class="cassette-weight-table"><thead><tr><th>优先级</th><th>属性权重</th></tr></thead><tbody>${weightTable}</tbody></table><ul><li><b>主属性：</b>60 × 主属性权重 × 品质系数；未选中的属性权重为 0。</li><li><b>副属性：</b>40 × 当前四条副属性权重之和 ÷ 此空幕合法副词条池中权重最高的四种不重复属性之和 × 品质系数。品质后上限仍为 40。</li><li><b>单块驱动：</b>100 × 四条不重复副属性权重和 ÷ 同形驱动合法副词条池中权重最高的四种属性权重和 × 品质系数；固定主属性不参与，沿用本角色卡带副属性推荐。</li><li><b>品质系数：</b>金色 ×1.00、紫色 ×0.80、蓝色 ×0.60。来自同词条装备实际数值比例；空幕主属性、副属性与同形驱动副属性都按此折算。金色沿用原有评分基准。</li><li><b>整体总评：</b>驱动盘面分 = Σ（单块分 × 占格数）÷ 可用格数，空槽为 0；总分 = 空幕分 + 驱动盘面分，上限 200；配装毕业率 = 总分 ÷ 200。空幕毕业率单独表示空幕分 ÷ 100。</li><li><b>毕业配装：</b>按同形状实例分组取高分装备，枚举形状数量并按盘面加权总分优先验证合法摆放；独立线程搜索，达到预算时只报告当前最佳，不宣称已证实最高分。默认同时排除其他角色占用的空幕和驱动，本角色装备保留。</li><li><b>保存与装配：</b>每账号、每原生角色实例保留一套方案；保存稳定装备引用和属性签名，刷新后重新解析。实例消失、属性变化或保护装备被其他角色占用时方案失效；自动装配和拆卸先显示操作清单，执行时逐件校验游戏实时来源与结果。</li><li><b>等级：</b>ACE ≥ 95%、S ≥ 85%、A ≥ 70%、B ≥ 50%，其余 C。单件按自身百分制评分，总评按配装毕业率。缺推荐、缺词条、摆放重叠或越界时不生成总评。用户端只显示当前装备，已移除候选列表。</li><li><b>口径：</b>未选择属性为 0；已选择的 P1 仍为正权重。词条种类衡量推荐适配度，品质按实数值比例折算；强化等级不重复叠加，套装和实战收益不计分。</li></ul><div class="cassette-scoring-example"><b>示例</b><span>若合法副词条池的前四档为 P5、P4、P3、P2（权重和 3.1），则金色“主属性 P5 + 四条 P1”约为 <strong>80.6 分</strong>；金色“主属性 P4 + 副属性 P5/P4/P3/P2”是 <strong>91 分</strong>。紫色、蓝色示例分别再乘 0.80、0.60。</span></div></aside>`;
  if (!cassette) { target.innerHTML = policy + emptyState("没有来源卡带可供配置推荐属性"); return; }
  const buildGroup = (kind, title) => {
    const selected = new Map(recommendedAffixes(cassette, kind).map((item) => [item.name, normalizeAffixPriority(item.priority)]));
    const options = CASSETTE_RECOMMENDATION_AFFIX_OPTIONS[kind];
    const preservedSelections = [...selected.keys()].filter((name) => !options.includes(name));
    const pool = [...options, ...preservedSelections];
    return '<div class="affix-editor-group"><div class="affix-editor-group-head"><div><b>' + title + '</b><small>点选属性，再拖动调节优先级（1–5）</small></div><span>' + selected.size + ' 项已选</span></div><div class="affix-editor-options">' +
      pool.map((name) => {
        const isSelected = selected.has(name);
        const priority = selected.get(name) || 1;
        return '<div class="affix-editor-row"><button type="button" class="affix-choice pressable' + (isSelected ? ' is-selected' : '') + '" data-affix-option="' + kind + '" data-affix-name="' + escapeHtml(name) + '" aria-pressed="' + isSelected + '">' + (isSelected ? '✓ ' : '+ ') + escapeHtml(name) + '</button><label class="affix-priority"><span>优先级</span><output data-affix-priority-value>' + priority + '/5</output><input data-affix-priority type="range" min="1" max="5" step="1" value="' + priority + '" aria-label="' + escapeHtml(name) + '优先级" aria-valuetext="' + priority + ' / 5"' + (isSelected ? '' : ' disabled') + '></label></div>';
      }).join("") + '</div></div>';
  };
  target.innerHTML = policy + '<div class="affix-editor-note">这里只维护推荐，不改变原站记录的随机可出现词条池。</div>' +
    buildGroup("main", "推荐主属性") +
    buildGroup("sub", "推荐副属性");
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
  target.addEventListener("input", (event) => {
    if (!event.target.matches("[data-affix-priority]")) return;
    const output = event.target.closest(".affix-priority")?.querySelector("[data-affix-priority-value]");
    if (output) output.textContent = event.target.value + "/5";
    event.target.setAttribute("aria-valuetext", event.target.value + " / 5");
    syncCassetteRecommendations(activeKnowledge, target);
  });
}

function resolveRecommendedCassette(knowledge) {
  const cassette = knowledge.recommended?.cassette;
  if (!cassette) return cassette;
  const catalogItem = (skyCurtainCatalog.items || []).find((item) => item.id === cassette.id);
  return { ...cassette, acquisition: catalogItem?.acquisition || cassette.acquisition || "",
    set_effects: catalogItem?.set_effects ? [{pieces:2,description:catalogItem.set_effects.two_piece},{pieces:4,description:catalogItem.set_effects.four_piece}] : cassette.set_effects,
    set_requirements: catalogItem?.set_requirements };
}

function renderCassette(knowledge) {
  const target = $("#cassetteDetails");
  const data = resolveRecommendedCassette(knowledge);
  if (!target) return;
  const terminalMarkup = renderTerminalCard(knowledge.terminal || data?.terminal, knowledge);
  if (!data) { target.innerHTML = terminalMarkup || emptyState("没有来源卡带详情"); return; }
  const effects = data.set_effects || [];
  const structure = data.structure || {};
  target.innerHTML = '<div class="cassette-summary">' + (data.icon ? '<img src="' + escapeHtml(importedAssetUrl({ local_path: data.icon })) + '" alt="' + escapeHtml(data.name) + '">' : '<span class="asset-placeholder">带</span>') + '<div><b>' + escapeHtml(data.name) + '</b><span>' + [data.category, data.cassette_type, data.element && `${data.element}属性`].filter(Boolean).map(escapeHtml).join(" · ") + '</span><small>' + escapeHtml(data.acquisition || "获取方式待补充") + '</small></div></div><div class="set-effects">' + (effects.length ? effects.map((effect) => '<div><b>' + effect.pieces + '件套</b><span>' + escapeHtml(effect.description) + '</span></div>').join("") : emptyState("暂无套装效果")) + '</div><div class="recommended-affixes"><div class="affix-section"><b>推荐主属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "main")) + '</div></div><div class="affix-section"><b>推荐副属性</b><div class="affix-ranking">' + renderAffixRanking(recommendedAffixes(data, "sub")) + '</div></div><small class="affix-source-note">推荐结果由维护者配置；原始随机词条池仅作为编辑参考。</small></div>' + window.TerminalPuzzle.renderRequirements(window.TerminalPuzzle.cassetteOf(knowledge)) + terminalMarkup + (structure.main_affix_count || structure.sub_affix_count ? '<div class="quality-note">' + (structure.main_affix_count ?? "—") + ' 个主属性 + ' + (structure.sub_affix_count ?? "—") + ' 个副属性 · ' + (structure.rerollable === false ? '词条不可洗练' : '洗练规则待补充') + '</div>' : '');
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

window.KekeDriveLayoutStore = {
  async exportAll() {
    const records = [];
    try {
      const database = await openDriveLayoutDb();
      const stored = await new Promise((resolve, reject) => {
        const request = database.transaction(DRIVE_LAYOUT_STORE, "readonly").objectStore(DRIVE_LAYOUT_STORE).getAll();
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => reject(request.error || new Error("读取本地摆放图失败"));
      });
      records.push(...stored);
    } catch { /* The fallback storage is checked below. */ }
    const ids = new Set(records.map(record => record.characterId));
    for (let index = 0; index < localStorage.length; index++) {
      const key = localStorage.key(index);
      if (!key?.startsWith(DRIVE_LAYOUT_FALLBACK_PREFIX)) continue;
      try {
        const record = JSON.parse(localStorage.getItem(key) || "null");
        if (record?.characterId && !ids.has(record.characterId)) records.push(record);
      } catch { /* Ignore malformed legacy records without deleting them. */ }
    }
    return records;
  },
  async clearExported(characterIds) {
    for (const id of new Set(characterIds || [])) {
      if (typeof id === "string" && id) await deleteDriveLayoutRecord(id);
    }
  }
};

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
    let savedToBrowser = false;
    try {
      await putDriveLayoutRecord(knowledge.id, file);
      savedToBrowser = true;
      const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
      if (connected) {
        const saved = await window.KekeAdminBridge.uploadDriveLayout(knowledge.id, file);
        knowledge.drive_layout_image = saved.path;
        window.characterOverrides ||= { schema_version: "1.0.0", characters: {} };
        window.characterOverrides.characters ||= {};
        window.characterOverrides.characters[knowledge.id] = {
          ...(window.characterOverrides.characters[knowledge.id] || {}),
          drive_layout_image: saved.path
        };
        await deleteDriveLayoutRecord(knowledge.id);
      }
      if (activeKnowledge?.id === knowledge.id) {
        await renderDriveLayout(knowledge);
        notify(connected ? `${knowledge.name} 的摆放图已写入项目` : `${knowledge.name} 的摆放图仅保存在此浏览器，尚未写入项目`);
      }
    } catch (error) {
      notify(savedToBrowser
        ? `摆放图已保留在当前浏览器，但写入项目失败；项目原图未变：${error.message}`
        : error.message || "图片保存失败");
    } finally {
      input.value = "";
    }
  });
  preview.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-remove-drive-layout]");
    if (!button || !activeKnowledge?.id) return;
    const knowledge = activeKnowledge;
    const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
    if (knowledge.drive_layout_image && !connected) {
      notify("这张图已属于项目资料；请通过 scripts/start_admin.ps1 启动后再删除，避免只在当前浏览器隐藏");
      return;
    }
    if (knowledge.drive_layout_image && connected) {
      await window.KekeAdminBridge.deleteDriveLayout(knowledge.id);
      const override = window.characterOverrides?.characters?.[knowledge.id];
      if (override) delete override.drive_layout_image;
    }
    await deleteDriveLayoutRecord(knowledge.id);
    if (activeKnowledge?.id === knowledge.id) {
      knowledge.drive_layout_image = "";
      await renderDriveLayout(knowledge);
      notify(connected ? `${knowledge.name} 的摆放图已从项目移除` : `${knowledge.name} 的浏览器摆放图已移除，尚未同步项目`);
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
  const reviewPill = $(".verified-pill");
  if (reviewPill) reviewPill.innerHTML = '<i></i> ' + (knowledge.manual_review?.length ? "待人工核验" : "已校验");
  renderRoleReactionEnhancements(knowledge);
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
  renderRoleContentEditors(knowledge);
  renderResonance(knowledge);
  renderSkillTargets(knowledge);
  renderCassetteRecommendationEditor(knowledge);
  renderCassette(knowledge);
  window.TerminalPuzzleEditor?.render(knowledge);
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
  syncPublicPreview();
  setText("#draftLabel", data.knowledge.review_status === "approved" ? "已审核" : "来源待核验");
  setText("#understandingTitle", data.summaryTitle);
  setText("#understandingCopy", data.summary);
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
  const currentEffect = rankDescriptions[selectedArcDriveRank - 1] || "暂无调弧效果数据。";

  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image">${item.image?.local_path ? `<img src="${escapeHtml(item.image.local_path)}" alt="${escapeHtml(item.name)}">` : "弧"}</div><div class="arc-drive-detail-title"><span class="rarity-chip rarity-${escapeHtml(item.rarity.toLowerCase())}">${escapeHtml(item.rarity)}级 · ${escapeHtml(item.type)}类</span><h2>${escapeHtml(item.name)}</h2><p>${escapeHtml(item.overview || `${item.name} · ${item.rarity}级${item.type}类弧盘`)}</p></div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>等级属性</h3><small>来源等级成长数据</small></div><label class="arc-level-select">等级<select id="arcDriveLevel">${breakpoints.map((level) => `<option value="${level}"${Number(level) === Number(selectedArcDriveLevel) ? " selected" : ""}>Lv.${level}</option>`).join("")}</select></label></div><div class="arc-stat-grid">${statRows.length ? statRows.map((row) => { const value = row.values_at_breakpoints?.[levelIndex] ?? row.current_value; return `<div class="arc-stat-card"><span>${escapeHtml(row.name || "属性")}</span><b>${escapeHtml(formatArcDriveStat(value, row.is_percent))}</b></div>`; }).join("") : emptyState("暂无等级属性数据")}</div></section>${item.description ? `<section class="arc-drive-description"><h3>说明</h3><p>${escapeHtml(item.description)}</p></section>` : ""}<section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>${escapeHtml(item.passive?.title || "调弧效果")}</h3><small>效果数值随调弧等级变化</small></div></div><div class="arc-rank-select" role="group" aria-label="调弧等级">${Array.from({ length: Math.max(rankDescriptions.length, 1) }, (_, index) => `<button type="button" class="${selectedArcDriveRank === index + 1 ? "is-active" : ""}" data-arc-rank="${index + 1}" aria-pressed="${selectedArcDriveRank === index + 1}">R${index + 1}</button>`).join("")}</div><p class="arc-effect-copy">${escapeHtml(currentEffect)}</p></section><section class="arc-drive-overview"><h3>图鉴概述</h3><p>${escapeHtml(item.overview || "暂无概述。")}</p></section>`;
}

function initArcDriveCatalog() {
  const entries = arcDriveCatalog.items || [];
  if (!entries.some((item) => item.id === selectedArcDriveId)) selectedArcDriveId = entries[0]?.id || "";
  const source = arcDriveCatalog.source || {};
  const attribution = $("#arcDriveAttribution");
  if (attribution) {
    attribution.textContent = `${source.site || "Mysqil · 环世全鉴"} · 弧盘资料；作者 ${source.author || "Matsuzaka Yuki"}；许可 ${source.license || "CC BY-NC-SA 4.0"}。非官方资料。`;
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

  const effects = item.set_effects || {};
  const renderPool = (title, pool) => {
    const values = pool?.items || [];
    return `<section class="arc-drive-description sky-curtain-pool"><h3>${escapeHtml(title)}</h3>${pool?.note ? `<p>${escapeHtml(pool.note)}</p>` : ""}<div class="sky-curtain-chip-list">${values.length ? values.map((value) => `<span class="sky-curtain-chip">${escapeHtml(value)}</span>`).join("") : `<span class="empty-state">暂无词条池。</span>`}</div></section>`;
  };
  const tierNotes = item.quality?.tiers || [];
  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image">${image?.local_path ? `<img src="${escapeHtml(image.local_path)}" alt="${escapeHtml(item.name)}·${escapeHtml(qualityLabels[selectedSkyCurtainQuality] || "金")}">` : "幕"}</div><div class="arc-drive-detail-title"><span class="sky-curtain-category-chip">${escapeHtml(item.category || "空幕")}${item.element ? ` · ${escapeHtml(item.element)}` : ""}</span><h2>${escapeHtml(item.name)}</h2></div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质图片</h3><small>金、紫、蓝品质图</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="空幕品质图片">${Object.entries(qualityLabels).map(([qualityId, label]) => `<button type="button" class="${selectedSkyCurtainQuality === qualityId ? "is-active" : ""}" data-sky-quality="${qualityId}" aria-pressed="${selectedSkyCurtainQuality === qualityId}">${label}</button>`).join("")}</div></section>${window.TerminalPuzzle.renderRequirements(item)}<section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>套装效果</h3><small>两件套与四件套效果</small></div></div><div class="sky-curtain-effect-grid"><div class="sky-curtain-effect-card"><span>2 件套</span><p>${escapeHtml(effects.two_piece || "暂无效果记录。")}</p></div><div class="sky-curtain-effect-card"><span>4 件套</span><p>${escapeHtml(effects.four_piece || "暂无效果记录。")}</p></div></div>${item.acquisition ? `<div class="arc-drive-description"><h3>获取途径</h3><p>${escapeHtml(item.acquisition)}</p></div>` : ""}</section>${renderPool("主属性可能词条", item.main_affix_pool)}${renderPool("副属性可能词条", item.sub_affix_pool)}<section class="arc-drive-description sky-curtain-quality-note"><h3>品质说明</h3>${item.quality?.role_note ? `<p><b>品质定位：</b>${escapeHtml(item.quality.role_note)}</p>` : ""}${item.quality?.note ? `<p>${escapeHtml(item.quality.note)}</p>` : ""}${tierNotes.length ? `<ul>${tierNotes.map((tier) => `<li><b>${escapeHtml(tier.quality)}</b><span>${escapeHtml(tier.description)}</span></li>`).join("")}</ul>` : ""}</section>${item.overview ? `<section class="arc-drive-overview"><h3>套装概述</h3><p>${escapeHtml(item.overview)}</p></section>` : ""}`;
}

function initSkyCurtainCatalog() {
  const entries = skyCurtainCatalog.items || [];
  if (!entries.some((item) => item.id === selectedSkyCurtainId)) selectedSkyCurtainId = entries[0]?.id || "";
  const source = skyCurtainCatalog.source || {};
  const attribution = $("#skyCurtainAttribution");
  if (attribution) {
    attribution.textContent = `${source.site || "Mysqil · 环世全鉴"} · 空幕资料；作者 ${source.author || "Matsuzaka Yuki"}；许可 ${source.license || "CC BY-NC-SA 4.0"}。非官方资料。`;
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
    target.innerHTML = emptyState("暂无此品质的数据");
    return;
  }
  const level = Math.min(tier.level?.max ?? 20, Math.max(tier.level?.min ?? 0, selectedDriverBlockLevel));
  selectedDriverBlockLevel = level;
  const levelIndex = level - (tier.level?.min ?? 0);
  const image = tier.images?.[selectedDriverBlockQuality];

  const mainStats = tier.main_stats || [];
  const randomStats = tier.random_stats || [];
  target.innerHTML = `<div class="arc-drive-detail-head"><div class="arc-drive-detail-image driver-block-artwork">${image?.local_path ? `<img src="${escapeHtml(image.local_path)}" alt="${escapeHtml(item.model)} ${escapeHtml(item.shape)} · ${qualityLabels[selectedDriverBlockQuality]}">` : "块"}</div><div class="arc-drive-detail-title"><span class="rarity-chip rarity-${escapeHtml(tier.grade.toLowerCase())}">${escapeHtml(item.model)} · ${escapeHtml(qualityLabels[selectedDriverBlockQuality])}色 ${escapeHtml(tier.grade)}级</span><h2>${escapeHtml(item.model)} · ${escapeHtml(item.shape || `${item.grid_count} 格`)}</h2><p>${escapeHtml(item.grid_count)} 格 · ${tier.random_slot_count} 个随机副词条槽 · ${randomStats.length} 种候选词条</p></div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质与形状图</h3><small>金、紫、蓝三档品质图</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="驱动块品质">${Object.entries(qualityLabels).map(([qualityId, label]) => { const qualityTier = item.qualities?.[qualityId]; return `<button type="button" class="${selectedDriverBlockQuality === qualityId ? "is-active" : ""}" data-driver-quality="${qualityId}" aria-pressed="${selectedDriverBlockQuality === qualityId}">${label} ${escapeHtml(qualityTier?.grade || "")}</button>`; }).join("")}</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>固定主属性</h3><small>强化等级成长值</small></div><label class="driver-block-level-control">强化 +<output id="driverBlockLevelValue">${level}</output><input id="driverBlockLevel" type="range" min="${tier.level?.min ?? 0}" max="${tier.level?.max ?? 20}" value="${level}" aria-label="驱动块强化等级"></label></div><div class="arc-stat-grid">${mainStats.map((stat, index) => `<div class="arc-stat-card"><span>${escapeHtml(stat.name || "主属性")}</span><b data-driver-main-stat="${index}">${escapeHtml(formatDriverBlockValue(stat.values?.[levelIndex]))}</b></div>`).join("")}</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>随机副属性</h3><small>每块装备 ${tier.random_slot_count} 条；可用候选值如下</small></div><span class="driver-block-pool-count">${randomStats.length} 种</span></div><div class="driver-block-stat-grid">${randomStats.map((stat) => `<div class="driver-block-stat-option">${stat.icon?.local_path ? `<img src="${escapeHtml(stat.icon.local_path)}" alt="">` : ""}<span>${escapeHtml(stat.name)}</span><b>${escapeHtml(formatDriverBlockValue(stat.value, stat.is_percent))}</b></div>`).join("")}</div></section>`;
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
}

function initDriverBlockCatalog() {
  const entries = driverBlockCatalog.items || [];
  if (!entries.some((item) => item.id === selectedDriverBlockId)) selectedDriverBlockId = entries[0]?.id || "";
  const source = driverBlockCatalog.source || {};
  const attribution = $("#driverBlockAttribution");
  if (attribution) {
    attribution.textContent = `${source.site || "Mysqil · 环世全鉴"} · 驱动块资料；作者 ${source.source_author || "Matsuzaka Yuki"}；许可 ${source.source_license || "CC BY-NC-SA 4.0"}。非官方资料。`;
  }
  renderDriverBlockList();
  renderDriverBlockGuide();
}

function showRoleManagement() {
  if (guideDirty && !guideCanLeave()) return;
  guideDirty = false;
  $("#guideManagerView").hidden = true;
  $("#reactionSystemView").hidden = true;
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
  if (guideDirty && !guideCanLeave()) return;
  guideDirty = false;
  $("#guideManagerView").hidden = true;
  $("#reactionSystemView").hidden = true;
  document.body.classList.remove("user-mode");
  $("#userExperienceView").hidden = true;
  $("#adminTopbarActions").hidden = false;
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
  $("#previewButton").hidden = false;
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
    else if (item.dataset.nav === "攻略阵容") showGuideManager();
    else if (item.dataset.nav === "反应体系") showReactionSystem();
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

function bindSave() {
  const save = async () => {
    const guideView = $("#guideManagerView");
    if (guideView && !guideView.hidden && !document.body.classList.contains("user-mode")) {
      $("#guideForm")?.requestSubmit();
      return;
    }
    const previousName = selectedCharacter;
    const data = characterData[previousName];
    const knowledge = data?.knowledge;
    if (!data || !knowledge?.id) { notify("没有可保存的角色资料"); return; }
    const name = $("#roleName").value.trim();
    if (!name || name.length > 80) { notify("角色名称需为 1–80 个字符"); return; }
    if (name !== previousName && characterData[name]) { notify("已有同名角色，请换一个名称"); return; }
    const patch = {
      name,
      basic: {
        rarity: $("#roleRarity").value,
        element: $("#roleElement").value,
        cassette_type: $("#roleCassetteType").value.trim(),
        role: $("#rolePosition").value.trim(),
        position: $("#roleStation").value.trim(),
        rating: $("#roleRating").value.trim(),
        summary: knowledge.basic?.summary || ""
      }
    };
    const sourceKnowledge = Object.values(rawCharacterKnowledge).find(entry => entry.id === knowledge.id) || {};
    const canonicalContent = window.characterOverrides?.characters?.[knowledge.id] || {};
    const localContent = localRoleContentOverrides[knowledge.id] || {};
    const contentPatch = {};
    for (const key of ["skills", "awakenings", "resonance"]) {
      if ((knowledge[key] || []).length || (sourceKnowledge[key] || []).length || Object.prototype.hasOwnProperty.call(canonicalContent, key) || Object.prototype.hasOwnProperty.call(localContent, key)) {
        contentPatch[key] = cloneData(knowledge[key] || []);
      }
    }
    const reactionEnhancements = cloneData(getRoleReactionDraft(knowledge));
    if ((contentPatch.skills || []).some(skill => !String(skill.name || "").trim())) { notify("每项技能都需要填写名称"); return; }
    if ((contentPatch.awakenings || []).some(awakening => !String(awakening.name || "").trim())) { notify("每个觉醒节点都需要填写名称"); return; }
    if ((contentPatch.resonance || []).some(entry => !String(entry.name || "").trim())) { notify("每个共鸣节点都需要填写名称"); return; }
    if (reactionEnhancements.some(entry => !entry.cycle_id || !(window.esperCycleKnowledge?.cycles || []).some(cycle => cycle.id === entry.cycle_id))) {
      notify("请为每条反应强化选择有效的反应类型"); return;
    }
    if (new Set(reactionEnhancements.map(entry => entry.cycle_id)).size !== reactionEnhancements.length) {
      notify("同一角色的每种反应只能添加一条强化"); return;
    }
    const cassette = knowledge.recommended?.cassette;
    if (cassette) {
      for (const kind of ["main", "sub"]) {
        const key = "recommended_" + kind + "_affixes";
        cassette[key] = recommendedAffixes(cassette, kind).map(item => ({ ...item, priority: normalizeAffixPriority(item.priority) }));
      }
    }
    const puzzlePlan = window.TerminalPuzzle?.resolve(knowledge);
    if (knowledge.recommended?.terminal_puzzle && puzzlePlan && !window.TerminalPuzzle.setStatus(knowledge,puzzlePlan).complete) {
      notify("摆法尚未满足完整4件套，请补齐缺少形状后再保存"); return;
    }
    if (knowledge.recommended?.terminal_puzzle && puzzlePlan) knowledge.recommended.terminal_puzzle = JSON.parse(JSON.stringify(puzzlePlan));
    if (!window.CharacterRecommendations.save(knowledge)) {
      notify("推荐保存失败，修改仍保留在编辑器中");
      return;
    }
    try {
      if (Object.keys(contentPatch).length) localRoleContentOverrides[knowledge.id] = contentPatch;
      localRoleReactionOverrides[knowledge.id] = reactionEnhancements;
      localRoleBasicOverrides[knowledge.id] = patch;
      localStorage.setItem(roleContentStorageKey, JSON.stringify(localRoleContentOverrides));
      localStorage.setItem(roleReactionStorageKey, JSON.stringify(localRoleReactionOverrides));
      localStorage.setItem(roleBasicStorageKey, JSON.stringify(localRoleBasicOverrides));
      syncCharacterReactionEnhancements(knowledge.id, reactionEnhancements, name);
    } catch { notify("浏览器存储不可用，角色资料没有保存"); return; }

    const original = allKnowledge[knowledge.id];
    if (original) {
      original.name = name;
      original.basic = { ...(original.basic || {}), ...patch.basic };
      if (Object.prototype.hasOwnProperty.call(contentPatch, "skills")) original.skills = cloneData(contentPatch.skills);
      if (Object.prototype.hasOwnProperty.call(contentPatch, "awakenings")) original.awakenings = cloneData(contentPatch.awakenings);
      if (Object.prototype.hasOwnProperty.call(contentPatch, "resonance")) original.resonance = cloneData(contentPatch.resonance);
    }
    knowledge.name = name;
    knowledge.basic = { ...(knowledge.basic || {}), ...patch.basic };
    if (Object.prototype.hasOwnProperty.call(contentPatch, "skills")) knowledge.skills = cloneData(contentPatch.skills);
    if (Object.prototype.hasOwnProperty.call(contentPatch, "awakenings")) knowledge.awakenings = cloneData(contentPatch.awakenings);
    if (Object.prototype.hasOwnProperty.call(contentPatch, "resonance")) knowledge.resonance = cloneData(contentPatch.resonance);
    data.rarity = patch.basic.rarity || "—";
    data.element = patch.basic.element || "—";
    data.cassetteType = patch.basic.cassette_type || "—";
    data.rating = patch.basic.rating || "—";
    data.role = patch.basic.role || "";
    data.sourcePosition = patch.basic.position || "";
    data.position = `${data.role || "定位待补充"} · ${data.sourcePosition || "站位待补充"}`;
    data.summaryTitle = `${name} · ${data.role || "定位待补充"}`;
    data.summary = patch.basic.summary || "暂无角色简介。";
    data.knowledge = knowledge;
    if (name !== previousName) {
      delete characterData[previousName];
      characterData[name] = data;
      userTeamNameById[knowledge.id] = name;
      if (userTeamOwnedNames.delete(previousName)) userTeamOwnedNames.add(name);
      userTeamPinnedCoreNames = userTeamPinnedCoreNames.map(item => item === previousName ? name : item);
      if (userTeamExpandedInvestmentNames.delete(previousName)) userTeamExpandedInvestmentNames.add(name);
      userTeamSaveSettings();
      selectedCharacter = name;
    }
    renderCharacterCards();
    applyCharacter(name, { silent: true });

    let persisted = false;
    try {
      const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
      if (connected) {
        await window.KekeAdminBridge.saveCharacter(knowledge.id, patch, knowledge.recommended || {}, contentPatch, reactionEnhancements);
        window.characterOverrides ||= { schema_version: "1.0.0", characters: {} };
        window.characterOverrides.characters ||= {};
        const existing = window.characterOverrides.characters[knowledge.id] || {};
        window.characterOverrides.characters[knowledge.id] = { ...existing, name, basic: { ...(existing.basic || {}), ...patch.basic }, ...contentPatch, reaction_enhancements: cloneData(reactionEnhancements), recommended: JSON.parse(JSON.stringify(knowledge.recommended || {})) };
        syncCharacterReactionEnhancements(knowledge.id, reactionEnhancements, name);
        delete localRoleBasicOverrides[knowledge.id];
        delete localRoleContentOverrides[knowledge.id];
        delete localRoleReactionOverrides[knowledge.id];
        if (Object.keys(localRoleBasicOverrides).length) localStorage.setItem(roleBasicStorageKey, JSON.stringify(localRoleBasicOverrides));
        else localStorage.removeItem(roleBasicStorageKey);
        if (Object.keys(localRoleContentOverrides).length) localStorage.setItem(roleContentStorageKey, JSON.stringify(localRoleContentOverrides));
        else localStorage.removeItem(roleContentStorageKey);
        if (Object.keys(localRoleReactionOverrides).length) localStorage.setItem(roleReactionStorageKey, JSON.stringify(localRoleReactionOverrides));
        else localStorage.removeItem(roleReactionStorageKey);
        persisted = true;
        window.CharacterRecommendations.clearPersistedCharacter(knowledge.id);
      }
    } catch (error) {
      notify(`已保存在本浏览器，但写入项目失败：${error.message}`);
    }
    setText("#draftLabel", persisted ? "已写入项目" : "仅保存在浏览器");
    setText(".updated-time", persisted ? "资料已写入项目" : "尚未写入项目");
    setText("#recommendationStatus", persisted ? "全部修改已保存" : "仅保存在本机，尚未写入项目");
    if (persisted) window.dispatchEvent(new Event("keke-role-saved"));
    if (persisted) notify(`${name} 的基础资料、技能、觉醒、反应强化和推荐配置已写入项目`);
    else if (!window.KekeAdminBridge?.connected) notify(`${name} 已保存在当前浏览器，尚未写入项目`);
  };
  $("#saveDraftButton").addEventListener("click", async () => {
    const button = $("#saveDraftButton");
    if (button.disabled) return;
    button.disabled = true;
    const editor = $("#editorCard");
    if (editor) editor.inert = true;
    try {
      await window.KekeAdminBridge?.waitForWrites?.();
      await save();
    } catch (error) { notify(`保存未完成，修改已保留：${error.message}`); }
    finally { button.disabled = false; if (editor) editor.inert = false; }
  });
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
bindSave();
bindRoleContentEditors();
bindImpact();
bindMisc();
bindDriveLayoutUpload();
bindUserExperience();
window.KekeAdminBridge?.bindDialog();
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

function userMaterialListMarkup(entries) {
  return entries.length
    ? `<div class="user-material-grid">${entries.map((entry) => `<article class="user-material-card">${userMediaMarkup(entry.icon, entry.name, "材")}<div><b>${escapeHtml(entry.name)}</b><span>${entry.amount.toLocaleString()}</span></div></article>`).join("")}</div>`
    : `<div class="user-empty">暂无养成材料数据。</div>`;
}

function updateUserCultivationTarget(input, knowledge) {
  const levels = String(input.dataset.levelOptions || "").split(",").map(Number).filter(Number.isFinite);
  if (!levels.length || !knowledge) return;
  const index = Math.max(0, Math.min(levels.length - 1, Number(input.value) || 0));
  userTargetLevel = levels[index];
  const output = $("#userTargetLevelValue");
  if (output) output.textContent = `Lv.${userTargetLevel}`;
  input.setAttribute("aria-valuetext", `Lv.${userTargetLevel}`);
  input.style.setProperty("--user-range-fill", `${levels.length > 1 ? (index / (levels.length - 1)) * 100 : 100}%`);
  const entries = userMaterialEntries(knowledge, userTargetLevel, userSkillTargets);
  const count = $("#userMaterialCount");
  const list = $("#userCultivationMaterialList");
  if (count) count.textContent = String(entries.length);
  if (list) list.innerHTML = userMaterialListMarkup(entries);
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
  return `<article class="user-build-card">${userMediaMarkup(image, data.name || type, fallback)}<div class="user-build-card-copy"><span>${escapeHtml(type)}${data.rating ? ` · ${escapeHtml(data.rating)}级` : ""}</span><b>${escapeHtml(data.name || "待补充")}</b><small>${escapeHtml(extra || data.description || data.cassette_type || "资料已整理")}</small></div></article>`;
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
  const cassette = resolveRecommendedCassette(knowledge);
  return `<section class="user-section-heading"><div><span class="user-section-kicker">角色概览</span><h2>先知道怎么用，再决定怎么养。</h2><p>${escapeHtml(factsForUser(knowledge))}</p></div></section><div class="user-overview-grid"><article class="user-metric-card"><span>定位</span><b>${escapeHtml(basic.role || "待补充")}</b><small>${escapeHtml(basic.position || "站位待补充")}</small></article><article class="user-metric-card"><span>技能资料</span><b>${skills.length}</b><small>项结构化技能</small></article><article class="user-metric-card"><span>养成材料</span><b>${materials.length}</b><small>种材料汇总</small></article><article class="user-metric-card"><span>等级上限</span><b>Lv.${knowledge.base_stats?.level_cap || "—"}</b><small>基础属性成长</small></article></div><div class="user-overview-columns"><section class="user-surface"><div class="user-section-heading"><div><span class="user-section-kicker">推荐起点</span><h2>先从这套配置开始。</h2></div><button class="user-text-action pressable" type="button" data-user-action="build">查看完整配装 →</button></div><div class="user-build-grid">${userBuildCard(recommended.weapon, "推荐武器", "武", recommended.weapon?.rating ? `${recommended.weapon.rating}级推荐` : "资料已整理")}${userBuildCard(cassette, "推荐空幕", "幕", cassette?.acquisition || "获取方式待补充")}</div></section><section class="user-surface user-highlight-card"><span class="user-section-kicker">玩法提示</span><div><h3>${escapeHtml(basic.role || "这个角色")}的核心是把机制用在正确时机。</h3><p>进入技能页查看完整描述，再到养成页按你的实际目标规划材料。</p></div></section></div>`;
}

function userSkillCard(skill, index) {
  const summary = skill.description_parts?.map((part) => `${part.name || ""}${part.text || ""}`).join(" ") || skill.raw_text || "暂无技能摘要。";
  const parameters = skill.parameters || [];
  return `<article class="user-skill-card"><div class="user-skill-card-head"><div><span>${escapeHtml(skill.category || `技能 ${index + 1}`)}</span><b>${escapeHtml(skill.name || "未命名技能")}</b></div><span class="user-skill-level">${skill.level_cap ? `Lv.${skill.level_cap}` : "机制"}</span></div><p>${escapeHtml(summary.slice(0, 180))}</p>${parameters.length ? `<div class="user-skill-parameters">${parameters.slice(0, 3).map((parameter) => `<span class="user-skill-parameter">${escapeHtml(parameter.label)} · ${escapeHtml(parameter.current_value || parameter.values?.[0] || "—")}</span>`).join("")}</div>` : ""}</article>`;
}

function renderUserSkills(knowledge) {
  const skills = knowledge.skills || [];
  return `<section class="user-section-heading"><div><span class="user-section-kicker">技能资料</span><h2>把机制讲清楚。</h2><p>先看每项技能的作用，再展开完整倍率和升级信息。</p></div></section>${skills.length ? `<div class="user-skills-grid">${skills.map((skill, index) => userSkillCard(skill, index)).join("")}</div>` : `<div class="user-empty">当前角色暂无可展示的技能资料。</div>`}`;
}

function renderUserBuild(knowledge) {
  const recommended = knowledge.recommended || {};
  const cassette = resolveRecommendedCassette(knowledge);
  const mainAffixes = renderAffixRanking(recommendedAffixes(cassette, "main"));
  const subAffixes = renderAffixRanking(recommendedAffixes(cassette, "sub"));
  return `<section class="user-section-heading"><div><span class="user-section-kicker">配装建议</span><h2>从一套舒服的配置开始。</h2><p>推荐属性按优先级排列；同一优先级代表近似选择，不等于唯一答案。</p></div></section><div class="user-build-layout"><section class="user-surface user-build-large"><div class="user-build-grid">${userBuildCard(recommended.weapon, "推荐武器", "武", recommended.weapon?.rating ? `${recommended.weapon.rating}级推荐` : "资料已整理")}${userBuildCard(cassette, "推荐空幕", "幕", cassette?.acquisition || "获取方式待补充")}</div><div class="user-affix-groups"><div class="user-affix-group"><span>推荐主属性</span><div class="user-affix-ranking">${mainAffixes}</div></div><div class="user-affix-group"><span>推荐副属性</span><div class="user-affix-ranking">${subAffixes}</div></div></div><div class="user-source-note"><i></i><span>原始可能词条池与维护者推荐已分开保存。</span></div></section>${window.TerminalPuzzle?.terminalOf(knowledge) ? `<section class="user-surface user-terminal-reference">${window.TerminalPuzzle.render(knowledge)}<div class="terminal-copy"><span class="terminal-kicker">终端 · 驱动加成</span><b>${escapeHtml(knowledge.terminal?.name || "卡带属性")}</b><p>${escapeHtml(knowledge.terminal?.description || "")}</p></div></section>` : `<div class="user-surface user-empty">暂无终端与细节资料。</div>`}</div>`;
}

function renderUserCultivation(knowledge) {
  const levelCap = knowledge.base_stats?.level_cap || 80;
  const levelOptions = [...new Set([30, 40, 50, 60, 70, levelCap].filter((level) => level <= levelCap))];
  if (!levelOptions.includes(Number(userTargetLevel))) userTargetLevel = levelOptions[levelOptions.length - 1] || levelCap;
  const selectedLevelIndex = Math.max(0, levelOptions.indexOf(Number(userTargetLevel)));
  const levelProgress = levelOptions.length > 1 ? (selectedLevelIndex / (levelOptions.length - 1)) * 100 : 100;
  const entries = userMaterialEntries(knowledge, userTargetLevel, userSkillTargets);
  const skills = knowledge.cultivation?.skills || [];
  const skillTargetMarkup = skills.length ? `<div class="user-skill-targets"><div class="user-skill-targets-head"><div><span>技能目标</span><b>每项技能单独规划</b><small>默认按各技能最高等级计算，调整后材料会立即更新。</small></div><em>${skills.length} 项</em></div><div class="user-skill-target-grid">${skills.map((skill, index) => { const levels = skillTargetOptions(skill); const selected = userSkillTargetValue(knowledge, skill, index); const fixed = levels.length === 1; return `<label class="user-skill-target-row"><span><b>${escapeHtml(skill.name || `技能 ${index + 1}`)}</b><small>${fixed ? "固定节点" : `可选至 Lv.${Math.max(...levels)}`}</small></span><select data-user-skill-target="${index}" ${fixed ? "disabled" : ""}>${levels.map((level) => `<option value="${level}"${level === selected ? " selected" : ""}>Lv.${level}</option>`).join("")}</select></label>`; }).join("")}</div></div>` : `<div class="user-skill-targets user-empty">当前角色暂无结构化技能养成节点。</div>`;
  return `<section class="user-section-heading"><div><span class="user-section-kicker">养成规划</span><h2>知道还差多少。</h2><p>调整角色等级和技能目标，材料清单会即时更新。</p></div></section><section class="user-surface user-cultivation-materials"><div class="user-cultivation-toolbar"><div class="user-material-heading"><span class="user-section-kicker">材料清单</span><h2><b id="userMaterialCount">${entries.length}</b> 种材料</h2></div><label class="user-level-range-control"><span class="user-level-range-heading"><span>角色目标等级</span><output id="userTargetLevelValue" for="userTargetLevel">Lv.${userTargetLevel}</output></span><input id="userTargetLevel" type="range" min="0" max="${Math.max(0, levelOptions.length - 1)}" step="1" value="${selectedLevelIndex}" data-level-options="${levelOptions.join(",")}" style="--user-range-fill:${levelProgress}%" aria-label="角色目标等级" aria-valuetext="Lv.${userTargetLevel}" ${levelOptions.length < 2 ? "disabled" : ""}><span class="user-level-range-marks" aria-hidden="true">${levelOptions.map((level) => `<span>Lv.${level}</span>`).join("")}</span></label></div>${skillTargetMarkup}<div id="userCultivationMaterialList">${userMaterialListMarkup(entries)}</div></section>`;
}

function renderUserConstellation(knowledge) {
  const section = (title, entries) => {
    const nodes = Array.isArray(entries) ? entries : [];
    return '<section class="user-surface user-constellation-section"><h2>' + title + '</h2>'
      + (nodes.length ? '<ol class="user-constellation-list">' + nodes.map((node, index) =>
        '<li><span>' + escapeHtml(title + ' ' + (node.level ?? index + 1)) + '</span><div><h3>'
        + escapeHtml(node.name || title + '节点 ' + (index + 1)) + '</h3><p>'
        + escapeHtml(node.description || '该节点的效果资料暂未补充。') + '</p></div></li>'
      ).join('') + '</ol>' : '<p class="user-empty">当前角色暂无' + title + '资料。</p>') + '</section>';
  };
  return '<section class="user-section-heading"><div><h2>觉醒与共鸣</h2><p>查看这名角色各节点的完整效果。</p></div></section>'
    + section('觉醒', knowledge.awakenings) + section('共鸣', knowledge.resonance);
}

function renderUserTabPanel(knowledge) {
  const panel = $("#userTabPanel");
  if (!panel || !knowledge) return;
  $$('[data-user-tab]').forEach((button) => button.classList.toggle('is-active', button.dataset.userTab === userActiveTab));
  panel.innerHTML = userActiveTab === "skills" ? renderUserSkills(knowledge) : userActiveTab === "constellation" ? renderUserConstellation(knowledge) : userActiveTab === "build" ? renderUserBuild(knowledge) : userActiveTab === "cultivation" ? renderUserCultivation(knowledge) : renderUserOverview(knowledge);
}

function renderUserExperience(knowledge) {
  if (!knowledge) return;
  renderUserCharacterRail();
  renderUserHero(knowledge);
  renderUserTabPanel(knowledge);
}

function showUserExperience() {
  if (guideDirty && !guideCanLeave()) return;
  guideDirty = false;
  $("#guideManagerView").hidden = true;
  $("#reactionSystemView").hidden = true;
  document.body.classList.add("user-mode");
  $("#userExperienceView").hidden = false;
  $("#roleManagementView").hidden = true;
  $("#encyclopediaView").hidden = true;
  $("#adminTopbarActions").hidden = true;
  $("#userTopbarActions").hidden = false;
  userActiveRoute = "characters";
  setText("#activeBreadcrumb", "用户端 · 角色");
  $$('[data-nav]').forEach((item) => item.classList.remove('is-active'));
  $("#encyclopediaNavTrigger")?.classList.remove('is-active');
  $$('[data-encyclopedia-kind]').forEach((item) => item.classList.remove('is-active'));
  renderUserRouteView("characters");
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
  $("#userTabPanel")?.addEventListener("input", (event) => {
    if (event.target.id === "userTargetLevel") updateUserCultivationTarget(event.target, activeKnowledge);
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
    if (event.target.id === "userTargetLevel") return;
  });
  $("#userHeroCard")?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-user-action]");
    if (!action) return;
    userActiveTab = action.dataset.userAction;
    renderUserTabPanel(activeKnowledge);
    $("#userTabNav")?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("#userAdminButton")?.addEventListener("click", showRoleManagement);
  bindUserRouteNavigation();
  bindUserCatalogRoutes();
}


function userTeamRoleKind(data) {
  const text = [data?.role, data?.position, data?.sourcePosition].filter(Boolean).join(" ");
  if (/主C|主输出|站场主C/.test(text)) return "main";
  if (/副C|副输出|爆发|破韧|DOT/.test(text)) return "secondary";
  if (/生存|治疗|护盾|防御|分摊/.test(text)) return "sustain";
  if (/辅助|支援|增益|减益|功能|聚怪|控场|回能/.test(text)) return "support";
  return "flex";
}

function userTeamRoleLabel(data) {
  return { main: "主C", secondary: "副C", support: "辅助", sustain: "生存", flex: "功能" }[userTeamRoleKind(data)] || "功能";
}

function userTeamAvailableNames() {
  return Object.keys(characterData).filter((name) => userTeamOwnedNames.has(name));
}

function userTeamCanPin(name) {
  const data = characterData[name];
  if (!data) return false;
  if (userTeamRoleKind(data) === "main") return true;
  return (window.teamGuideStore ? window.teamGuideStore.all() : (teamTemplateKnowledge.teams || [])).some((team) => team.source_core_character_id === data.id);
}

function userTeamInvestmentState(name) {
  const id = characterData[name]?.id;
  const value = id ? userTeamInvestmentByCharacterId[id] : null;
  const resonance = Number(value?.resonance);
  return {
    resonance: Number.isInteger(resonance) ? Math.max(0, Math.min(6, resonance)) : 0,
    hasSignatureArc: Boolean(value?.hasSignatureArc)
  };
}

function userTeamSaveSettings() {
  const investments = {};
  Object.keys(characterData).forEach((name) => {
    const id = characterData[name].id;
    const value = userTeamInvestmentState(name);
    investments[id] = { resonance: value.resonance, hasSignatureArc: value.hasSignatureArc };
  });
  const state = {
    schemaVersion: 1,
    ownedCharacterIds: userTeamAvailableNames().map((name) => characterData[name].id),
    pinnedMainCIds: userTeamPinnedCoreNames.map((name) => characterData[name]?.id).filter(Boolean),
    investmentsByCharacterId: investments,
    teamCount: userTeamTeamCount
  };
  try {
    localStorage.setItem("keke-user-team-v1", JSON.stringify(state));
  } catch {}
}

function userTeamInvestmentRank(name) {
  const investment = userTeamInvestmentState(name);
  return investment.resonance * 0.45 + (investment.hasSignatureArc ? 0.8 : 0);
}

function userTeamRankedMainCNames(names) {
  return names.filter(userTeamCanPin).sort((firstName, secondName) => {
    const firstData = characterData[firstName];
    const secondData = characterData[secondName];
    const firstSourceCount = (window.teamGuideStore ? window.teamGuideStore.all() : (teamTemplateKnowledge.teams || [])).filter((team) => team.source_core_character_id === firstData.id).length;
    const secondSourceCount = (window.teamGuideStore ? window.teamGuideStore.all() : (teamTemplateKnowledge.teams || [])).filter((team) => team.source_core_character_id === secondData.id).length;
    const firstScore = userTeamTierScore(firstData) + firstSourceCount * 0.25 + userTeamInvestmentRank(firstName);
    const secondScore = userTeamTierScore(secondData) + secondSourceCount * 0.25 + userTeamInvestmentRank(secondName);
    return secondScore - firstScore || firstName.localeCompare(secondName, "zh-CN");
  });
}

function userTeamIsElement(element) {
  return userTeamElementRing.includes(element);
}

function userTeamAdjacent(first, second) {
  const firstIndex = userTeamElementRing.indexOf(first);
  const secondIndex = userTeamElementRing.indexOf(second);
  if (firstIndex < 0 || secondIndex < 0) return false;
  const distance = Math.abs(firstIndex - secondIndex);
  return distance === 1 || distance === userTeamElementRing.length - 1;
}

function userTeamReactionProfile(names) {
  const attrs = [...new Set(names.map((name) => characterData[name]?.element).filter(userTeamIsElement))];
  const reactions = userTeamReactionRules.filter((rule) => rule.attrs.every((attr) => attrs.includes(attr)));
  const adjacentPairs = reactions.filter((rule) => rule.attrs.length === 2).map((rule) => rule.name);
  const derivedReactions = reactions.filter((rule) => rule.attrs.length === 3).map((rule) => rule.name);
  return { attrs, reactions: reactions.map((rule) => rule.name), adjacentPairs, derivedReactions };
}

function userTeamTierScore(data) {
  const rarityScore = { S: 3, A: 2, B: 1 }[data?.rarity] || 0;
  const ratingMatch = String(data?.rating || "").match(/T(\d)/i);
  const ratingScore = ratingMatch ? Math.max(0, 4 - Number(ratingMatch[1])) : 0;
  return rarityScore + ratingScore;
}

function userTeamEvaluate(coreName, memberNames) {
  const core = characterData[coreName] || {};
  const members = memberNames.map((name) => characterData[name]).filter(Boolean);
  const roleKinds = members.map(userTeamRoleKind);
  const counts = {
    secondary: roleKinds.filter((kind) => kind === "secondary").length,
    support: roleKinds.filter((kind) => kind === "support").length,
    sustain: roleKinds.filter((kind) => kind === "sustain").length,
    flex: roleKinds.filter((kind) => kind === "flex").length
  };
  const profile = userTeamReactionProfile([coreName, ...memberNames]);
  const coreKind = userTeamRoleKind(core);
  const primaryReaction = core.knowledge?.mechanism_facts?.primary_reaction || "";
  let score = 0;
  if (coreKind === "main" || coreKind === "secondary") score += 7;
  if (counts.secondary) score += 10;
  if (counts.support) score += 9;
  if (counts.sustain) score += 9;
  if (counts.support >= 2) score += 3;
  if (counts.sustain >= 2) score += 2;
  if (!counts.secondary) score -= 5;
  if (!counts.support && !counts.sustain) score -= 8;
  if (primaryReaction && profile.reactions.includes(primaryReaction)) score += 10;
  score += profile.adjacentPairs.length * 5;
  score += profile.derivedReactions.length * 7;
  if (members.some((member) => userTeamAdjacent(core.element, member.element))) score += 4;
  score += members.reduce((sum, member) => sum + userTeamTierScore(member), 0) * 0.4;
  score += new Set(members.map((member) => member.element).filter(userTeamIsElement)).size;
  score -= members.filter((member) => member.element === core.element).length * 0.75;
  score += [coreName, ...memberNames].reduce((sum, name) => sum + userTeamInvestmentRank(name) * 0.45, 0);
  return { score, members, memberNames, counts, profile, coreKind, primaryReaction };
}

function userTeamCandidateKey(names) {
  return [...names].sort().join("|");
}

function userTeamCreateCandidate(coreName, memberNames, options = {}) {
  const companions = memberNames.filter((name) => name !== coreName);
  const evaluated = userTeamEvaluate(coreName, companions);
  const orderedNames = options.orderedNames || [coreName, ...companions];
  return {
    ...evaluated,
    coreName,
    memberNames: orderedNames,
    missing: Math.max(0, 4 - orderedNames.length),
    candidateKind: "source",
    sourceRecord: options.sourceRecord,
    id: options.sourceRecord.id
  };
}

function userTeamCollectPlans(coreName, blockedNames = new Set(), records = null) {
  const available = new Set(userTeamAvailableNames().filter((name) => !blockedNames.has(name)));
  if (!coreName || !available.has(coreName)) return [];
  const templates = records || (window.teamGuideStore ? window.teamGuideStore.all() : (teamTemplateKnowledge.teams || []));
  return templates.map((team, maintenanceIndex) => ({ team, maintenanceIndex,
    orderedNames: Array.isArray(team.member_character_ids) ? team.member_character_ids.map((id) => userTeamNameById[id]) : [] }))
    .filter(({ team, orderedNames }) => team.editorial?.active !== false
      && team.source_core_character_id === characterData[coreName]?.id
      && orderedNames.length === 4 && new Set(orderedNames).size === 4
      && orderedNames.includes(coreName) && orderedNames.every((name) => name && available.has(name)))
    .sort((first, second) => (first.team.source_order || 0) - (second.team.source_order || 0))
    .map(({ team, orderedNames, maintenanceIndex }) => {
      const candidate = userTeamCreateCandidate(coreName, orderedNames, { sourceRecord: team, orderedNames });
      candidate.score += userTeamInvestmentRank(coreName) * 0.3;
      return { ...candidate, maintenanceIndex };
    });
}

function userTeamBuildPlans(coreName, blockedNames = new Set(), limit = 3) {
  const seen = new Set();
  return userTeamCollectPlans(coreName, blockedNames).filter((candidate) => {
    const key = userTeamCandidateKey(candidate.memberNames);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, limit);
}

function userTeamRecommendPlans(lockedCoreName = "", blockedNames = new Set(), limit = 3) {
  if (lockedCoreName) return userTeamBuildPlans(lockedCoreName, blockedNames, limit);
  const available = userTeamAvailableNames().filter((name) => !blockedNames.has(name));
  const cores = userTeamRankedMainCNames(available);
  const candidates = cores.flatMap((name) => userTeamBuildPlans(name, blockedNames, limit));
  candidates.sort((first, second) => first.missing - second.missing
    || (second.score + userTeamTierScore(characterData[second.coreName])) - (first.score + userTeamTierScore(characterData[first.coreName]))
    || cores.indexOf(first.coreName) - cores.indexOf(second.coreName)
    || first.id.localeCompare(second.id));
  const seen = new Set();
  return candidates.filter((candidate) => {
    const key = userTeamCandidateKey(candidate.memberNames);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, limit);
}

// Dual teams use maintained rosters as a joint unit. No single-team truncation or rarity ranking here.
function userTeamPairQuality(plan) {
  const { counts, profile, primaryReaction, coreKind } = plan;
  const roles = (coreKind === "main" || coreKind === "secondary" ? 7 : 0)
    + (counts.secondary ? 10 : -5) + (counts.support ? 9 : 0) + (counts.sustain ? 9 : 0)
    - (!counts.support && !counts.sustain ? 8 : 0)
    - plan.members.filter((member) => userTeamRoleKind(member) === "main").length * 8;
  const mechanism = (primaryReaction && profile.reactions.includes(primaryReaction) ? 10 : 0)
    + profile.adjacentPairs.length * 5 + profile.derivedReactions.length * 7
    + (plan.members.some((member) => userTeamAdjacent(characterData[plan.coreName].element, member.element)) ? 4 : 0);
  // Existing role/reaction facts are a structural heuristic, not damage or a skill rotation simulation.
  return roles + mechanism;
}

function userTeamMissingForCores(coreNames, records) {
  const owned = new Set(userTeamAvailableNames());
  const candidates = records.filter((team) => team.editorial?.active !== false
    && coreNames.some((name) => characterData[name]?.id === team.source_core_character_id))
    .map((team) => ({ core: userTeamNameById[team.source_core_character_id],
      names: Array.isArray(team.member_character_ids) ? team.member_character_ids.map((id) => userTeamNameById[id]) : [] }))
    .filter(({ core, names }) => core && names.length === 4 && new Set(names).size === 4 && names.includes(core) && names.every(Boolean))
    .map(({ names }) => names.filter((name) => !owned.has(name)))
    .filter((names) => names.length).sort((a, b) => a.length - b.length);
  return candidates[0] || [];
}

function userTeamRecommendPairs(lockedCoreNames = [], limit = 3) {
  const records = window.teamGuideStore ? window.teamGuideStore.all() : (teamTemplateKnowledge.teams || []);
  const owned = new Set(userTeamAvailableNames());
  const cores = [...new Set(records.filter((team) => team.editorial?.active !== false)
    .map((team) => userTeamNameById[team.source_core_character_id]).filter((name) => name && owned.has(name)))];
  const firstCores = lockedCoreNames.length ? [lockedCoreNames[0]] : cores;
  const secondCores = lockedCoreNames.length > 1 ? [lockedCoreNames[1]] : cores.filter((name) => name !== lockedCoreNames[0]);
  const byCore = new Map([...new Set([...firstCores, ...secondCores])]
    .map((name) => [name, userTeamCollectPlans(name, new Set(), records)]));
  const firstPlans = firstCores.flatMap((name) => byCore.get(name));
  const secondPlans = secondCores.flatMap((name) => byCore.get(name));
  const failure = (reason, extra = {}) => ({ pairs: [], reason, firstCount: firstPlans.length, secondCount: secondPlans.length, ...extra });
  if (lockedCoreNames.length > 2 || new Set(lockedCoreNames).size !== lockedCoreNames.length) return failure("locks");
  if (!firstPlans.length) return failure("first", { missingNames: userTeamMissingForCores(firstCores, records) });
  if (!secondPlans.length) return failure("second", { missingNames: userTeamMissingForCores(secondCores, records) });
  const quality = new Map([...firstPlans, ...secondPlans].map((plan) => [plan, userTeamPairQuality(plan)]));
  const pairs = [];
  let closestConflicts = null;
  for (const first of firstPlans) {
    const members = new Set(first.memberNames);
    for (const second of secondPlans) {
      if (first.coreName === second.coreName) continue;
      // Without locks A+B and B+A represent one combination, ordered by maintained core order.
      if (!lockedCoreNames.length && cores.indexOf(first.coreName) > cores.indexOf(second.coreName)) continue;
      const conflicts = second.memberNames.filter((name) => members.has(name));
      if (conflicts.length) {
        if (!closestConflicts || conflicts.length < closestConflicts.length) closestConflicts = conflicts;
        continue;
      }
      const scores = [quality.get(first), quality.get(second)];
      pairs.push({ first, second, id: JSON.stringify([first.id, second.id]),
        weakest: Math.min(...scores), total: scores[0] + scores[1],
        investment: [...first.memberNames, ...second.memberNames].reduce((sum, name) => sum + userTeamInvestmentRank(name), 0) });
    }
  }
  if (!pairs.length) return failure(closestConflicts ? "conflict" : "second", { conflictNames: closestConflicts || [] });
  pairs.sort((a, b) => b.weakest - a.weakest || b.total - a.total || b.investment - a.investment
    || (a.first.sourceRecord.source_order || 0) - (b.first.sourceRecord.source_order || 0)
    || (a.second.sourceRecord.source_order || 0) - (b.second.sourceRecord.source_order || 0)
    || a.first.maintenanceIndex - b.first.maintenanceIndex || a.second.maintenanceIndex - b.second.maintenanceIndex
    || a.id.localeCompare(b.id));
  const seen = new Set();
  const unique = pairs.filter(({ first, second }) => {
    const key = JSON.stringify([first.coreName, userTeamCandidateKey(first.memberNames), second.coreName, userTeamCandidateKey(second.memberNames)]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return { pairs: unique.slice(0, Math.min(3, Math.max(0, limit))), total: unique.length, reason: null };
}

function userTeamMemberCard(entry, label, isCore = false) {
  const role = userTeamRoleLabel(entry.data);
  const element = entry.data.element && entry.data.element !== "待补充" ? " · " + entry.data.element : "";
  return '<article class="user-team-member ' + (isCore ? "is-core" : "") + '">' + '<div class="user-team-member-art">' + userMediaMarkup(entry.data.icon, entry.name, entry.name.slice(0, 1)) + '</div><div class="user-team-member-copy"><span>' + escapeHtml(label) + " · " + escapeHtml(role) + '</span><b>' + escapeHtml(entry.name) + '</b><small>' + escapeHtml(role + element) + '</small></div></article>';
}

function userTeamInvestmentMarkup(name) {
  const state = userTeamInvestmentState(name);
  const resonanceOptions = Array.from({ length: 7 }, (_, level) => '<option value="' + level + '"' + (state.resonance === level ? " selected" : "") + '>共鸣 ' + level + '</option>').join("");
  return '<div class="user-team-investment"><label><span>共鸣</span><select data-user-team-resonance="' + escapeHtml(name) + '" aria-label="' + escapeHtml(name) + '共鸣等级">' + resonanceOptions + '</select></label><label class="user-team-arc-toggle"><input type="checkbox" data-user-team-signature="' + escapeHtml(name) + '"' + (state.hasSignatureArc ? " checked" : "") + '><span>专属弧盘已持有</span></label><small>按你的账号情况填写；共鸣和专属弧盘只影响方案排序，不参与伤害模拟。</small></div>';
}

function userTeamRosterCard(name, data) {
  const selected = userTeamOwnedNames.has(name);
  const pinIndex = userTeamPinnedCoreNames.indexOf(name);
  const canPin = pinIndex >= 0 || userTeamCanPin(name);
  const expanded = userTeamExpandedInvestmentNames.has(name) || pinIndex >= 0;
  const pinLabel = pinIndex === 0 ? "1队主C" : pinIndex === 1 ? "2队主C" : "锁定主C";
  return '<article class="user-team-roster-card' + (selected ? " is-selected" : "") + (pinIndex >= 0 ? " is-core-choice" : "") + '">' +
    '<div class="user-team-roster-row"><button class="user-team-roster-toggle" type="button" data-user-team-roster="' + escapeHtml(name) + '" aria-pressed="' + String(selected) + '"><span class="user-team-roster-avatar">' + (data.icon ? '<img src="' + escapeHtml(data.icon) + '" alt="">' : escapeHtml(name.slice(0, 1))) + '</span><span class="user-team-roster-name"><b>' + escapeHtml(name) + '</b><small>' + escapeHtml(userTeamRoleLabel(data) + " · " + (data.element || "属性待补充")) + '</small></span><i aria-hidden="true">' + (selected ? "✓" : "+") + '</i></button><div class="user-team-roster-tools">' +
    (canPin ? '<button class="user-team-pin' + (pinIndex >= 0 ? " is-pinned" : "") + '" type="button" data-user-team-pin="' + escapeHtml(name) + '" aria-pressed="' + String(pinIndex >= 0) + '"' + (!selected ? " disabled" : "") + '>' + (pinIndex >= 0 ? pinLabel : "锁定主C") + '</button>' : "") +
    (selected && pinIndex < 0 ? '<button class="user-team-investment-toggle" type="button" data-user-team-investment-toggle="' + escapeHtml(name) + '" aria-expanded="' + String(expanded) + '">' + (expanded ? "收起养成" : "养成") + '</button>' : "") +
    '</div></div>' + (selected && expanded ? userTeamInvestmentMarkup(name) : "") + '</article>';
}

function userTeamReasonMarkup(plan) {
  const reactionText = plan.profile.reactions.length ? plan.profile.reactions.join(" · ") : "尚未形成相邻属性环合";
  const structure = [
    "主C " + (plan.coreKind === "main" || plan.coreKind === "secondary" ? "已确定" : "需留意"),
    "副C " + (plan.counts.secondary ? "已补齐" : "缺少"),
    "辅助 " + (plan.counts.support ? "已补齐" : "缺少"),
    "生存 " + (plan.counts.sustain ? "已补齐" : "缺少")
  ].join(" · ");
  return '<div class="user-team-reason-grid"><div><span>定位结构</span><b>' + escapeHtml(structure) + '</b></div><div><span>属性环合</span><b>' + escapeHtml(reactionText) + '</b></div><div><span>属性组合</span><b>' + escapeHtml(plan.profile.attrs.join(" · ") || "待补充") + '</b></div></div>';
}

function userTeamCandidatePickerMarkup(plans, selectedIndex, teamIndex) {
  return '<div class="user-team-candidates" role="group" aria-label="第' + (teamIndex + 1) + '队候选方案">' + plans.map((plan, index) => {
    const selected = selectedIndex === index;
    const origin = "维护阵容";
    const archetype = plan.sourceRecord?.source_archetype || (plan.profile.reactions[0] ? plan.profile.reactions[0] + "反应" : "定位组合");
    return '<button class="user-team-candidate' + (selected ? " is-active" : "") + '" type="button" data-user-team-candidate="' + teamIndex + ':' + index + '" aria-pressed="' + String(selected) + '"><span>' + escapeHtml("方案 " + (index + 1)) + '</span><b>' + escapeHtml(plan.coreName + " · " + archetype) + '</b><small>' + escapeHtml(origin) + '</small></button>';
  }).join("") + '</div>';
}

function userTeamResultSection(title, teamIndex, plans, selectedIndex, joint = false) {
  if (!plans.length) {
    return '<section class="user-team-result user-team-result-empty"><div class="user-section-heading"><div><span class="user-section-kicker">' + escapeHtml(title) + '</span><h2>剩余角色暂时无法组成第二队</h2><p>剩余持有角色没有匹配到完整的维护阵容。可补充持有角色，或等待管理端更新阵容。</p></div><span class="user-result-pill">待选择</span></div></section>';
  }
  const safeIndex = Math.min(Math.max(0, selectedIndex), plans.length - 1);
  const plan = plans[safeIndex];
  const memberMarkup = plan.memberNames.map((name) => {
    const entry = { name, data: characterData[name] };
    const isCore = name === plan.coreName;
    const roleLabel = isCore ? (teamIndex === 0 ? "1队主C" : "2队主C") : "队友";
    return userTeamMemberCard(entry, roleLabel, isCore);
  }).join("");
  const missingMarkup = plan.missing ? '<div class="user-team-missing"><b>还差 ' + plan.missing + ' 位角色</b><span>目前有 ' + plan.memberNames.length + ' 位可用角色，纳入更多未被另一队占用的角色后可补齐。</span></div>' : "";
  const sourceRecord = plan.sourceRecord;
  const sourceMarkup = '<div class="user-team-source-note"><span>阵容说明</span><b>' + escapeHtml(sourceRecord.source_archetype || "维护阵容") + '</b>' + (sourceRecord.editorial?.notes ? '<p>' + escapeHtml(sourceRecord.editorial.notes) + '</p>' : '') + '</div>';
  return '<section class="user-team-result"><div class="user-section-heading"><div><span class="user-section-kicker">' + escapeHtml(title) + '</span><h2>' + escapeHtml(plan.coreName) + ' 的方案</h2><p>' + (joint ? '两队由同一个组合确定，八名角色互不重复。' : '从维护阵容中选择适合你的方案。') + '</p></div><span class="user-result-pill">' + "维护阵容" + '</span></div>' + (joint ? "" : userTeamCandidatePickerMarkup(plans, safeIndex, teamIndex)) + '<div class="user-team-grid">' + memberMarkup + '</div>' + missingMarkup + userTeamReasonMarkup(plan) + sourceMarkup + '</section>';
}

function userTeamPairResultMarkup(result, selectedIndex) {
  if (!result.pairs.length) {
    const titles = { first: "没有第一队候选", second: "没有第二队候选", conflict: "所有双队组合都存在角色冲突", locks: "主C锁定条件无效" };
    const reasons = { first: "第一队没有符合已选角色与核心条件的启用维护阵容。",
      second: "第二队没有符合已选角色与不同核心条件的启用维护阵容。",
      conflict: "两边均有维护阵容，但无法同时使用八名不同角色。",
      locks: "请按顺序锁定至多两位不同主C。" };
    const detail = result.conflictNames?.length ? "最近一组冲突角色：" + result.conflictNames.join("、") + "。"
      : result.missingNames?.length ? "最近一套阵容尚未勾选：" + result.missingNames.join("、") + "。" : "";
    return '<section class="user-team-result user-team-result-empty" role="status"><div class="user-section-heading"><div><h2>双队无解：' + escapeHtml(titles[result.reason]) + '</h2><p>' + escapeHtml(reasons[result.reason] + detail + "请调整角色池或锁定主C；停用阵容不会参与推荐。") + '</p></div><span class="user-result-pill">无可行组合</span></div></section>';
  }
  const safeIndex = Math.min(Math.max(0, selectedIndex), result.pairs.length - 1);
  const selected = result.pairs[safeIndex];
  const picker = '<div class="user-team-candidates" role="group" aria-label="双队组合方案">' + result.pairs.map((pair, index) =>
    '<button class="user-team-candidate' + (safeIndex === index ? ' is-active' : '') + '" type="button" data-user-team-pair="' + index + '" aria-pressed="' + (safeIndex === index) + '"><span>组合方案 ' + (index + 1) + '</span><b>第一队 · ' + escapeHtml(pair.first.coreName) + '</b><small>' + escapeHtml(pair.first.memberNames.join('、')) + '</small><b>第二队 · ' + escapeHtml(pair.second.coreName) + '</b><small>' + escapeHtml(pair.second.memberNames.join('、')) + '</small></button>'
  ).join("") + '</div>';
  return '<section class="user-team-result"><div class="user-section-heading"><div><h2>双队组合方案</h2><p>已先校验两队能够同时成立，再按双队结构与机制匹配排序。选择组合会同时切换两队，最多展示三组。</p></div><span class="user-result-pill">' + result.pairs.length + ' 组可选</span></div>' + picker + '</section>'
    + userTeamResultSection("第一队", 0, [selected.first], 0, true)
    + userTeamResultSection("第二队", 1, [selected.second], 0, true);
}

function renderUserTeamRoute() {
  const target = $("#userTeamRoute");
  if (!target) return;
  const oldRoster = target.querySelector('.user-team-roster-grid');
  const scroll = { roster: oldRoster?.scrollTop || 0, main: $('.main-content')?.scrollTop || 0, x: window.scrollX, y: window.scrollY };
  const active = document.activeElement;
  const focusAttribute = oldRoster?.contains(active) && ['data-user-team-roster', 'data-user-team-pin', 'data-user-team-investment-toggle', 'data-user-team-resonance', 'data-user-team-signature'].find((attribute) => active.hasAttribute(attribute));
  const focusValue = focusAttribute ? active.getAttribute(focusAttribute) : null;
  const allEntries = Object.entries(characterData).sort(([nameA, a], [nameB, b]) => {
    const rarityOrder = { S: 0, A: 1, B: 2 };
    return (rarityOrder[a.rarity] ?? 3) - (rarityOrder[b.rarity] ?? 3) || nameA.localeCompare(nameB, "zh-CN");
  });
  const allNames = allEntries.map(([name]) => name);
  if (!allNames.length) {
    target.innerHTML = '<div class="user-empty">当前没有可用于配队的角色资料。</div>';
    return;
  }
  userTeamPinnedCoreNames = userTeamPinnedCoreNames.filter((name) => userTeamOwnedNames.has(name)
    && (userTeamTeamCount === 2 ? Boolean(characterData[name]) : userTeamCanPin(name))).slice(0, 2);
  const rosterStatus = userTeamOwnedNames.size + " / " + allNames.length + " 人已纳入角色池";
  const rosterCards = allEntries.map(([name, data]) => userTeamRosterCard(name, data)).join("");
  const teamCountOptions = [1, 2].map((count) => '<button class="user-route-segment ' + (count === userTeamTeamCount ? "is-active" : "") + ' pressable" type="button" data-user-team-count="' + count + '" aria-pressed="' + String(count === userTeamTeamCount) + '">' + count + '队</button>').join("");
  const pinnedMarkup = userTeamPinnedCoreNames.length
    ? userTeamPinnedCoreNames.map((name, index) => '<span class="user-team-pin-slot"><i>' + (index + 1) + '</i>' + escapeHtml(name) + '</span>').join("")
    : '<span class="user-team-pin-empty">交给助手推荐主C；有明确偏好时，可在角色卡片上锁定，最多两位。</span>';
  let resultMarkup = '<section class="user-team-result user-team-result-empty"><div class="user-section-heading"><div><span class="user-section-kicker">02 · 候选结果</span><h2>先选你的持有角色</h2><p>选择持有角色后直接生成；助手会推荐主C，也可手动锁定。</p></div><span class="user-result-pill">待生成</span></div></section>';
  if (userTeamGenerated) {
    if (userTeamTeamCount === 2) {
      resultMarkup = userTeamPairResultMarkup(userTeamRecommendPairs(userTeamPinnedCoreNames), userTeamSelectedCandidateIndexes[0] || 0);
    } else {
      const firstBlocked = new Set(userTeamPinnedCoreNames.slice(1));
      const firstPlans = userTeamRecommendPlans(userTeamPinnedCoreNames[0], firstBlocked, 3);
      if (!firstPlans.length) {
        resultMarkup = '<section class="user-team-result user-team-result-empty"><div class="user-section-heading"><div><h2>无法生成第一队</h2><p>当前持有角色没有匹配到完整的维护阵容。可补充持有角色，或调整锁定主C。</p></div><span class="user-result-pill">暂无匹配</span></div></section>';
      } else {
        resultMarkup = userTeamResultSection("02 · 第一队候选", 0, firstPlans, userTeamSelectedCandidateIndexes[0] || 0);
      }
    }
  }
  target.innerHTML = '<div class="user-route-intro"><div><span class="user-section-kicker">角色池 · 多方案 · 双队去重</span><h1 id="userTeamTitle">自动配队 1.0</h1><p>勾选你的角色，助手会推荐维护阵容；双队会先检查完整组合，再一起展示两队。</p></div><div class="user-route-status"><i></i><span>' + escapeHtml(rosterStatus) + '</span></div></div>' +
    '<section class="user-surface user-team-builder"><div class="user-team-builder-head"><div><span class="user-section-kicker">01 · 角色池</span><h2>先告诉助手你有哪些角色。</h2><p>首次使用从空角色池开始；持有状态、共鸣和专属弧盘只保存在当前浏览器。</p></div><div class="user-team-roster-actions"><button class="user-secondary-action pressable" type="button" data-user-team-roster-action="all">全部纳入</button><button class="user-secondary-action pressable" type="button" data-user-team-roster-action="clear">清空角色池</button></div></div><div class="user-team-roster-grid">' + rosterCards + '</div></section>' +
    '<section class="user-surface user-team-builder user-team-controls-surface"><div class="user-team-controls"><div class="user-team-core-locks"><span>主C偏好（可选）</span><div class="user-team-pin-slots">' + pinnedMarkup + '</div></div><div class="user-route-control"><span>生成队伍数</span><div class="user-route-segments" role="group" aria-label="生成队伍数">' + teamCountOptions + '</div></div><button class="user-primary-action pressable" type="button" data-user-team-generate>生成候选</button></div><div class="user-team-rule-note"><span class="user-section-kicker">候选依据</span><p>仅从管理端维护的完整阵容中，按持有角色筛选。未锁定时自动推荐主C；最多可锁定两位，分别用于第一队和第二队，成员不会跨队重复。共鸣和专属弧盘只用于方案排序，不等同伤害模拟。</p></div></section>' + resultMarkup;
  const roster = target.querySelector('.user-team-roster-grid');
  if (roster) roster.scrollTop = scroll.roster;
  const main = $('.main-content');
  if (main) main.scrollTop = scroll.main;
  window.scrollTo({ left: scroll.x, top: scroll.y, behavior: 'instant' });
  if (focusAttribute) [...target.querySelectorAll('[' + focusAttribute + ']')]
    .find((element) => element.getAttribute(focusAttribute) === focusValue)?.focus({ preventScroll: true });
}
function renderUserArcDriveRoute() {
  const target = $("#userArcDriveRoute");
  if (!target) return;
  const items = (arcDriveCatalog.items || []).filter((item) => !userArcDriveSearchQuery || arcDriveSearchText(item).includes(userArcDriveSearchQuery));
  if (!items.some((item) => item.id === userSelectedArcDriveId)) userSelectedArcDriveId = items[0]?.id || "";
  const selected = items.find((item) => item.id === userSelectedArcDriveId);
  const stats = selected?.stats || {};
  const breakpoints = stats.level_breakpoints || [1, 20, 30, 40, 50, 60, 70, 80];
  if (!breakpoints.some((level) => Number(level) === Number(userArcDriveLevel))) userArcDriveLevel = Number(breakpoints[breakpoints.length - 1] || 80);
  const levelIndex = Math.max(0, breakpoints.findIndex((level) => Number(level) === Number(userArcDriveLevel)));
  const statRows = stats.rows || [];
  const rankDescriptions = selected?.passive?.rank_descriptions || [];
  const currentEffect = rankDescriptions[userArcDriveRank - 1] || selected?.passive?.description_template || "暂无调弧效果数据。";
  const cards = items.map((item) => {
    const image = item.image?.local_path ? '<img src="' + escapeHtml(item.image.local_path) + '" alt=""> ' : "弧";
    return '<button class="user-library-card' + (item.id === userSelectedArcDriveId ? " is-active" : "") + '" type="button" data-user-arc-drive-id="' + escapeHtml(item.id) + '" aria-pressed="' + String(item.id === userSelectedArcDriveId) + '"><span class="user-library-image">' + image + '</span><span><small>' + escapeHtml((item.rarity || "—") + "级 · " + (item.type || "弧盘")) + '</small><b>' + escapeHtml(item.name) + '</b></span></button>';
  }).join("");
  const levels = breakpoints.map((level) => '<option value="' + escapeHtml(level) + '"' + (Number(level) === Number(userArcDriveLevel) ? " selected" : "") + '>Lv.' + escapeHtml(level) + '</option>').join("");
  const ranks = Array.from({ length: Math.max(rankDescriptions.length, 1) }, (_, index) => '<button type="button" class="' + (userArcDriveRank === index + 1 ? "is-active" : "") + '" data-user-arc-rank="' + (index + 1) + '" aria-pressed="' + String(userArcDriveRank === index + 1) + '">R' + (index + 1) + '</button>').join("");
  const statMarkup = statRows.length ? statRows.map((row) => {
    const value = row.values_at_breakpoints?.[levelIndex] ?? row.current_value;
    return '<div><span>' + escapeHtml(row.name || "属性") + '</span><b>' + escapeHtml(formatArcDriveStat(value, row.is_percent)) + '</b></div>';
  }).join("") : emptyState("暂无等级属性数据");
  const detail = selected ? '<article class="user-library-detail"><div class="user-library-detail-head"><div class="user-library-detail-image">' + (selected.image?.local_path ? '<img src="' + escapeHtml(selected.image.local_path) + '" alt="' + escapeHtml(selected.name) + '">' : "弧") + '</div><div><span class="user-result-pill">' + escapeHtml((selected.rarity || "—") + "级 · " + (selected.type || "弧盘")) + '</span><h2>' + escapeHtml(selected.name) + '</h2><p>' + escapeHtml(selected.overview || selected.description || "查看弧盘属性与调弧效果。") + '</p>' + '</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>等级属性</h3><small>随所选等级查看属性成长</small></div><label class="arc-level-select">等级<select data-user-arc-level aria-label="弧盘等级">' + levels + '</select></label></div><div class="user-library-stat-grid">' + statMarkup + '</div></section>' + (selected.description ? '<section class="user-library-copy"><span>说明</span><p>' + escapeHtml(selected.description) + '</p></section>' : "") + '<section class="user-library-copy"><span>' + escapeHtml(selected.passive?.title || "调弧效果") + '</span><div class="arc-rank-select" role="group" aria-label="用户端调弧等级">' + ranks + '</div><p>' + escapeHtml(currentEffect) + '</p></section></article>' : '<div class="user-empty">没有找到符合条件的弧盘。</div>';
  target.innerHTML = '<div class="user-route-intro"><div><span class="user-section-kicker">图鉴</span><h1 id="userArcDriveTitle">弧盘</h1><p>查看等级属性与调弧效果，按当前目标调整调弧等级。</p></div><div class="user-route-status"><i></i><span>' + items.length + ' / ' + (arcDriveCatalog.items || []).length + ' 件</span></div></div><div class="user-library-toolbar"><label class="user-search"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 4 4" stroke="currentColor" stroke-linecap="round"/></svg><input id="userArcDriveSearch" type="search" value="' + escapeHtml(userArcDriveSearchQuery) + '" placeholder="搜索弧盘名称、类型或效果" aria-label="搜索弧盘"></label></div><div class="user-library-layout"><div class="user-library-grid" aria-label="用户端弧盘列表">' + (cards || '<div class="user-empty">没有找到符合条件的弧盘。</div>') + '</div>' + detail + '</div>';
}

function renderUserSkyCurtainRoute() {
  const target = $("#userSkyCurtainRoute");
  if (!target) return;
  const items = (skyCurtainCatalog.items || []).filter((item) => !userSkyCurtainSearchQuery || skyCurtainSearchText(item).includes(userSkyCurtainSearchQuery));
  if (!items.some((item) => item.id === userSelectedSkyCurtainId)) userSelectedSkyCurtainId = items[0]?.id || "";
  const selected = items.find((item) => item.id === userSelectedSkyCurtainId);
  const qualityLabels = { gold: "金", purple: "紫", blue: "蓝" };
  if (selected && !selected.images?.[userSkyCurtainQuality]) userSkyCurtainQuality = "gold";
  const image = selected?.images?.[userSkyCurtainQuality] || selected?.images?.gold || Object.values(selected?.images || {})[0];
  const cards = items.map((item) => {
    const cardImage = item.images?.gold?.local_path || Object.values(item.images || {})[0]?.local_path || "";
    return '<button class="user-library-card' + (item.id === userSelectedSkyCurtainId ? " is-active" : "") + '" type="button" data-user-sky-curtain-id="' + escapeHtml(item.id) + '" aria-pressed="' + String(item.id === userSelectedSkyCurtainId) + '"><span class="user-library-image">' + (cardImage ? '<img src="' + escapeHtml(cardImage) + '" alt="">' : "幕") + '</span><span><small>' + escapeHtml([item.category, item.element].filter(Boolean).join(" · ") || "空幕套装") + '</small><b>' + escapeHtml(item.name) + '</b></span></button>';
  }).join("");
  const qualityButtons = Object.entries(qualityLabels).map(([qualityId, label]) => '<button type="button" class="' + (userSkyCurtainQuality === qualityId ? "is-active" : "") + '" data-user-sky-quality="' + qualityId + '" aria-pressed="' + String(userSkyCurtainQuality === qualityId) + '">' + label + '</button>').join("");
  const renderPool = (title, pool) => {
    const values = pool?.items || [];
    return '<section class="user-library-copy"><span>' + escapeHtml(title) + '</span>' + (pool?.note ? '<p>' + escapeHtml(pool.note) + '</p>' : "") + '<div class="user-affix-chip-list">' + (values.length ? values.map((value) => '<span>' + escapeHtml(value) + '</span>').join("") : '<span>暂无词条池</span>') + '</div></section>';
  };
  const effects = selected?.set_effects || {};
  const tierNotes = selected?.quality?.tiers || [];
  const detail = selected ? '<article class="user-library-detail"><div class="user-library-detail-head"><div class="user-library-detail-image">' + (image?.local_path ? '<img src="' + escapeHtml(image.local_path) + '" alt="' + escapeHtml(selected.name) + '">' : "幕") + '</div><div><span class="user-result-pill">' + escapeHtml(selected.category || "空幕") + (selected.element ? " · " + escapeHtml(selected.element) : "") + '</span><h2>' + escapeHtml(selected.name) + '</h2><p>' + escapeHtml(selected.overview || "查看套装效果与词条详情。") + '</p>' + '</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质图片</h3><small>切换品质查看对应图像</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="用户端空幕品质">' + qualityButtons + '</div></section>' + window.TerminalPuzzle.renderRequirements(selected) + '<div class="user-sky-effects"><div><span>2 件套</span><p>' + escapeHtml(effects.two_piece || "暂无") + '</p></div><div><span>4 件套</span><p>' + escapeHtml(effects.four_piece || "暂无") + '</p></div></div>' + (selected.acquisition ? '<section class="user-library-copy"><span>获取途径</span><p>' + escapeHtml(selected.acquisition) + '</p></section>' : "") + renderPool("主属性可能词条", selected.main_affix_pool) + renderPool("副属性可能词条", selected.sub_affix_pool) + '<section class="user-library-copy"><span>品质说明</span>' + (selected.quality?.role_note ? '<p><b>品质定位：</b>' + escapeHtml(selected.quality.role_note) + '</p>' : "") + (selected.quality?.note ? '<p>' + escapeHtml(selected.quality.note) + '</p>' : "") + (tierNotes.length ? '<ul>' + tierNotes.map((tier) => '<li><b>' + escapeHtml(tier.quality) + '</b><span>' + escapeHtml(tier.description) + '</span></li>').join("") + '</ul>' : "") + '</section></article>' : '<div class="user-empty">没有找到符合条件的空幕。</div>';
  target.innerHTML = '<div class="user-route-intro"><div><span class="user-section-kicker">图鉴</span><h1 id="userSkyCurtainTitle">空幕</h1><p>查看套装效果、获取途径和可能词条。</p></div><div class="user-route-status"><i></i><span>' + items.length + ' / ' + (skyCurtainCatalog.items || []).length + ' 套</span></div></div><div class="user-library-toolbar"><label class="user-search"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 4 4" stroke="currentColor" stroke-linecap="round"/></svg><input id="userSkyCurtainSearch" type="search" value="' + escapeHtml(userSkyCurtainSearchQuery) + '" placeholder="搜索空幕名称、效果或属性" aria-label="搜索空幕"></label></div><div class="user-library-layout"><div class="user-library-grid" aria-label="用户端空幕列表">' + (cards || '<div class="user-empty">没有找到符合条件的空幕。</div>') + '</div>' + detail + '</div>';
}

function renderUserDriverBlockRoute() {
  const target = $("#userDriverBlockRoute");
  if (!target) return;
  const qualityLabels = { gold: "金", purple: "紫", blue: "蓝" };
  const items = (driverBlockCatalog.items || []).filter((item) => {
    if (userDriverBlockModelFilter !== "all" && item.model !== userDriverBlockModelFilter) return false;
    return !userDriverBlockSearchQuery || driverBlockSearchText(item).includes(userDriverBlockSearchQuery);
  });
  if (!items.some((item) => item.id === userSelectedDriverBlockId)) userSelectedDriverBlockId = items[0]?.id || "";
  const selected = items.find((item) => item.id === userSelectedDriverBlockId);
  const tier = selected?.qualities?.[userSelectedDriverBlockQuality] || selected?.qualities?.gold;
  if (selected && !selected.qualities?.[userSelectedDriverBlockQuality]) userSelectedDriverBlockQuality = "gold";
  const activeTier = selected?.qualities?.[userSelectedDriverBlockQuality] || tier;
  const level = activeTier ? Math.min(activeTier.level?.max ?? 20, Math.max(activeTier.level?.min ?? 0, userSelectedDriverBlockLevel)) : 20;
  userSelectedDriverBlockLevel = level;
  const levelIndex = activeTier ? level - (activeTier.level?.min ?? 0) : 0;
  const modelButtons = ["all", "Ⅱ型", "Ⅲ型", "Ⅳ型"].map((model) => '<button type="button" class="' + (userDriverBlockModelFilter === model ? "is-active" : "") + '" data-user-driver-model="' + model + '" aria-pressed="' + String(userDriverBlockModelFilter === model) + '">' + (model === "all" ? "全部" : model) + '</button>').join("");
  const qualityButtons = Object.entries(qualityLabels).map(([qualityId, label]) => '<button type="button" class="' + (userSelectedDriverBlockQuality === qualityId ? "is-active" : "") + '" data-user-driver-quality="' + qualityId + '" aria-pressed="' + String(userSelectedDriverBlockQuality === qualityId) + '">' + label + (selected?.qualities?.[qualityId]?.grade ? " " + escapeHtml(selected.qualities[qualityId].grade) : "") + '</button>').join("");
  const cards = items.map((item) => {
    const itemTier = item.qualities?.[userSelectedDriverBlockQuality] || item.qualities?.gold;
    const image = itemTier?.images?.[userSelectedDriverBlockQuality]?.local_path || itemTier?.images?.gold?.local_path || "";
    return '<button class="user-library-card' + (item.id === userSelectedDriverBlockId ? " is-active" : "") + '" type="button" data-user-driver-block-id="' + escapeHtml(item.id) + '" aria-pressed="' + String(item.id === userSelectedDriverBlockId) + '"><span class="user-library-image">' + (image ? '<img src="' + escapeHtml(image) + '" alt="">' : "块") + '</span><span><small>' + escapeHtml(item.model + " · " + (item.shape || item.grid_count + " 格")) + '</small><b>' + escapeHtml(item.name || "驱动块") + '</b></span></button>';
  }).join("");
  const mainStats = activeTier?.main_stats || [];
  const randomStats = activeTier?.random_stats || [];
  const statMarkup = mainStats.map((stat, index) => '<div><span>' + escapeHtml(stat.name || "主属性") + '</span><b data-user-driver-stat="' + index + '">' + escapeHtml(formatDriverBlockValue(stat.values?.[levelIndex], stat.is_percent)) + '</b></div>').join("");
  const randomMarkup = randomStats.map((stat) => '<span>' + escapeHtml(stat.name) + ' · ' + escapeHtml(formatDriverBlockValue(stat.value, stat.is_percent)) + '</span>').join("");
  const detail = selected && activeTier ? '<article class="user-library-detail"><div class="user-library-detail-head"><div class="user-library-detail-image">' + (activeTier.images?.[userSelectedDriverBlockQuality]?.local_path ? '<img src="' + escapeHtml(activeTier.images[userSelectedDriverBlockQuality].local_path) + '" alt="' + escapeHtml(selected.name || "驱动块") + '">' : "块") + '</div><div><span class="user-result-pill">' + escapeHtml(selected.model + " · " + qualityLabels[userSelectedDriverBlockQuality] + "色 " + activeTier.grade + "级") + '</span><h2>' + escapeHtml(selected.model + " · " + (selected.shape || selected.grid_count + " 格")) + '</h2><p>' + escapeHtml(selected.grid_count + " 格 · " + activeTier.random_slot_count + " 个随机副词条槽 · " + randomStats.length + " 种候选词条") + '</p>' + '</div></div><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>品质与形状图</h3><small>切换品质查看对应成长数据</small></div></div><div class="sky-curtain-quality-selector" role="group" aria-label="用户端驱动块品质">' + qualityButtons + '</div></section><section class="arc-drive-detail-section"><div class="arc-detail-section-head"><div><h3>固定主属性</h3><small>强化 +0 至 +' + (activeTier.level?.max ?? 20) + '</small></div><label class="driver-block-level-control">强化 +<output>' + level + '</output><input data-user-driver-level type="range" min="' + (activeTier.level?.min ?? 0) + '" max="' + (activeTier.level?.max ?? 20) + '" value="' + level + '" aria-label="驱动块强化等级"></label></div><div class="user-library-stat-grid">' + statMarkup + '</div></section><section class="user-library-copy"><span>随机副属性池 · ' + randomStats.length + ' 种</span><div class="user-affix-chip-list">' + (randomMarkup || "<span>暂无随机副属性</span>") + '</div></section></article>' : '<div class="user-empty">没有找到符合条件的驱动块。</div>';
  target.innerHTML = '<div class="user-route-intro"><div><span class="user-section-kicker">图鉴</span><h1 id="userDriverBlockTitle">驱动块</h1><p>浏览型号、形状、品质成长和随机副属性。</p></div><div class="user-route-status"><i></i><span>' + items.length + ' / ' + (driverBlockCatalog.items || []).length + ' 种形状</span></div></div><div class="user-library-toolbar"><label class="user-search"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 4 4" stroke="currentColor" stroke-linecap="round"/></svg><input id="userDriverBlockSearch" type="search" value="' + escapeHtml(userDriverBlockSearchQuery) + '" placeholder="搜索型号、形状或副属性" aria-label="搜索驱动块"></label><div class="user-library-filters" role="group" aria-label="驱动块型号筛选">' + modelButtons + '</div></div><div class="user-library-layout"><div class="user-library-grid" aria-label="用户端驱动块列表">' + (cards || '<div class="user-empty">没有找到符合条件的驱动块。</div>') + '</div>' + detail + '</div>';
}

function renderUserRouteView(route = userActiveRoute) {
  const safeRoute = userRouteLabels[route] ? route : "characters";
  userActiveRoute = safeRoute;
  $$('[data-user-route-panel]').forEach((panel) => { panel.hidden = panel.dataset.userRoutePanel !== safeRoute; });
  $$('[data-user-route]').forEach((button) => { const active = button.dataset.userRoute === safeRoute; button.classList.toggle("is-active", active); if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current"); });
  setText("#activeBreadcrumb", `用户端 · ${userRouteLabels[safeRoute]}`);
  if (safeRoute === "characters") renderUserExperience(activeKnowledge);
  if (safeRoute === "team") renderUserTeamRoute();
  if (safeRoute === "arc-drives") renderUserArcDriveRoute();
  if (safeRoute === "cassettes") renderUserSkyCurtainRoute();
  if (safeRoute === "drive-blocks") renderUserDriverBlockRoute();
  if (safeRoute === "role-build") window.KekeRoleBuildStandard?.render();
  if (safeRoute === "role-build-plus") window.KekeRoleBuild?.render();
  if (safeRoute === "vision") window.KekeVision?.render();
  if (safeRoute === "inventory") window.KekeInventory?.render();
}

function showUserRoute(route) {
  if (!userRouteLabels[route]) return;
  renderUserRouteView(route);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindUserRouteNavigation() {
  $("#userPrimaryNav")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-user-route]");
    if (!button) return;
    showUserRoute(button.dataset.userRoute);
  });
}

function bindUserCatalogRoutes() {
  $("#userTeamRoute")?.addEventListener("change", (event) => {
    const resonanceInput = event.target.closest("[data-user-team-resonance]");
    const signatureInput = event.target.closest("[data-user-team-signature]");
    if (!resonanceInput && !signatureInput) return;
    const input = resonanceInput || signatureInput;
    const name = input.dataset.userTeamResonance || input.dataset.userTeamSignature;
    const id = characterData[name]?.id;
    if (!id) return;
    const current = userTeamInvestmentState(name);
    userTeamInvestmentByCharacterId[id] = {
      resonance: resonanceInput ? Number(resonanceInput.value) : current.resonance,
      hasSignatureArc: signatureInput ? signatureInput.checked : current.hasSignatureArc
    };
    userTeamGenerated = false;
    userTeamSaveSettings();
    renderUserTeamRoute();
  });
  $("#userTeamRoute")?.addEventListener("click", (event) => {
    const rosterAction = event.target.closest("[data-user-team-roster-action]");
    if (rosterAction) {
      if (rosterAction.dataset.userTeamRosterAction === "all") userTeamOwnedNames = new Set(Object.keys(characterData));
      if (rosterAction.dataset.userTeamRosterAction === "clear") {
        userTeamOwnedNames = new Set();
        userTeamPinnedCoreNames = [];
      }
      userTeamGenerated = false;
      userTeamSelectedCandidateIndexes = [0, 0];
      userTeamSaveSettings();
      renderUserTeamRoute();
      return;
    }

    const pinButton = event.target.closest("[data-user-team-pin]");
    if (pinButton) {
      const name = pinButton.dataset.userTeamPin;
      const index = userTeamPinnedCoreNames.indexOf(name);
      if (index >= 0) {
        userTeamPinnedCoreNames.splice(index, 1);
      } else if (userTeamPinnedCoreNames.length >= 2) {
        notify("最多锁定两位主C；先取消一位再添加");
        return;
      } else if (userTeamOwnedNames.has(name)) {
        userTeamPinnedCoreNames.push(name);
        userTeamExpandedInvestmentNames.add(name);
        if (userTeamPinnedCoreNames.length === 2) userTeamTeamCount = 2;
      }
      userTeamGenerated = false;
      userTeamSelectedCandidateIndexes = [0, 0];
      userTeamSaveSettings();
      renderUserTeamRoute();
      return;
    }

    const investmentToggle = event.target.closest("[data-user-team-investment-toggle]");
    if (investmentToggle) {
      const name = investmentToggle.dataset.userTeamInvestmentToggle;
      if (userTeamExpandedInvestmentNames.has(name)) userTeamExpandedInvestmentNames.delete(name);
      else userTeamExpandedInvestmentNames.add(name);
      renderUserTeamRoute();
      return;
    }

    const rosterCard = event.target.closest("[data-user-team-roster]");
    if (rosterCard) {
      const name = rosterCard.dataset.userTeamRoster;
      if (userTeamOwnedNames.has(name)) {
        userTeamOwnedNames.delete(name);
        userTeamPinnedCoreNames = userTeamPinnedCoreNames.filter((coreName) => coreName !== name);
      } else {
        userTeamOwnedNames.add(name);
      }
      userTeamGenerated = false;
      userTeamSelectedCandidateIndexes = [0, 0];
      userTeamSaveSettings();
      renderUserTeamRoute();
      return;
    }

    const pairButton = event.target.closest("[data-user-team-pair]");
    if (pairButton) {
      const index = Number(pairButton.dataset.userTeamPair);
      if (Number.isInteger(index) && index >= 0 && index < 3) {
        userTeamSelectedCandidateIndexes = [index, 0];
        renderUserTeamRoute();
        $('[data-user-team-pair="' + index + '"]')?.focus({ preventScroll: true });
      }
      return;
    }

    const candidateButton = event.target.closest("[data-user-team-candidate]");
    if (candidateButton) {
      const [teamIndex, candidateIndex] = candidateButton.dataset.userTeamCandidate.split(":").map(Number);
      if (Number.isInteger(teamIndex) && Number.isInteger(candidateIndex) && teamIndex >= 0 && teamIndex <= 1) {
        userTeamSelectedCandidateIndexes[teamIndex] = candidateIndex;
        if (teamIndex === 0) userTeamSelectedCandidateIndexes[1] = 0;
        renderUserTeamRoute();
      }
      return;
    }

    const teamCount = event.target.closest("[data-user-team-count]");
    if (teamCount) {
      userTeamTeamCount = Number(teamCount.dataset.userTeamCount) === 1 ? 1 : 2;
      userTeamGenerated = false;
      userTeamSaveSettings();
      renderUserTeamRoute();
      return;
    }

    if (event.target.closest("[data-user-team-generate]")) {
      if (!userTeamOwnedNames.size) {
        notify("先把你的角色纳入角色池");
        return;
      }
      userTeamGenerated = true;
      userTeamSelectedCandidateIndexes = [0, 0];
      renderUserTeamRoute();
      notify(!userTeamAvailableNames().some(userTeamCanPin) ? "当前角色池没有可推荐的主C，请纳入更多角色" : userTeamTeamCount === 2 ? "已检查双队组合，请查看配对结果" : "已生成多套候选阵容");
    }
  });
  $("#userArcDriveRoute")?.addEventListener("input", (event) => {
    if (event.target.id !== "userArcDriveSearch") return;
    userArcDriveSearchQuery = event.target.value.trim().toLowerCase();
    renderUserArcDriveRoute();
  });
  $("#userArcDriveRoute")?.addEventListener("change", (event) => {
    if (event.target.matches("[data-user-arc-level]")) {
      userArcDriveLevel = Number(event.target.value);
      renderUserArcDriveRoute();
    }
  });
  $("#userArcDriveRoute")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-user-arc-drive-id]");
    const rank = event.target.closest("[data-user-arc-rank]");
    if (card) {
      userSelectedArcDriveId = card.dataset.userArcDriveId;
      renderUserArcDriveRoute();
      return;
    }
    if (rank) {
      userArcDriveRank = Number(rank.dataset.userArcRank) || 1;
      renderUserArcDriveRoute();
    }
  });
  $("#userSkyCurtainRoute")?.addEventListener("input", (event) => {
    if (event.target.id !== "userSkyCurtainSearch") return;
    userSkyCurtainSearchQuery = event.target.value.trim().toLowerCase();
    renderUserSkyCurtainRoute();
  });
  $("#userSkyCurtainRoute")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-user-sky-curtain-id]");
    const quality = event.target.closest("[data-user-sky-quality]");
    if (card) {
      userSelectedSkyCurtainId = card.dataset.userSkyCurtainId;
      renderUserSkyCurtainRoute();
      return;
    }
    if (quality) {
      userSkyCurtainQuality = quality.dataset.userSkyQuality;
      renderUserSkyCurtainRoute();
    }
  });
  $("#userDriverBlockRoute")?.addEventListener("input", (event) => {
    if (event.target.matches("[data-user-driver-level]")) {
      const slider = event.target;
      userSelectedDriverBlockLevel = Number(slider.value);
      const item = (driverBlockCatalog.items || []).find((entry) => entry.id === userSelectedDriverBlockId);
      const tier = item?.qualities?.[userSelectedDriverBlockQuality] || item?.qualities?.gold;
      const levelIndex = userSelectedDriverBlockLevel - (tier?.level?.min ?? 0);
      const output = slider.closest(".driver-block-level-control")?.querySelector("output");
      if (output) output.textContent = String(userSelectedDriverBlockLevel);
      slider.closest(".arc-drive-detail-section")?.querySelectorAll(".user-library-stat-grid > div").forEach((row, index) => {
        const value = row.querySelector("b");
        const stat = tier?.main_stats?.[index];
        if (value && stat) value.textContent = formatDriverBlockValue(stat.values?.[levelIndex], stat.is_percent);
      });
      return;
    }
    if (event.target.id === "userDriverBlockSearch") {
      userDriverBlockSearchQuery = event.target.value.trim().toLowerCase();
      renderUserDriverBlockRoute();
    }
  });
  $("#userDriverBlockRoute")?.addEventListener("change", (event) => {
    if (event.target.matches("[data-user-driver-level]")) {
      userSelectedDriverBlockLevel = Number(event.target.value);
      renderUserDriverBlockRoute();
    }
  });
  $("#userDriverBlockRoute")?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-user-driver-block-id]");
    const model = event.target.closest("[data-user-driver-model]");
    const quality = event.target.closest("[data-user-driver-quality]");
    if (card) {
      userSelectedDriverBlockId = card.dataset.userDriverBlockId;
      renderUserDriverBlockRoute();
      return;
    }
    if (model) {
      userDriverBlockModelFilter = model.dataset.userDriverModel;
      renderUserDriverBlockRoute();
      return;
    }
    if (quality) {
      userSelectedDriverBlockQuality = quality.dataset.userDriverQuality;
      userSelectedDriverBlockLevel = 20;
      renderUserDriverBlockRoute();
    }
  });
}

bindGuideManager();
window.addEventListener("guide-lineups-changed", () => {
  userTeamSelectedCandidateIndexes = [0, 0];
  if (userActiveRoute === "team") renderUserTeamRoute();
});
function showAdminToolbar(showDraft = false) {
  $("#adminTopbarActions").hidden = false;
  $("#userTopbarActions").hidden = true;
  $("#previewButton").hidden = false;
  $("#saveDraftButton").hidden = !showDraft;
}
bindReactionSystem();
