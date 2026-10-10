# 演示素材

按 `docs/demo-script.md` 顺序的关键截图（真实求解器 + 真实 DeepSeek，headless Chrome 自动化生成，未人工修图）：

1. `F07_1-solved.png`：small-11 求解完成，3D 车厢与卸货步骤。
2. `F07_2-explained.png`：调度助手「总览」解释，核对 12 个数字。
3. `F07_3-interpreted.png`：指令「V02 今天不出车」解析为字段级 diff，等待确认。
4. `F07_4-compared.png`：确认重算后的自动对比（2 → 2 车，869.2 → 919.2 元，费用可比 +5.8%，如实显示上升）。
5. `F05_c02_unassigned_real.png`：单件尺寸超过车厢，门店未配送并给出原因。
6. `F05_standard-11_map_real.png`：30 店 12 车路线示意。

7. `flow-standard-11/1-solved.png … 4-compared.png`：`docs/demo-script.md` 当前版本对应的 standard-11 流程（2026-10-10 晚）：5 车 2,003.2 元 → 总览核对 11 个数字 → 「V02 和 V04 今天都不出车」→ 5 车 2,053.2 元，费用可比 +2.5%。
8. `repair/10-snapshot-before-unified.png`、`11-snapshot-before-map.png`：geometry-22 修复前快照，KPI / 车辆栏 / 未配送 / 路线图与 3D 同源。
9. `ui/1366x768_standard-11.png`：1366 × 768 下的布局验收。

录屏未制作；如需视频，按脚本人工录制后放本目录（.mp4 已在 .gitignore 中，需走网盘链接）。
