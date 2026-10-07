/* Explicit role recommendations, layered over the unchanged imported defaults. */
window.CharacterRecommendations = (() => {
  const key = "keke-role-recommendations-v2";
  const clone = value => JSON.parse(JSON.stringify(value));
  const originals = window.characterKnowledge || {};
  let saved = {};
  for (const [id, override] of Object.entries(window.characterOverrides?.characters || {})) {
    if (override?.recommended && typeof override.recommended === "object") saved[id] = clone(override.recommended);
  }
  let hasLegacy = false;
  try {
    const legacyText = localStorage.getItem(key);
    const value = JSON.parse(legacyText || "{}");
    hasLegacy = Boolean(legacyText);
    if (value && typeof value === "object" && !Array.isArray(value)) saved = { ...saved, ...value };
  } catch (_) { /* Imported defaults remain available. */ }
  function createKnowledge(original) {
    const recommended = clone(original.recommended || {});
    const override = saved[original.id];
    for (const kind of ["weapon", "cassette"]) {
      const item = override?.[kind];
      if (item && typeof item.id === "string" && typeof item.name === "string") recommended[kind] = clone(item);
    }
    if (override?.terminal_puzzle) recommended.terminal_puzzle = clone(override.terminal_puzzle);
    const terminalOverride = window.characterOverrides?.characters?.[original.id]?.terminal;
    const terminal = terminalOverride && typeof terminalOverride === "object"
      ? { ...(original.terminal || {}), ...clone(terminalOverride) }
      : original.terminal;
    if (terminal && recommended.cassette) recommended.cassette.terminal = clone(terminal);
    return { ...original, terminal, recommended };
  }
  function select(knowledge, kind, id) {
    if (knowledge.recommended?.[kind]?.id === id) return;
    const original = originals[knowledge.id]?.recommended?.[kind];
    if (original?.id === id) {
      knowledge.recommended[kind] = clone(original);
      return;
    }
    const catalog = kind === "weapon" ? window.arcDriveKnowledge : window.skyCurtainKnowledge;
    const item = catalog.items.find(item => item.id === id);
    if (!item) return;
    if (kind === "weapon") {
      knowledge.recommended.weapon = { id: item.id, name: item.name, rating: item.rarity, asset: item.image?.local_path || "" };
      return;
    }
    const template = Object.values(originals).map(character => character.recommended?.cassette).find(cassette => cassette?.id === id);
    const previous = knowledge.recommended.cassette || {};
    const pool = value => Array.isArray(value) ? value : value?.items || [];
    const main = pool(item.main_affix_pool), sub = pool(item.sub_affix_pool);
    knowledge.recommended.cassette = {
      ...clone(template || {}), id: item.id, name: item.name, category: item.category,
      cassette_type: "空幕卡带", element: (item.element || "").replace(/属性$/, ""),
      icon: item.images?.gold?.local_path || item.images?.purple?.local_path || item.images?.blue?.local_path || "",
      acquisition: item.acquisition || "", main_affix_pool: main, sub_affix_pool: sub,
      set_effects: [{ pieces: 2, description: item.set_effects?.two_piece || "" }, { pieces: 4, description: item.set_effects?.four_piece || "" }].filter(effect => effect.description),
      recommended_main_affixes: clone(previous.recommended_main_affixes || []),
      recommended_sub_affixes: clone(previous.recommended_sub_affixes || [])
    };
  }
  function save(knowledge) {
    const next = { ...saved, [knowledge.id]: clone(knowledge.recommended || {}) };
    try { localStorage.setItem(key, JSON.stringify(next)); saved = next; return true; }
    catch (_) { return false; }
  }
  function reset(knowledge) {
    const next = { ...saved }; delete next[knowledge.id];
    try { localStorage.setItem(key, JSON.stringify(next)); saved = next; }
    catch (_) { return false; }
    knowledge.recommended = clone(originals[knowledge.id]?.recommended || {});
    return true;
  }
  function exportOverrides() { return clone(saved); }
  function clearLegacy() { localStorage.removeItem(key); hasLegacy = false; }
  function clearPersistedCharacter(id) {
    const pending = JSON.parse(localStorage.getItem(key) || "{}");
    delete pending[id];
    if (Object.keys(pending).length) localStorage.setItem(key, JSON.stringify(pending));
    else localStorage.removeItem(key);
    hasLegacy = Object.keys(pending).length > 0;
  }
  function hasLegacyOverrides() { return hasLegacy; }
  return { createKnowledge, select, save, reset, export: exportOverrides, clearLegacy, clearPersistedCharacter, hasLegacy: hasLegacyOverrides };
})();
