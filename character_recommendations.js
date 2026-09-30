/* Explicit role recommendations, layered over the unchanged imported defaults. */
window.CharacterRecommendations = (() => {
  const key = "keke-role-recommendations-v2";
  const clone = value => JSON.parse(JSON.stringify(value));
  const originals = window.characterKnowledge || {};
  let saved = {};
  try {
    const value = JSON.parse(localStorage.getItem(key) || "{}");
    if (value && typeof value === "object" && !Array.isArray(value)) saved = value;
  } catch (_) { /* Imported defaults remain available. */ }
  function createKnowledge(original) {
    const recommended = clone(original.recommended || {});
    const override = saved[original.id];
    for (const kind of ["weapon", "cassette"]) {
      const item = override?.[kind];
      if (item && typeof item.id === "string" && typeof item.name === "string") recommended[kind] = clone(item);
    }
    return { ...original, recommended };
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
      recommended_main_affixes: clone((previous.recommended_main_affixes || []).filter(affix => main.includes(affix.name))),
      recommended_sub_affixes: clone((previous.recommended_sub_affixes || []).filter(affix => sub.includes(affix.name)))
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
  return { createKnowledge, select, save, reset };
})();
