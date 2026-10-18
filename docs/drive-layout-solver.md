# 驱动布局计算模块

`drive_layout_solver.js` 是独立纯计算模块，可在浏览器使用 `window.DriveLayoutSolver`，也可在 Node 中 `require('./drive_layout_solver.js')`。它不读取 DOM、角色图鉴、仓库存储或网络。

`terminal_puzzle.js` 负责把角色终端/推荐空幕转成请求，以及绘图、套装状态。`terminal_editor.js` 只处理编辑交互。现有“按所选型号重排”在不同最优形状组合间循环，不增加 UI 板块。

## 两层候选

- **形状组合**：每种固定朝向形状需要几块。例如两个Ⅱ横，与一个Ⅱ横加一个Ⅱ竖，是不同组合；这层直接影响玩家库存能否满足。`rankBy: 'score_first'` 会先比较所有组合的实际装备评分，再以填充格数、终端偏好和块数破同分。
- **坐标摆法**：同一形状组合可能有多种摆放位置。库存评分相同时可视为等价参考；需要坐标变体时单独枚举，不用大量位置变化挤占形状组合候选。

`generateCandidates()` 默认每种形状组合只保留一套合法坐标，按 `profileKey` 去重。`placementsFor()` 可以为指定形状组合枚举不同坐标。

## 输入与调用

```js
const result = DriveLayoutSolver.generateCandidates({
  terminal,                      // layout.rows/columns/active_slots，坐标从1开始
  required: [                    // 空幕四种必需形状，必须全部满足
    { shape_id: 'cell2_style1_1', count: 1 },
    { shape_id: 'cell3_style5_1', count: 1 },
    { shape_id: 'cell3_style4_1', count: 1 },
    { shape_id: 'cell4_style2_1', count: 1 }
  ],
  preferredModel: 3,
  allowPartial: false,            // 必须铺满；true允许在完整套装前提下留空
  inventoryCounts: {             // 可选；提供后，未列出的形状视为0库存
    cell2_style1_1: 1,
    cell2_style2_1: 1,
    cell3_style3_1: 2,
    cell3_style4_1: 1,
    cell3_style5_1: 1,
    cell4_style2_1: 1
  },
  limit: 64,
  maxNodes: 500000,
  layoutsPerProfile: 1
});
```

省略库存表示不限制库存的攻略参考，不表示玩家已经持有。提供空库存则无可行解。固定朝向有独立 `shape_id`，横竖及 L/Z 的方向不能互相代替。

实际实例可以替代或同时限制形状数量：

```js
const result = DriveLayoutSolver.generateCandidates({
  terminal, required, preferredModel: 3,
  inventory: [
    { uid: 'drive-001', shape_id: 'cell2_style1_1', stats: { crit_rate: 0.08, atk_ratio: 0.12 } },
    // 其余实际驱动……
  ],
  excludedUids: ['已被另一角色方案占用的UID'],
  weights: { crit_rate: 5, atk_ratio: 2 },
  rankBy: 'passive_first',
  allowPartial: false
});
```

`stats` 必须先由调用方统一属性名称和数值单位，例如8%输入0.08。内置评分只是 `Σ weight × stat` 的可替换线性评分，不等于完整伤害计算，也不会自行判断“毕业”。需要更准确的角色收益时提供 `scoreItem(item)` 回调。

同一形状下按实例得分选择所需数量，每块实例 UID 只能使用一次。缺少属性按0处理；传入数据格式、未知形状、重复UID、非有限数值等会抛出 `TypeError`。`fixed` 可带合法坐标块；如含 `inventory_uid`，该实例也被固定，不能被更高分驱动替换。

## 排序与结果

完整套装形状是硬约束。默认排序为填充格数、优先型号块数、装备评分、较少块数。`rankBy: 'equipment_first'` 将装备评分放在优先型号数量之前，但不会放宽套装或库存约束。是否允许留空由 `allowPartial` 明确控制。

每个候选包含：

- `shape_counts` / `profileKey`：库存所需形状数量与稳定组合身份。
- `plan`：坐标、D编号、优先型号；有实际库存时包含 `inventory_uid`。
- `metrics`：实际填充格数、优先型号数量、装备得分与块数。
- `placementKey`：忽略D编号后的坐标身份。

总体结果包含 `status`、`searchComplete`、`truncated`、`rankingComplete`、`optimalityProven` 和搜索节点数。`status` 为 `ok`、`infeasible` 或 `budget_exhausted`。预算耗尽不能解释为无解。候选数截断或坐标枚举截断会明确标记；`searchComplete` 只针对声明的 `scope`，默认是形状组合，不表示枚举了所有坐标摆法。`score_first` 在完整计算了所有库存形状组合分数后，按分数降序检查摆放合法性；找到首个可行组合即能证明最高分，坐标差异不会改变其装备分数。

候选排序只有在 `rankingComplete` 为 true 时才能确认为整个已定义搜索范围内的最佳排序。未完成的结果仍可以提供已验证可行的候选，但不得宣称全局最优。

## 接入边界

当前已接入管理端参考重排，未增加玩家仓库 UI，也未接入真实账号库存。后续仓库适配层负责冻结账号、仓库版本、权重版本及排除UID，向本模块提供实例，并在返回时核对版本后才能保存。多角色分配由外层协调各角色实例占用；本模块支持通过 `excludedUids` 排除已占用实例，但不会将贪心逐角色选择宣称为全队最优。

验证：`node scripts/check_drive_layout_solver.cjs`。当前本地终端槽位＋失落光芒＋Ⅲ型优先，包含11种最优形状组合；同时验证Ⅱ横/Ⅱ竖库存差异、权重实例选择、固定/排除UID、坐标变体和预算耗尽。
