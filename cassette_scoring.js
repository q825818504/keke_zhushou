/* Shared air-curtain recommendation scoring used by maintenance previews and the user build page. */
window.KekeCassetteScoring = (() => {
  const PRIORITY_WEIGHTS = Object.freeze({ 0: 0, 1: 0.4, 2: 0.55, 3: 0.7, 4: 0.85, 5: 1 });
  const MAIN_POINTS = 60;
  const SUB_POINTS = 40;
  const SUB_SLOT_COUNT = 4;
  // B/A/S gear values are 0.6/0.8/1.0 of the gold (S) baseline across
  // cartridge main/sub stats and module sub stats. Module shape scales the
  // absolute value, but does not change the ratio between rarities.
  const QUALITY_MULTIPLIERS = Object.freeze({ gold: 1, purple: 0.8, blue: 0.6 });
  const ELEMENT_NAMES = ["光", "暗", "灵", "咒", "魂", "相"];

  function rawName(value) {
    if (typeof value === "string") return value;
    return value?.name || value?.names?.zh_cn || value?.names?.zh_CN || value?.id || "";
  }

  function canonicalAffix(value) {
    const raw = rawName(value).trim();
    if (!raw) return "";
    const compact = raw.replace(/[\s\u3000]/g, "");
    const isPercent = typeof value === "object" && (value.is_percent === true || value.percent === true);
    const percentNamed = /百分比|[%％]/.test(compact);
    for (const base of ["攻击力", "生命值", "防御力"]) {
      if (compact.startsWith(base)) {
        if (percentNamed || isPercent) return base + "百分比";
        return base;
      }
    }
    if (compact.includes("暴击率")) return "暴击率";
    if (compact.includes("暴击伤害")) return "暴击伤害";
    if (compact.includes("环合强度")) return "环合强度";
    if (compact.includes("倾陷强度")) return "倾陷强度";
    if (compact.includes("通用伤害增强") || compact.includes("全伤害增强") || compact.includes("全伤害加成")) return "通用伤害增强";
    if (compact.includes("元素伤害加成")) return "元素伤害加成";
    return compact
      .replace(/百分比/g, "百分比")
      .replace(/[（()）]/g, "")
      .replace(/[%％]/g, "");
  }

  function expandPoolAffix(value) {
    const raw = rawName(value).replace(/[\s\u3000]/g, "");
    if (!raw) return [];
    for (const base of ["攻击力", "生命值", "防御力"]) {
      if (raw.startsWith(base) && /固定值/.test(raw) && /[%％]/.test(raw)) {
        return [base + "百分比", base];
      }
      if (raw.startsWith(base) && /固定值/.test(raw)) return [base];
      if (raw.startsWith(base) && /[%％]|百分比/.test(raw)) return [base + "百分比"];
    }
    if (/元素伤害[（(].*[光灵咒暗魂相]/.test(raw)) return ELEMENT_NAMES.map(name => name + "属性异能伤害增强");
    return [canonicalAffix(value)].filter(Boolean);
  }

  function priorityValue(value) {
    const priority = Math.round(Number(value) || 0);
    return priority >= 1 && priority <= 5 ? priority : 0;
  }

  function weightForPriority(priority) {
    return PRIORITY_WEIGHTS[priorityValue(priority)] || 0;
  }

  function qualityTier(item) {
    const value = String(item?.rarity ?? item?.quality ?? "").trim().toLowerCase();
    if (/^(?:s|5|s-rank|s-class|orange|gold|golden|legendary|金|橙)$/.test(value) || /(?:orange|gold|legendary|金|橙)/.test(value)) return "gold";
    if (/^(?:a|4|a-rank|a-class|purple|pink|epic|紫)$/.test(value) || /(?:purple|pink|epic|紫)/.test(value)) return "purple";
    if (/^(?:b|3|b-rank|b-class|blue|rare|蓝)$/.test(value) || /(?:blue|rare|蓝)/.test(value)) return "blue";
    // Older snapshots may not contain rarity; keep them comparable to the
    // historical score, which is now the gold baseline.
    return "gold";
  }

  function qualityMultiplier(item) {
    return QUALITY_MULTIPLIERS[qualityTier(item)];
  }

  function recommendationMap(cassette, kind) {
    const items = cassette?.["recommended_" + kind + "_affixes"];
    const result = new Map();
    for (const item of Array.isArray(items) ? items : []) {
      const name = canonicalAffix(item);
      if (name) result.set(name, priorityValue(item.priority));
    }
    return result;
  }

  function poolItems(pool) {
    if (Array.isArray(pool)) return pool;
    if (Array.isArray(pool?.items)) return pool.items;
    return [];
  }

  function legalSubAffixes(cassette, catalogCassette) {
    const pool = poolItems(catalogCassette?.sub_affix_pool).length
      ? poolItems(catalogCassette.sub_affix_pool)
      : poolItems(cassette?.sub_affix_pool);
    if (pool.length) return [...new Set(pool.flatMap(expandPoolAffix).filter(Boolean))];
    return [...recommendationMap(cassette, "sub").keys()];
  }

  function attributePriority(attribute, priorities) {
    const name = canonicalAffix(attribute);
    return { name, priority: priorities.get(name) || 0 };
  }

  function scoreItem(item, cassette, catalogCassette) {
    const mainPriorities = recommendationMap(cassette, "main");
    const subPriorities = recommendationMap(cassette, "sub");
    const mainAttribute = (item?.main_stats || item?.main_attributes || [])[0] || null;
    const main = attributePriority(mainAttribute, mainPriorities);
    const mainWeight = weightForPriority(main.priority);
    const subAttributes = (item?.sub_stats || item?.sub_attributes || [])
      .map(attribute => attributePriority(attribute, subPriorities));
    const subWeight = subAttributes.reduce((sum, attribute) => sum + weightForPriority(attribute.priority), 0);
    const idealSubWeight = legalSubAffixes(cassette, catalogCassette)
      .map(name => subPriorities.get(name) || 0)
      .sort((a, b) => b - a)
      .slice(0, SUB_SLOT_COUNT)
      .reduce((sum, priority) => sum + weightForPriority(priority), 0);
    const tier = qualityTier(item), multiplier = QUALITY_MULTIPLIERS[tier];
    const baseMainPoints = MAIN_POINTS * mainWeight;
    const baseSubPoints = idealSubWeight > 0 ? Math.min(SUB_POINTS, SUB_POINTS * subWeight / idealSubWeight) : 0;
    const mainPoints = baseMainPoints * multiplier;
    const subPoints = baseSubPoints * multiplier;
    return {
      item,
      quality: tier,
      qualityMultiplier: multiplier,
      mainName: rawName(mainAttribute),
      mainPriority: main.priority,
      mainWeight,
      mainPoints,
      mainEligible: main.priority > 0,
      subAttributes,
      subWeight,
      idealSubWeight,
      baseMainPoints,
      baseSubPoints,
      subPoints,
      score: mainPoints + subPoints
    };
  }

  function byScore(a, b) {
    return b.score - a.score || b.mainPoints - a.mainPoints || b.subPoints - a.subPoints;
  }

  // Attribute identity, not random-roll size or enhancement level, determines fit.
  function scoreDrive(item, cassette, catalogDrive) {
    const priorities = recommendationMap(cassette, "sub");
    const pool = Object.values(catalogDrive?.qualities || {}).find(row => row.random_stats?.length)?.random_stats;
    if (!priorities.size || !pool?.length || !(item?.sub_stats || item?.sub_attributes)?.length) return null;
    const legal = new Set(pool.map(canonicalAffix));
    const seen = new Set();
    const attributes = (item.sub_stats || item.sub_attributes).slice(0, SUB_SLOT_COUNT).map(attribute => {
      const row = attributePriority(attribute, priorities);
      const weight = legal.has(row.name) && !seen.has(row.name) ? weightForPriority(row.priority) : 0;
      seen.add(row.name);
      return { ...row, weight };
    });
    const ideal = [...legal].map(name => weightForPriority(priorities.get(name))).sort((a,b) => b-a).slice(0,SUB_SLOT_COUNT).reduce((a,b) => a+b,0);
    if (ideal <= 0) return null;
    const tier = qualityTier(item), multiplier = QUALITY_MULTIPLIERS[tier];
    const baseScore = Math.min(100, 100 * attributes.reduce((sum,row) => sum+row.weight,0) / ideal);
    return { quality: tier, qualityMultiplier: multiplier, baseScore, score: baseScore * multiplier, attributes };
  }

  function grade(value) {
    if (!Number.isFinite(value)) return null;
    return value >= 95 ? "ACE" : value >= 85 ? "S" : value >= 70 ? "A" : value >= 50 ? "B" : "C";
  }

  function scoreLoadout(tapeScore, drives, board) {
    const active = new Set((board || []).map(([r,c]) => `${r}:${c}`)), used = new Set();
    if (!active.size || !Number.isFinite(tapeScore)) return null;
    let driveScore = 0;
    for (const { item, score } of drives) {
      if (!Number.isFinite(score) || !item.placement || !item.cells?.length) return null;
      for (const [r,c] of item.cells) {
        const key = `${r+item.placement.row}:${c+item.placement.column}`;
        if (!active.has(key) || used.has(key)) return null;
        used.add(key);
      }
      driveScore += score * item.cells.length / active.size;
    }
    const total = tapeScore + driveScore;
    return { tapeScore, driveScore, total, graduation: total / 2, grade: grade(total/2), filled: used.size, capacity: active.size };
  }

  function rank(items, cassette, catalogCassette) {
    const scored = (Array.isArray(items) ? items : [])
      .filter(item => item?.category === "tape")
      .map((item, index) => ({ ...scoreItem(item, cassette, catalogCassette), index }));
    const hasRecommendedMain = scored.some(entry => entry.mainEligible);
    const primary = scored.filter(entry => hasRecommendedMain ? entry.mainEligible : true).sort(byScore);
    const fallback = hasRecommendedMain ? scored.filter(entry => !entry.mainEligible).sort(byScore) : [];
    return { candidates: primary, fallback, fallbackMode: !hasRecommendedMain, total: scored.length };
  }

  return {
    PRIORITY_WEIGHTS,
    MAIN_POINTS,
    SUB_POINTS,
    SUB_SLOT_COUNT,
    QUALITY_MULTIPLIERS,
    canonicalAffix,
    weightForPriority,
    qualityTier,
    qualityMultiplier,
    scoreItem,
    scoreDrive,
    scoreLoadout,
    grade,
    rank
  };
})();
