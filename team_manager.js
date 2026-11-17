/* Shared guide catalog. Stored edits overlay source records without altering provenance. */
(() => {
  const key = "keke-guide-lineups-v1";
  const base = window.teamTemplateKnowledge || { teams: [], source_catalog: {} };
  const knownIds = new Set(Object.values(window.characterKnowledge || {}).map(c => c.id));
  let edits = {};
  let removed = [];
  const canonical = window.teamGuideOverrides && typeof window.teamGuideOverrides === "object" ? window.teamGuideOverrides : {};
  if (canonical.edits && typeof canonical.edits === "object" && !Array.isArray(canonical.edits)) edits = JSON.parse(JSON.stringify(canonical.edits));
  if (Array.isArray(canonical.removed)) removed = [...new Set(canonical.removed)];
  let hasLegacyEdits = false;
  try {
    const legacyText = localStorage.getItem(key);
    const saved = JSON.parse(legacyText || "{}");
    hasLegacyEdits = Boolean(legacyText);
    if (saved.edits && typeof saved.edits === "object" && !Array.isArray(saved.edits)) edits = { ...edits, ...saved.edits };
    if (Array.isArray(saved.removed)) removed = [...new Set([...removed, ...saved.removed])];
  } catch {}
  const copy = value => JSON.parse(JSON.stringify(value));
  function validate(team) {
    if (!team || typeof team.id !== "string" || !/^[a-zA-Z0-9_-]{1,120}$/.test(team.id)) throw Error("阵容编号无效");
    const members = team.member_character_ids;
    if (!Array.isArray(members) || members.length !== 4 || new Set(members).size !== 4 || members.some(id => !knownIds.has(id))) throw Error("请选择四名不同的本地角色");
    if (!members.includes(team.source_core_character_id)) throw Error("主C必须在阵容中");
    if (typeof team.source_archetype !== "string" || !team.source_archetype.trim() || team.source_archetype.length > 80) throw Error("请填写 1–80 字的阵容名称");
    if (team.editorial?.notes != null && (typeof team.editorial.notes !== "string" || team.editorial.notes.length > 3000)) throw Error("攻略说明最多 3000 字");
    return team;
  }
  function all() {
    const originals = base.teams || [];
    const ids = new Set(originals.map(t => t.id));
    return originals.filter(t => !removed.includes(t.id)).map(t => copy(edits[t.id] || t))
      .concat(Object.values(edits).filter(t => !ids.has(t.id) && !removed.includes(t.id)).map(copy));
  }
  // 记录变更代数：读取方（推荐求解、列表渲染）用它判断自己缓存的那一份 all() 是否过期，
  // 不依赖 guide-lineups-changed 是否真的被派发到（测试桩/无监听者的环境下同样可靠）。
  let revision = 0;
  function commit(nextEdits, nextRemoved) {
    localStorage.setItem(key, JSON.stringify({ schema_version: "1.0.0", edits: nextEdits, removed: nextRemoved }));
    edits = nextEdits;
    removed = nextRemoved;
    revision += 1;
    window.dispatchEvent(new Event("guide-lineups-changed"));
  }
  window.teamGuideStore = {
    all,
    revision: () => revision,
    save(team) {
      validate(team);
      commit({ ...edits, [team.id]: copy(team) }, removed.filter(id => id !== team.id));
    },
    remove(id) {
      if (!all().some(t => t.id === id)) throw Error("阵容不存在");
      commit(edits, [...new Set([...removed, id])]);
    },
    removeMany(ids) {
      const uniqueIds = [...new Set(ids)];
      const records = all();
      if (!uniqueIds.length || uniqueIds.some(id => !records.some(team => team.id === id))) throw Error("所选阵容已变化，请刷新后重试");
      commit(edits, [...new Set([...removed, ...uniqueIds])]);
      return uniqueIds.length;
    },
    restoreMany(teams) {
      if (!Array.isArray(teams) || !teams.length) throw Error("没有可撤销的阵容");
      const restored = teams.map(team => copy(validate(copy(team))));
      const ids = new Set(restored.map(team => team.id));
      if (ids.size !== restored.length) throw Error("撤销列表包含重复阵容");
      const nextEdits = { ...edits };
      restored.forEach(team => { nextEdits[team.id] = team; });
      commit(nextEdits, removed.filter(id => !ids.has(id)));
      return restored.length;
    },
    overrides() { return { schema_version: "1.0.0", edits: copy(edits), removed: [...removed] }; },
    hasLegacyEdits() { return hasLegacyEdits; },
    clearLegacy() { localStorage.removeItem(key); hasLegacyEdits = false; },
    export() { return { schema_version: "1.0.0", source_catalog: copy(base.source_catalog || {}), teams: all() }; },
    import(data) {
      if (!data || !Array.isArray(data.teams) || data.teams.length > 2000) throw Error("请选择包含 teams 数组的阵容 JSON（最多 2000 条）");
      const incoming = data.teams.map(t => copy(validate(t)));
      if (new Set(incoming.map(t => t.id)).size !== incoming.length) throw Error("文件包含重复阵容编号");
      const next = { ...edits };
      incoming.forEach(t => { next[t.id] = t; });
      commit(next, removed.filter(id => !incoming.some(t => t.id === id)));
      return incoming.length;
    }
  };
})();

let guideDraft = null;
let guideDirty = false;
let guideSlot = 0;
let guideSearch = "";
let guideFilter = "all";
let guideRosterSearch = "";
let guideUndo = null;
let guideSelected = new Set();
let guidePendingDuplicateDraft = null;

function guideBlank() {
  return { id: "local-" + (window.crypto?.randomUUID?.() || Date.now() + "-" + Math.random().toString(36).slice(2)), source_core_character_id: "", member_character_ids: ["", "", "", ""], source_archetype: "", source_order: 0, source_visibility: "local_editor", editorial: { active: true, status: "reviewed", tags: [], notes: "", updated_at: null } };
}
function guideCanLeave() {
  if (!guideDirty) return true;
  if (!window.confirm("当前阵容有未保存的修改，要放弃修改吗？")) return false;
  const saved = window.teamGuideStore.all().find(t => t.id === guideDraft?.id);
  guideDraft = saved ? JSON.parse(JSON.stringify(saved)) : guideBlank();
  guideDirty = false;
  return true;
}
function guidePick(record) {
  guideDraft = JSON.parse(JSON.stringify(record || guideBlank()));
  guideDirty = false;
  guideSlot = 0;
  renderGuideManager();
}
function showGuideManager() {
  document.body.classList.remove("user-mode");
  ["userExperienceView", "roleManagementView", "encyclopediaView", "reactionSystemView", "userTopbarActions"].forEach(id => { const el = document.getElementById(id); if (el) el.hidden = true; });
  document.getElementById("guideManagerView").hidden = false;
  showAdminToolbar();
  setText("#activeBreadcrumb", "攻略阵容");
  $$("[data-nav]").forEach(el => el.classList.toggle("is-active", el.dataset.nav === "攻略阵容"));
  $("#encyclopediaNavTrigger")?.classList.remove("is-active");
  if (!guideDraft) guideDraft = guideBlank();
  renderGuideManager();
}
function guideCharacter(id) {
  const name = userTeamNameById[id];
  return name ? { name, ...characterData[name] } : null;
}
function guideCompositionKey(team) {
  const ids = team?.member_character_ids;
  if (!Array.isArray(ids) || ids.length !== 4 || ids.some(id => typeof id !== "string" || !id) || new Set(ids).size !== 4) return "";
  return [...ids].sort().join("\u001f");
}
function guideFindCompositionDuplicates(team) {
  const key = guideCompositionKey(team);
  if (!key) return [];
  return window.teamGuideStore.all().filter(record => record.id !== team.id && guideCompositionKey(record) === key);
}
function guideDuplicateSideMarkup(team, side) {
  const ids = [...team.member_character_ids].sort((left, right) =>
    (guideCharacter(left)?.name || left).localeCompare(guideCharacter(right)?.name || right, "zh-CN"));
  return '<section class="guide-duplicate-side"><header><span>' + side + '</span><b>' + escapeHtml(team.source_archetype || "未命名阵容") + '</b></header><div class="guide-duplicate-members">' + ids.map(id => {
    const character = guideCharacter(id);
    const role = character ? userTeamRoleLabel(character) + " · " + character.element : "角色资料已不可用";
    const isCore = id === team.source_core_character_id;
    return '<article class="guide-duplicate-member' + (isCore ? " is-core" : "") + '"><div class="guide-duplicate-avatar">' + guideAvatar(id) + '</div><b>' + escapeHtml(character?.name || id) + '</b><small>' + escapeHtml(role) + '</small>' + (isCore ? '<span class="guide-duplicate-core">主C</span>' : "") + '</article>';
  }).join("") + '</div></section>';
}
function guideDuplicateComparisonsMarkup(records, draft) {
  return records.map(record => '<article class="guide-duplicate-comparison"><div class="guide-duplicate-match-label"><b>角色组成相同</b><span>已忽略角色顺序</span></div><div class="guide-duplicate-pair">' + guideDuplicateSideMarkup(record, "已有阵容") + '<span class="guide-duplicate-vs" aria-hidden="true">↔</span>' + guideDuplicateSideMarkup(draft, "当前草稿") + '</div></article>').join("");
}
function guidePrepareDraftForSave() {
  const form = $("#guideForm");
  guideDraft.source_archetype = form.elements.namedItem("title").value.trim();
  guideDraft.editorial = {
    ...guideDraft.editorial,
    notes: form.elements.namedItem("notes").value,
    active: form.elements.namedItem("active").checked,
    status: "reviewed",
    updated_at: new Date().toISOString()
  };
}
async function guidePersistDraft() {
  try {
    window.teamGuideStore.save(guideDraft);
    const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
    if (connected) await window.KekeAdminBridge.persistTeamOverrides();
    guideDirty = false;
    guidePendingDuplicateDraft = null;
    const dialog = $("#guideDuplicateDialog");
    if (dialog?.open) dialog.close();
    renderGuideManager();
    notify(connected ? "阵容已写入项目资料" : "阵容仅保存在当前浏览器；启动本地管理端后才能写入项目");
    const status = $("#guideStorageStatus");
    if (status) status.textContent = connected ? "已写入项目资料；通过资料同步提交到 GitHub。" : "仅保存在此浏览器，尚未写入项目。";
    return true;
  } catch (error) {
    const message = window.KekeAdminBridge?.connected
      ? `项目写入失败；阵容仍保存在此浏览器，尚未写入项目：${error.message}`
      : `阵容仍保存在此浏览器，但项目写入服务不可用：${error.message}`;
    const duplicateError = $("#guideDuplicateDialog[open] #guideDuplicateError");
    if (duplicateError) duplicateError.textContent = message;
    else $("#guideError").textContent = message;
    notify(message);
    return false;
  }
}
function guideAvatar(id) {
  const c = guideCharacter(id);
  return c?.icon ? '<img src="' + escapeHtml(c.icon) + '" alt="">' : '<span>＋</span>';
}
function renderGuideBoard() {
  const board = $("#guideBoard");
  if (!board || !guideDraft) return;
  board.innerHTML = guideDraft.member_character_ids.map((id, index) => {
    const c = guideCharacter(id);
    const core = id && id === guideDraft.source_core_character_id;
    return '<article class="guide-slot' + (index === guideSlot ? " is-selected" : "") + '" data-guide-drop="' + index + '">' +
      '<button type="button" class="guide-slot-pick" data-guide-slot="' + index + '" data-guide-drag="' + escapeHtml(id) + '" data-guide-from="' + index + '" aria-pressed="' + (index === guideSlot) + '" aria-label="第' + (index + 1) + '位，' + escapeHtml(c?.name || "空位") + '"><small>0' + (index + 1) + '</small><div class="guide-avatar">' + guideAvatar(id) + '</div><b>' + escapeHtml(c?.name || "拖入角色") + '</b><span>' + escapeHtml(c ? userTeamRoleLabel(c) + " · " + c.element : "或选中后点击角色") + '</span></button>' +
      (c ? '<div class="guide-slot-tools"><button type="button" data-guide-core="' + index + '" aria-pressed="' + Boolean(core) + '">' + (core ? "✓ 主C" : "设为主C") + '</button><button type="button" data-guide-remove="' + index + '" aria-label="移除' + escapeHtml(c.name) + '">移除</button></div>' : "") + '</article>';
  }).join("");
  const count = guideDraft.member_character_ids.filter(Boolean).length;
  $("#guideDraftStatus").textContent = (guideDirty ? "未保存 · " : "草稿 · ") + count + " / 4 位";
}
function renderGuideRoster() {
  $("#guideRoster").innerHTML = Object.entries(characterData).filter(([name]) => name.includes(guideRosterSearch)).map(([name, c]) =>
    '<button type="button" class="guide-roster-character' + (guideDraft.member_character_ids.includes(c.id) ? " is-used" : "") + '" data-guide-drag="' + escapeHtml(c.id) + '" data-guide-add="' + escapeHtml(c.id) + '" aria-label="将' + escapeHtml(name) + '加入选中位置"><div class="guide-roster-avatar">' + guideAvatar(c.id) + '</div><span><b>' + escapeHtml(name) + '</b><small>' + escapeHtml(userTeamRoleLabel(c) + " · " + c.element) + '</small></span></button>'
  ).join("") || '<p class="guide-empty">没有匹配角色</p>';
}
function renderGuideList() {
  const records = window.teamGuideStore.all();
  const recordIds = new Set(records.map(team => team.id));
  guideSelected = new Set([...guideSelected].filter(id => recordIds.has(id)));
  const visible = records.filter(t => (guideFilter === "all" || (guideFilter === "active" ? t.editorial?.active !== false : t.editorial?.active === false)) &&
    [t.source_archetype, ...t.member_character_ids.map(id => guideCharacter(id)?.name || ""), t.editorial?.notes].join(" ").toLowerCase().includes(guideSearch.toLowerCase()));
  $("#guideListCount").textContent = visible.length + " / " + records.length + " 套";
  $("#guideList").innerHTML = visible.map(t => '<article class="guide-saved-card' + (t.id === guideDraft?.id ? " is-active" : "") + (guideSelected.has(t.id) ? " is-bulk-selected" : "") + '"><label class="guide-card-select"><input type="checkbox" data-guide-select-id="' + escapeHtml(t.id) + '" aria-label="选择阵容 ' + escapeHtml(t.source_archetype) + '"' + (guideSelected.has(t.id) ? " checked" : "") + '><span>选择</span></label><button type="button" class="guide-saved-open" data-guide-edit="' + escapeHtml(t.id) + '"><div class="guide-saved-avatars">' + t.member_character_ids.map(id => '<span>' + guideAvatar(id) + '</span>').join("") + '</div><b>' + escapeHtml(t.source_archetype) + '</b><small>' + escapeHtml(t.member_character_ids.map(id => guideCharacter(id)?.name || id).join(" · ")) + '</small><span>' + (t.editorial?.active === false ? "已停用" : "已纳入攻略") + '</span></button><div class="guide-card-tools"><button type="button" data-guide-copy="' + escapeHtml(t.id) + '">复制</button><button type="button" data-guide-toggle="' + escapeHtml(t.id) + '">' + (t.editorial?.active === false ? "启用" : "停用") + '</button><button type="button" data-guide-delete="' + escapeHtml(t.id) + '">删除</button></div></article>').join("") || '<p class="guide-empty">暂无匹配阵容。创建一套，或调整筛选。</p>';
  updateGuideBulkControls();
}
function updateGuideBulkControls() {
  const count = $("#guideSelectedCount");
  const remove = $("[data-guide-delete-selected]");
  if (count) count.textContent = "已选 " + guideSelected.size + " 套";
  if (remove) {
    remove.disabled = guideSelected.size === 0;
    remove.textContent = guideSelected.size ? "删除所选（" + guideSelected.size + "）" : "删除所选";
  }
}
function renderGuideManager() {
  const root = $("#guideManagerView");
  root.innerHTML = '<div class="guide-heading"><div><span class="user-section-kicker">阵容工作台</span><h1>攻略阵容</h1><p>把角色拖到队伍里，让你的攻略成为配队依据。</p></div><div class="guide-actions"><button type="button" class="ghost-button" data-guide-export>导出阵容</button><label class="ghost-button guide-import">导入 JSON<input id="guideImport" type="file" accept=".json,application/json"></label><button type="button" class="primary-button" data-guide-new>＋ 新建阵容</button></div></div>' +
    '<div class="guide-workspace"><section class="guide-editor user-surface"><div class="guide-section-head"><h2>阵容编辑</h2><span id="guideDraftStatus" role="status"></span></div><p class="guide-help">拖入角色填充四个位置；拖动队内角色可交换位置。也可先点击位置，再点击角色。</p><div class="guide-board" id="guideBoard"></div><form id="guideForm"><label>阵容名称<input name="title" maxlength="80" required placeholder="例如：真红 · 盈蓄队" value="' + escapeHtml(guideDraft.source_archetype) + '"></label><label>攻略说明<textarea name="notes" maxlength="3000" rows="4" placeholder="适用场景、出场顺序、关键养成要求…">' + escapeHtml(guideDraft.editorial?.notes || "") + '</textarea></label><label class="guide-active-label"><input type="checkbox" name="active"' + (guideDraft.editorial?.active !== false ? " checked" : "") + '>启用后纳入用户端攻略阵容</label><div class="guide-save-bar"><small id="guideStorageStatus">保存后写入项目资料；可在顶栏同步 GitHub。</small><button class="primary-button" type="submit">保存阵容</button></div><p id="guideError" class="guide-error" role="alert"></p></form></section><aside class="guide-roster-panel user-surface"><div class="guide-section-head"><h2>角色库</h2><span>' + Object.keys(characterData).length + ' 位</span></div><input class="guide-search" id="guideRosterSearch" type="search" placeholder="搜索角色" value="' + escapeHtml(guideRosterSearch) + '" aria-label="搜索角色"><div class="guide-roster" id="guideRoster"></div></aside></div>' +
    '<section class="guide-library user-surface"><div class="guide-section-head"><div><h2>已有攻略阵容</h2><span id="guideListCount"></span></div><div class="guide-library-tools"><input class="guide-search" id="guideSearch" type="search" placeholder="搜索名称、角色或攻略" aria-label="搜索阵容" value="' + escapeHtml(guideSearch) + '"><select id="guideFilter" aria-label="筛选阵容状态"><option value="all">全部状态</option><option value="active">已启用</option><option value="inactive">已停用</option></select><button type="button" data-guide-undo' + (!guideUndo ? " hidden" : "") + '>撤销删除</button></div></div><div class="guide-bulk-tools"><div class="guide-bulk-selection"><span id="guideSelectedCount" role="status">已选 0 套</span><button type="button" class="ghost-button" data-guide-select-visible>全选当前结果</button><button type="button" class="ghost-button" data-guide-clear-selection>清空选择</button><small>切换搜索或筛选时，已选阵容会保留。</small></div><button type="button" class="guide-bulk-delete" data-guide-delete-selected disabled>删除所选</button></div><div class="guide-list" id="guideList"></div></section>' +
    '<dialog id="guideDuplicateDialog" class="guide-duplicate-dialog" aria-labelledby="guideDuplicateTitle" aria-describedby="guideDuplicateDescription"><div class="guide-duplicate-shell"><header class="guide-duplicate-header"><span class="user-section-kicker">保存前核对</span><h2 id="guideDuplicateTitle">已有重复阵容</h2><p id="guideDuplicateDescription"></p></header><div class="guide-duplicate-comparisons" id="guideDuplicateComparisons"></div><p id="guideDuplicateError" class="guide-error" role="alert"></p><footer class="guide-duplicate-actions"><button type="button" class="ghost-button" data-guide-duplicate-cancel>返回修改</button><button type="button" class="primary-button" data-guide-duplicate-save>仍要保存</button></footer></div></dialog>';
  $("#guideFilter").value = guideFilter;
  const storageStatus = $("#guideStorageStatus");
  if (storageStatus && window.KekeAdminBridge && window.KekeAdminBridge.connected) storageStatus.textContent = "保存后直接写入项目资料；GitHub 同步在顶栏完成。";
  $("#guideDuplicateDialog").addEventListener("close", () => { guidePendingDuplicateDraft = null; });
  renderGuideBoard();
  renderGuideRoster();
  renderGuideList();
}
function guidePlace(id, slot) {
  if (!guideCharacter(id) || !Number.isInteger(slot) || slot < 0 || slot > 3) return;
  const members = guideDraft.member_character_ids;
  const existing = members.indexOf(id);
  if (existing === slot) return;
  if (existing >= 0) members[existing] = members[slot];
  members[slot] = id;
  if (!guideDraft.source_core_character_id || !members.includes(guideDraft.source_core_character_id)) guideDraft.source_core_character_id = id;
  guideDirty = true;
  guideSlot = members.findIndex(member => !member);
  if (guideSlot < 0) guideSlot = slot;
  renderGuideBoard();
  renderGuideRoster();
}
function bindGuideManager() {
  const root = $("#guideManagerView");
  root.addEventListener("input", event => {
    if (event.target.matches("[data-guide-select-id]")) return;
    if (event.target.id === "guideRosterSearch") { guideRosterSearch = event.target.value.trim(); renderGuideRoster(); return; }
    if (event.target.id === "guideSearch") { guideSearch = event.target.value.trim(); renderGuideList(); return; }
    if (event.target.name === "title") guideDraft.source_archetype = event.target.value;
    if (event.target.name === "notes") { guideDraft.editorial ||= {}; guideDraft.editorial.notes = event.target.value; }
    if (event.target.name === "active") { guideDraft.editorial ||= {}; guideDraft.editorial.active = event.target.checked; }
    guideDirty = true;
    renderGuideBoard();
  });
  root.addEventListener("change", async event => {
    if (event.target.matches("[data-guide-select-id]")) {
      const id = event.target.dataset.guideSelectId;
      if (event.target.checked) guideSelected.add(id); else guideSelected.delete(id);
      event.target.closest(".guide-saved-card")?.classList.toggle("is-bulk-selected", event.target.checked);
      updateGuideBulkControls();
      return;
    }
    if (event.target.id === "guideFilter") { guideFilter = event.target.value; renderGuideList(); }
    if (event.target.id === "guideImport") {
      const file = event.target.files?.[0];
      if (!file) return;
      let importedLocally = false;
      try {
        if (file.size > 5000000) throw Error("文件不能超过 5 MB");
        const payload = JSON.parse(await file.text());
        if (!window.confirm("按编号合并导入阵容，同编号的已保存阵容将被更新。继续吗？")) return;
        const count = window.teamGuideStore.import(payload);
        importedLocally = true;
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistTeamOverrides();
        renderGuideList();
        notify(connected ? "已导入并写入项目 " + count + " 套阵容" : "已导入到当前浏览器 " + count + " 套阵容；尚未写入项目");
      } catch (error) {
        if (importedLocally) {
          renderGuideManager();
          notify("阵容已合并并保留在当前浏览器，但写入项目失败：" + error.message);
        } else notify("导入失败：" + error.message);
      }
      finally { event.target.value = ""; }
    }
  });
  root.addEventListener("submit", async event => {
    if (event.target.id !== "guideForm") return;
    event.preventDefault();
    try {
      guidePrepareDraftForSave();
      const duplicates = guideFindCompositionDuplicates(guideDraft);
      if (duplicates.length) {
        guidePendingDuplicateDraft = JSON.parse(JSON.stringify(guideDraft));
        $("#guideDuplicateDescription").textContent = "发现 " + duplicates.length + " 套已有攻略阵容包含相同的 4 名角色。角色顺序不影响重复判断。";
        $("#guideDuplicateComparisons").innerHTML = guideDuplicateComparisonsMarkup(duplicates, guidePendingDuplicateDraft);
        $("#guideDuplicateError").textContent = "";
        $("#guideDuplicateDialog").showModal();
        return;
      }
      await guidePersistDraft();
    } catch (error) { $("#guideError").textContent = error.message; }
  });
  root.addEventListener("click", async event => {
    const el = event.target.closest("button");
    if (!el) return;
    const d = el.dataset;
    let localChange = false;
    try {
      if ("guideDuplicateCancel" in d) {
        guidePendingDuplicateDraft = null;
        $("#guideDuplicateDialog").close();
        return;
      }
      if ("guideDuplicateSave" in d) {
        if (!guidePendingDuplicateDraft) return;
        guideDraft = guidePendingDuplicateDraft;
        await guidePersistDraft();
        return;
      }
      if ("guideNew" in d) { if (guideCanLeave()) guidePick(null); }
      if ("guideSelectVisible" in d) {
        $$("#guideList [data-guide-select-id]").forEach(input => guideSelected.add(input.dataset.guideSelectId));
        renderGuideList();
      }
      if ("guideClearSelection" in d) { guideSelected.clear(); renderGuideList(); }
      if ("guideDeleteSelected" in d) {
        const selectedIds = [...guideSelected];
        const selectedRecords = window.teamGuideStore.all().filter(record => guideSelected.has(record.id));
        if (!selectedRecords.length) { guideSelected.clear(); renderGuideList(); return; }
        const visibleIds = new Set($$("#guideList [data-guide-select-id]").map(input => input.dataset.guideSelectId));
        const hiddenCount = selectedIds.filter(id => !visibleIds.has(id)).length;
        const hiddenNote = hiddenCount ? "其中 " + hiddenCount + " 套不在当前搜索或筛选结果中。" : "";
        if (!window.confirm("确定删除所选的 " + selectedRecords.length + " 套阵容吗？" + hiddenNote + "删除后可使用“撤销删除”恢复。")) return;
        const draftWillBeDeleted = selectedRecords.some(record => record.id === guideDraft?.id);
        if (draftWillBeDeleted && !guideCanLeave()) return;
        window.teamGuideStore.removeMany(selectedRecords.map(record => record.id));
        localChange = true;
        guideUndo = selectedRecords;
        guideSelected.clear();
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistTeamOverrides();
        if (draftWillBeDeleted) guidePick(null); else renderGuideManager();
        notify(connected ? "已删除 " + selectedRecords.length + " 套阵容并写入项目，可撤销" : "已从当前浏览器删除 " + selectedRecords.length + " 套阵容，可撤销；尚未写入项目");
      }
      if ("guideSlot" in d) { guideSlot = Number(d.guideSlot); renderGuideBoard(); }
      if ("guideAdd" in d) guidePlace(d.guideAdd, guideSlot);
      if ("guideCore" in d) { guideDraft.source_core_character_id = guideDraft.member_character_ids[Number(d.guideCore)]; guideDirty = true; renderGuideBoard(); }
      if ("guideRemove" in d) {
        const index = Number(d.guideRemove);
        guideDraft.member_character_ids[index] = "";
        if (!guideDraft.member_character_ids.includes(guideDraft.source_core_character_id)) guideDraft.source_core_character_id = guideDraft.member_character_ids.find(Boolean) || "";
        guideDirty = true; guideSlot = index; renderGuideBoard(); renderGuideRoster();
      }
      const records = window.teamGuideStore.all();
      if ("guideEdit" in d && guideCanLeave()) guidePick(records.find(t => t.id === d.guideEdit));
      if ("guideCopy" in d && guideCanLeave()) {
        const record = records.find(t => t.id === d.guideCopy);
        guidePick({ ...record, id: guideBlank().id, source_archetype: record.source_archetype + "（副本）", source_visibility: "local_editor" });
        guideDirty = true; renderGuideBoard();
      }
      if ("guideToggle" in d) {
        const record = records.find(t => t.id === d.guideToggle);
        record.editorial = { ...record.editorial, active: record.editorial?.active === false, updated_at: new Date().toISOString() };
        window.teamGuideStore.save(record);
        localChange = true;
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistTeamOverrides();
        if (record.id === guideDraft.id) { guideDraft.editorial.active = record.editorial.active; $("#guideForm [name=active]").checked = record.editorial.active; }
        renderGuideList();
        notify(connected ? "攻略状态已写入项目" : "状态已保存在当前浏览器，尚未写入项目");
      }
      if ("guideDelete" in d) {
        const record = records.find(t => t.id === d.guideDelete);
        if (record.id === guideDraft.id && !guideCanLeave()) return;
        window.teamGuideStore.remove(record.id);
        localChange = true;
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistTeamOverrides();
        guideUndo = [record];
        guideSelected.delete(record.id);
        if (record.id === guideDraft.id) guidePick(null); else renderGuideManager();
        notify(connected ? "阵容已从用户攻略中移除，可撤销" : "阵容已从当前浏览器中移除，可撤销；尚未写入项目");
      }
      if ("guideUndo" in d && guideUndo) {
        const recordsToRestore = Array.isArray(guideUndo) ? guideUndo : [guideUndo];
        window.teamGuideStore.restoreMany(recordsToRestore);
        localChange = true;
        const connected = window.KekeAdminBridge ? await window.KekeAdminBridge.ready : false;
        if (connected) await window.KekeAdminBridge.persistTeamOverrides();
        guideUndo = null; renderGuideManager(); notify(connected ? "已恢复 " + recordsToRestore.length + " 套阵容并写入项目" : "已在当前浏览器恢复 " + recordsToRestore.length + " 套阵容，尚未写入项目");
      }
      if ("guideExport" in d) {
        const url = URL.createObjectURL(new Blob([JSON.stringify(window.teamGuideStore.export(), null, 2)], { type: "application/json" }));
        const a = document.createElement("a"); a.href = url; a.download = "team_templates.json"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (error) {
      if (localChange) {
        renderGuideManager();
        notify("本浏览器中的阵容修改已保留，但写入项目失败：" + error.message);
      } else notify(error.message);
    }
  });
  let drag = null;
  let suppressClick = false;
  root.addEventListener("click", event => { if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); } }, true);
  root.addEventListener("dragstart", event => event.preventDefault());
  root.addEventListener("pointerdown", event => {
    const source = event.target.closest("[data-guide-drag]");
    if (!source?.dataset.guideDrag || event.button !== 0) return;
    if (event.pointerType === "mouse") event.preventDefault();
    drag = { source, id: source.dataset.guideDrag, pointer: event.pointerId, x: event.clientX, y: event.clientY, ghost: null, target: null };
  });
  root.addEventListener("pointermove", event => {
    if (!drag || drag.pointer !== event.pointerId) return;
    if (!drag.ghost && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 8) return;
    event.preventDefault();
    if (!drag.ghost) {
      drag.source.setPointerCapture(event.pointerId);
      const rect = drag.source.getBoundingClientRect();
      drag.offsetX = drag.x - rect.left; drag.offsetY = drag.y - rect.top;
      drag.ghost = drag.source.cloneNode(true);
      drag.ghost.removeAttribute("id"); drag.ghost.classList.add("guide-drag-ghost");
      drag.ghost.style.width = rect.width + "px";
      document.body.appendChild(drag.ghost);
    }
    drag.ghost.style.transform = "translate(" + (event.clientX - drag.offsetX) + "px," + (event.clientY - drag.offsetY) + "px)";
    drag.target?.classList.remove("is-drop-target");
    drag.target = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-guide-drop]");
    drag.target?.classList.add("is-drop-target");
  });
  function endDrag(event) {
    if (!drag || drag.pointer !== event.pointerId) return;
    const finished = drag; drag = null;
    finished.target?.classList.remove("is-drop-target");
    finished.ghost?.remove();
    if (finished.source.hasPointerCapture(event.pointerId)) finished.source.releasePointerCapture(event.pointerId);
    if (finished.ghost) {
      suppressClick = true; setTimeout(() => { suppressClick = false; }, 0);
      if (event.type === "pointerup" && finished.target) guidePlace(finished.id, Number(finished.target.dataset.guideDrop));
    }
  }
  root.addEventListener("pointerup", endDrag);
  root.addEventListener("pointercancel", endDrag);
  root.addEventListener("lostpointercapture", endDrag);
  window.addEventListener("beforeunload", event => { if (guideDirty) { event.preventDefault(); event.returnValue = ""; } });
}
