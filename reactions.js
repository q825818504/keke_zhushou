/* Read-only reaction reference, backed by the locally preserved source guide. */
const reactionKnowledge = window.esperCycleKnowledge || { cycles: [], source: {} };
let reactionSearch = "";
let reactionElement = "all";
const reactionOpenIds = new Set();

function showReactionSystem() {
  if (guideDirty && !guideCanLeave()) return;
  guideDirty = false;
  document.body.classList.remove("user-mode");
  ["userExperienceView", "roleManagementView", "encyclopediaView", "guideManagerView"].forEach(id => { document.getElementById(id).hidden = true; });
  document.getElementById("reactionSystemView").hidden = false;
  showAdminToolbar();
  setText("#activeBreadcrumb", "反应体系");
  $$("[data-nav]").forEach(el => el.classList.toggle("is-active", el.dataset.nav === "反应体系"));
  $("#encyclopediaNavTrigger")?.classList.remove("is-active");
  $$("[data-encyclopedia-kind]").forEach(el => el.classList.remove("is-active"));
  renderReactionSystem();
}
function reactionBadge(attribute) {
  return '<span class="reaction-element"><img src="' + escapeHtml(attribute.image.local_path) + '" alt="">' + escapeHtml(attribute.name) + '</span>';
}
function renderReactionCards() {
  const terms = reactionSearch.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const cycles = reactionKnowledge.cycles.filter(cycle => {
    const text = [cycle.name, cycle.description, ...cycle.attributes.map(a => a.name), ...cycle.enhancements.map(e => e.character_name + " " + e.description)].join(" ").toLowerCase();
    return (reactionElement === "all" || cycle.attributes.some(a => a.name === reactionElement)) && terms.every(term => text.includes(term));
  });
  $("#reactionResultCount").textContent = cycles.length + " / " + reactionKnowledge.cycles.length + " 种环合";
  $("#reactionCards").innerHTML = cycles.map(cycle => {
    const passives = cycle.enhancements.map(e => '<article class="reaction-passive"><img src="' + escapeHtml(e.image.local_path) + '" alt="" loading="lazy"><div><h4>' + escapeHtml(e.character_name) + '<span>' + escapeHtml(e.label) + '</span></h4><p>' + escapeHtml(e.description) + '</p></div></article>').join("");
    return '<details class="reaction-card" data-reaction-id="' + escapeHtml(cycle.id) + '"' + (reactionOpenIds.has(cycle.id) ? " open" : "") + '><summary><span class="reaction-chevron" aria-hidden="true">›</span><div class="reaction-summary-title"><h2>' + escapeHtml(cycle.name) + '</h2><small>' + (cycle.attributes.length === 3 ? "三属性环合" : "双属性环合") + (cycle.enhancements.length ? " · " + cycle.enhancements.length + " 条强化被动" : "") + '</small></div><div class="reaction-elements">' + cycle.attributes.map(reactionBadge).join("") + '</div></summary><div class="reaction-content"><div class="reaction-base"><h3>基础效果</h3><p>' + escapeHtml(cycle.description) + '</p></div>' + (passives ? '<div class="reaction-passives"><h3>' + escapeHtml(cycle.enhancement_heading) + '</h3><div class="reaction-passive-grid">' + passives + '</div></div>' : "") + '</div></details>';
  }).join("") || '<div class="reaction-empty"><h2>没有匹配的环合</h2><p>试试角色名、反应名称或效果中的关键词。</p></div>';
  $$("#reactionCards details").forEach(details => details.addEventListener("toggle", () => {
    if (details.open) reactionOpenIds.add(details.dataset.reactionId);
    else reactionOpenIds.delete(details.dataset.reactionId);
  }));
}
function renderReactionSystem() {
  const root = $("#reactionSystemView");
  const source = reactionKnowledge.source;
  const attributes = Array.from(new Map(reactionKnowledge.cycles.flatMap(c => c.attributes).map(a => [a.name, a])).values());
  const passiveCount = reactionKnowledge.cycles.reduce((count, c) => count + c.enhancements.length, 0);
  root.innerHTML = '<div class="reaction-heading"><div><span class="user-section-kicker">玩法资料 · 异能环合</span><h1>' + escapeHtml(reactionKnowledge.title || "异能环合") + '</h1><p>' + escapeHtml(reactionKnowledge.subtitle || "") + '</p></div><span class="reaction-count-pill">' + reactionKnowledge.cycles.length + ' 种环合 · ' + passiveCount + ' 条强化被动</span></div>' +
    '<section class="reaction-system-note"><h2>' + escapeHtml(reactionKnowledge.system_heading || "系统说明") + '</h2><p>' + escapeHtml(reactionKnowledge.system_description || "") + '</p></section>' +
    '<section class="reaction-controls" aria-label="筛选环合"><div class="reaction-search"><input type="search" id="reactionSearch" placeholder="搜索环合、角色或效果…" aria-label="搜索环合、角色或效果" value="' + escapeHtml(reactionSearch) + '"></div><div class="reaction-filter-buttons" role="group" aria-label="按属性筛选"><button type="button" data-reaction-element="all"' + (reactionElement === "all" ? ' aria-pressed="true"' : ' aria-pressed="false"') + '>全部</button>' + attributes.map(a => '<button type="button" data-reaction-element="' + escapeHtml(a.name) + '" aria-pressed="' + (reactionElement === a.name) + '">' + reactionBadge(a) + '</button>').join("") + '</div></section>' +
    '<div class="reaction-list-toolbar"><span id="reactionResultCount" role="status"></span><div><button type="button" class="ghost-button" data-reaction-expand>全部展开</button><button type="button" class="ghost-button" data-reaction-collapse>全部收起</button></div></div><div id="reactionCards" class="reaction-cards"></div>' +
    '<footer class="reaction-attribution">资料整理自 <a href="' + escapeHtml(source.source_url || "") + '" target="_blank" rel="noreferrer">环世全鉴 · 异能环合</a>，作者 ' + escapeHtml(source.author || "") + '。许可：<a href="' + escapeHtml(source.license_url || "") + '" target="_blank" rel="noreferrer">' + escapeHtml(source.license || "") + '</a>。本地整理保留原文、数值与图片，调整展示和分类。<br>来源采集日期：' + escapeHtml(source.captured_at ? new Date(source.captured_at).toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai" }) : "") + ' · 非官方攻略资料。</footer>';
  renderReactionCards();
}
function bindReactionSystem() {
  const root = $("#reactionSystemView");
  root.addEventListener("input", event => {
    if (event.target.id !== "reactionSearch") return;
    reactionSearch = event.target.value;
    renderReactionCards();
  });
  root.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.reactionElement) {
      reactionElement = button.dataset.reactionElement;
      $$("[data-reaction-element]", root).forEach(el => el.setAttribute("aria-pressed", String(el.dataset.reactionElement === reactionElement)));
      renderReactionCards();
    }
    if ("reactionExpand" in button.dataset || "reactionCollapse" in button.dataset) {
      const open = "reactionExpand" in button.dataset;
      $$("#reactionCards details").forEach(el => {
        el.open = open;
        if (open) reactionOpenIds.add(el.dataset.reactionId);
        else reactionOpenIds.delete(el.dataset.reactionId);
      });
    }
  });
}
