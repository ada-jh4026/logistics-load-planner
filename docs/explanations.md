# 解释与执行指引说明

本模块（backend/explanations.py）从求解器的真实 `Result` 生成确定性的文本解释，
供前端展示或作为共享模板，不新增 HTTP 字段。

## 数据来源（全部来自真实结果，不编造）

- **总体**：`metrics.served_stores/total_stores`、`served_boxes/total_boxes`、
  `total_cost`、`total_distance_km`、`volume_utilization`、`weight_utilization`。
- **逐车**：`routes[].vehicle_id/store_ids/cost/distance_km`，及车辆尺寸/载重（来自 request）。
- **未配送**：`unassigned[].store_id/box_ids/reason_code/message`。
- **装货指引**：`routes[].unload_steps` 的逆序（装货 = 卸货逆序，见 ALGORITHMS A3）。

## 约束

- 只陈述事实，不声称「降本/节省」——成本改善率须由 B15 实验在相同服务集合上对比得出。
- 没有实际修复日志（diagnostics）就不声称发生过修复。
- 几何装载是保守启发式，不保证最优；「未找到布局」不代表数学不可行（DECISIONS D06）。

## 模型限制

- 单仓、单日、每车一趟；箱形货物、固定时间窗；不建模实时路况、多仓、异形物体、材质承重。
- 自然语言改规则 / 智能体助手由 agent 线（A01–A04）负责，本模块仅做规则化文本说明。
