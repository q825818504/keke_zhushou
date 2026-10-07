/* Local-only bridge. Git credentials stay in the user's installed Git credential helper. */
window.KekeAdminBridge = (() => {
  const pageLocation = typeof location === "undefined" ? null : location;
  const isLoopback = pageLocation?.protocol === "http:" && pageLocation.hostname === "127.0.0.1";
  let connected = false;
  let canSaveCharacter = false;
  const ready = (async () => {
    if (!isLoopback) return false;
    try {
      const response = await fetch("/api/ping", { cache: "no-store" });
      const status = await response.json();
      connected = response.ok && status.service === "keke-admin";
      canSaveCharacter = status.capabilities?.includes("character-save") === true;
    } catch { connected = false; }
    return connected;
  })();

  const pendingWrites = new Set();
  function request(path, options = {}) {
    const work = performRequest(path, options);
    if (options.method === "POST" && !path.startsWith("/api/git/")) {
      pendingWrites.add(work);
      work.then(() => pendingWrites.delete(work), () => pendingWrites.delete(work));
    }
    return work;
  }
  async function performRequest(path, options = {}) {
    if (!(await ready)) throw new Error("本地写回服务未连接。请通过 scripts/start_admin.ps1 启动管理端。旧浏览器数据仍在本机，可先导出备份。");
    const response = await fetch(path, { cache: "no-store", ...options });
    let result = {};
    try { result = await response.json(); } catch { /* The service returned a non-JSON response. */ }
    if (!response.ok || result.ok === false) throw new Error(result.error || `本地服务请求失败（${response.status}）`);
    if (options.method === "POST" && !path.startsWith("/api/git/")) window.dispatchEvent(new Event("keke-admin-saved"));
    return result;
  }

  const jsonRequest = (path, body) => request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  async function getStatus() {
    return request("/api/status");
  }

  function readLocalJson(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "{}");
      return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch { return {}; }
  }

  async function exportBrowserData() {
    const canonical = window.characterOverrides?.characters || {};
    const localBasic = readLocalJson("keke-role-basics-v1");
    const characterBasics = {};
    for (const [id, record] of Object.entries(canonical)) {
      if (record?.name || record?.basic) characterBasics[id] = { name: record.name, basic: record.basic || {} };
    }
    for (const [id, record] of Object.entries(localBasic)) {
      characterBasics[id] = { ...characterBasics[id], ...record, basic: { ...characterBasics[id]?.basic, ...record?.basic } };
    }
    const recFromStore = window.CharacterRecommendations?.export?.() || {};
    const localRecommendations = readLocalJson("keke-role-recommendations-v2");
    const characterRecommendations = { ...recFromStore, ...localRecommendations };
    const driveLayouts = [];
    const records = await window.KekeDriveLayoutStore?.exportAll?.() || [];
    for (const record of records) {
      const blob = record.blob instanceof Blob ? record.blob : null;
      let dataUrl = record.dataUrl || "";
      if (blob) dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("读取摆放图失败"));
        reader.readAsDataURL(blob);
      });
      const comma = dataUrl.indexOf(",");
      if (comma < 0) continue;
      driveLayouts.push({
        id: record.characterId,
        mime_type: record.mimeType || dataUrl.slice(5, dataUrl.indexOf(";")),
        data_base64: dataUrl.slice(comma + 1)
      });
    }
    return {
      schema_version: "1.0.0",
      exported_at: new Date().toISOString(),
      team_overrides: window.teamGuideStore?.overrides?.() || readLocalJson("keke-guide-lineups-v1"),
      character_recommendations: characterRecommendations,
      character_basics: characterBasics,
      drive_layouts: driveLayouts
    };
  }

  function mergeBrowserBackups(current, incoming) {
    const currentTeams = current.team_overrides || {};
    const incomingTeams = incoming.team_overrides || {};
    const teamEdits = { ...(currentTeams.edits || {}) };
    const removed = new Set(currentTeams.removed || []);
    for (const [id, team] of Object.entries(incomingTeams.edits || {})) {
      teamEdits[id] = team;
      removed.delete(id);
    }
    for (const id of incomingTeams.removed || []) {
      delete teamEdits[id];
      removed.add(id);
    }
    const layouts = new Map();
    for (const item of [...(current.drive_layouts || []), ...(incoming.drive_layouts || [])]) {
      if (item?.id) layouts.set(item.id, item);
    }
    const asRecord = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const recommendations = { ...asRecord(current.character_recommendations) };
    for (const [id, value] of Object.entries(asRecord(incoming.character_recommendations))) {
      recommendations[id] = { ...asRecord(recommendations[id]), ...asRecord(value) };
    }
    const basics = { ...asRecord(current.character_basics) };
    for (const [id, value] of Object.entries(asRecord(incoming.character_basics))) {
      const existing = asRecord(basics[id]);
      const imported = asRecord(value);
      basics[id] = {
        ...existing,
        ...imported,
        basic: { ...asRecord(existing.basic), ...asRecord(imported.basic) }
      };
    }
    return {
      schema_version: "1.0.0",
      exported_at: new Date().toISOString(),
      team_overrides: { schema_version: "1.0.0", edits: teamEdits, removed: [...removed] },
      character_recommendations: recommendations,
      character_basics: basics,
      drive_layouts: [...layouts.values()]
    };
  }

  function downloadJson(value, filename) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function showStatus() {
    const dialog = document.querySelector("#repoSyncDialog");
    const summary = document.querySelector("#repoSyncSummary");
    const detail = document.querySelector("#repoGitDetails");
    const pull = document.querySelector("#repoPullButton");
    const sync = document.querySelector("#repoSyncNowButton");
    const importLabel = document.querySelector("#repoImportLabel");
    const exportButton = document.querySelector("#repoExportLocalButton");
    const checkButton = document.querySelector("#repoCheckButton");
    const commitLabel = document.querySelector("#repoCommitLabel");
    if (!dialog || !summary) return;
    if (!dialog.open) dialog.showModal();
    const connectedHere = await ready;
    importLabel.hidden = !connectedHere;
    exportButton.hidden = false;
    pull.hidden = !connectedHere;
    sync.hidden = !connectedHere;
    checkButton.hidden = !connectedHere;
    commitLabel.hidden = !connectedHere;
    detail.hidden = !connectedHere;
    if (!connectedHere) {
      summary.textContent = "当前是浏览器本地模式。管理修改只保存在此浏览器，尚未写入项目或同步 GitHub。启动本地管理端后可直接写回；可先导出旧数据备份。";
      return;
    }
    summary.textContent = "正在读取 GitHub 同步状态…";
    try {
      const result = await getStatus();
      const git = result.git || {};
      if (!git.available && git.error) {
        summary.textContent = `本地写回服务已连接，但 Git 同步不可用：${git.error}`;
        detail.hidden = true;
        pull.disabled = sync.disabled = checkButton.disabled = true;
        return;
      }
      detail.hidden = false;
      pull.disabled = sync.disabled = checkButton.disabled = !git.remoteConfigured;
      const pieces = [git.branch ? `分支 ${git.branch}` : "未识别分支"];
      if (git.ahead) pieces.push(`本地领先 ${git.ahead}`);
      if (git.behind) pieces.push(`GitHub 有 ${git.behind} 个新提交`);
      pieces.push(git.dirty ? `工作区有 ${git.changes?.length || ""} 项改动` : "工作区干净");
      summary.textContent = git.remoteConfigured ? pieces.join(" · ") : `${pieces.join(" · ")} · 未配置 origin`;
      const list = document.querySelector("#repoGitChanges");
      if (list) list.textContent = (git.changes || []).slice(0, 12).join("\n") || "没有本地文件改动";
      return git;
    } catch (error) {
      summary.textContent = error.message;
      detail.hidden = true;
      return null;
    }
  }

  async function runAction(button, action) {
    const summary = document.querySelector("#repoSyncSummary");
    const buttons = [...document.querySelectorAll("#repoSyncDialog button")];
    buttons.forEach(item => { item.disabled = true; });
    try {
      summary.textContent = "正在处理…";
      const result = await action();
      summary.textContent = result.message || "操作完成。";
      await showStatus();
      if (result.message) summary.textContent = result.message;
      if (button?.id === "repoPullButton" && result.ok) {
        const reloadNote = document.querySelector("#repoReloadNote");
        if (reloadNote) reloadNote.hidden = false;
      }
    } catch (error) {
      summary.textContent = error.message;
    } finally {
      buttons.forEach(item => { item.disabled = false; });
    }
  }

  async function bindDialog() {
    await ready;
    const openButton = document.querySelector("#repoSyncButton");
    if (!openButton || openButton.dataset.bound) return;
    openButton.dataset.bound = "true";
    openButton.addEventListener("click", showStatus);
    document.querySelector("#repoSyncDialog")?.addEventListener("click", event => {
      if (event.target.closest("[data-repo-close]") || event.target === event.currentTarget) event.currentTarget.close();
    });
    document.querySelector("#repoCheckButton")?.addEventListener("click", () => runAction(null, async () => {
      await jsonRequest("/api/git/fetch", {});
      return { ok: true, message: "已检查 GitHub 远端状态。" };
    }));
    document.querySelector("#repoPullButton")?.addEventListener("click", () => runAction(document.querySelector("#repoPullButton"), () => jsonRequest("/api/git/pull", {})));
    document.querySelector("#repoSyncNowButton")?.addEventListener("click", () => runAction(document.querySelector("#repoSyncNowButton"), () => {
      const message = document.querySelector("#repoCommitMessage")?.value.trim() || "更新可可助手资料";
      return jsonRequest("/api/git/sync", { message });
    }));
    document.querySelector("#repoExportLocalButton")?.addEventListener("click", async () => {
      const summary = document.querySelector("#repoSyncSummary");
      try {
        summary.textContent = "正在整理本浏览器的维护资料…";
        const backup = await exportBrowserData();
        downloadJson(backup, "keke-admin-local-data.json");
        summary.textContent = `备份已导出：${Object.keys(backup.character_recommendations).length} 名角色推荐、${Object.keys(backup.team_overrides.edits || {}).length} 条阵容编辑、${backup.drive_layouts.length} 张摆放图。用户持有角色等个人设置不会导出。`;
      } catch (error) { summary.textContent = error.message; }
    });
    document.querySelector("#repoImportFile")?.addEventListener("change", async event => {
      const file = event.target.files?.[0];
      const summary = document.querySelector("#repoSyncSummary");
      if (!file) return;
      try {
        if (file.size > 32 * 1024 * 1024) throw new Error("备份文件不能超过 32 MB");
        const incoming = JSON.parse(await file.text());
        if (!incoming || typeof incoming !== "object" || Array.isArray(incoming)) throw new Error("备份根节点必须是 JSON 对象");
        const current = await exportBrowserData();
        const backup = mergeBrowserBackups(current, incoming);
        const recCount = Object.keys(backup.character_recommendations || {}).length;
        const teamCount = Object.keys(backup.team_overrides?.edits || {}).length;
        const imageCount = (backup.drive_layouts || []).length;
        if (!window.confirm(`将当前浏览器维护数据与所选备份合并到项目：${recCount} 名角色推荐、${teamCount} 条阵容编辑、${imageCount} 张摆放图。同编号冲突以所选备份为准；仅在写入成功后清理已迁移的本地维护覆盖，用户持有角色等个人设置不会清理。项目文件会先备份到本机应用数据目录。继续吗？`)) return;
        summary.textContent = "正在校验并导入…";
        const result = await jsonRequest("/api/migrate", backup);
        localStorage.removeItem("keke-role-recommendations-v2");
        localStorage.removeItem("keke-role-basics-v1");
        localStorage.removeItem("keke-guide-lineups-v1");
        await window.KekeDriveLayoutStore?.clearExported?.((backup.drive_layouts || []).map(item => item?.id).filter(Boolean));
        summary.textContent = result.message + " 已迁移本浏览器维护覆盖；源备份文件与旧 file:// 浏览器数据均保留。刷新页面后载入导入资料。";
        document.querySelector("#repoReloadNote")?.removeAttribute("hidden");
      } catch (error) { summary.textContent = `导入未完成，源备份仍保留：${error.message}`; }
      finally { event.target.value = ""; }
    });
  }

  const bridge = {
    ready,
    get connected() { return connected; },
    waitForWrites: () => Promise.all([...pendingWrites]),
    getStatus,
    mergeBrowserBackups,
    saveTeamOverrides: overrides => jsonRequest("/api/teams", { overrides }),
    saveCharacterBasics: (id, patch) => jsonRequest("/api/characters/basic", { id, patch }),
    saveCharacter: async (id, patch, recommended) => {
      await ready;
      if (!canSaveCharacter) throw new Error("管理程序版本过旧，不支持完整保存。请关闭旧程序并打开新版管理EXE；本机编辑缓存已保留。");
      return jsonRequest("/api/characters/save", { id, patch, recommended });
    },
    saveCharacterRecommendations: recommendations => jsonRequest("/api/characters/recommendations", { recommendations }),
    uploadDriveLayout: async (id, file) => {
      return request(`/api/characters/layout?id=${encodeURIComponent(id)}`, {
        method: "POST", headers: { "Content-Type": file.type }, body: file
      });
    },
    deleteDriveLayout: id => jsonRequest("/api/characters/layout/delete", { id }),
    persistTeamOverrides: async () => {
      if (!window.teamGuideStore?.overrides) return false;
      await bridge.saveTeamOverrides(window.teamGuideStore.overrides());
      window.teamGuideStore.clearLegacy?.();
      return true;
    },
    persistCharacterRecommendations: async () => {
      const recommendations = window.CharacterRecommendations?.export?.() || {};
      await bridge.saveCharacterRecommendations(recommendations);
      window.characterOverrides ||= { schema_version: "1.0.0", characters: {} };
      window.characterOverrides.characters ||= {};
      for (const record of Object.values(window.characterOverrides.characters)) delete record.recommended;
      for (const [id, value] of Object.entries(recommendations)) {
        window.characterOverrides.characters[id] ||= {};
        window.characterOverrides.characters[id].recommended = value;
      }
      window.CharacterRecommendations?.clearLegacy?.();
      return true;
    },
    bindDialog
  };
  return bridge;
})();
