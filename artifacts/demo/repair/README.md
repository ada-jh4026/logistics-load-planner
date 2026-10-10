# 协同修复面板演示截图（O04）

均为 headless Chrome 自动化（`_tools/shot_repair.mjs`）对真实数据的截图，未修图。

| 文件 | 内容 | 数据来源 |
|---|---|---|
| `O04_1-not-needed.png` | 无需修复：初始已全可执行，0 尝试 | `artifacts/benchmarks/hetero-before-20261010/runs/hetero-long-2/coupled` |
| `O04_2-unresolved.png` | 未解决：发现冲突但无候选通过 | `hetero-development-before-20261010/runs/hetero-dev-6/coupled`（H01 前） |
| `O04_3-budget-exhausted.png` | 预算退出：12 次尝试 0 采用 | `hetero-mixed-before-20261010/runs/standard-11-mixed-2/coupled`（H01 前） |
| `O04_4-partial-truncated.png` | 部分修复 + 日志截断：0 → 8/10 店，省略 27 条被拒记录 | `hetero-mixed-before-20261010/runs/small-11-mixed-1/coupled`（H01 前） |
| `O04_5-repaired.png` | 修复成功：5 → 10/10 店，12 次尝试 5 次采用 | `hetero-mixed-after-20261010/runs/small-11-mixed-2/coupled`（H01 后） |
| `O04_6/7-snapshot-*.png` | 选中接受事件 6，切换修复前（V04 空车）/ 修复后（V04 装入 S10）快照；3D 只读后端快照 | 同上 |
| `O04_8-live-geometry-22.png` | 当前服务实时求解 geometry-22：0 → 2/2 店，1 次采用 | `POST /api/solve` |
| `O04_9-live-explain.png` | 助手总览（DeepSeek，核对 24 个数字）末尾如实转述修复：检测 1 处冲突、采用 1 次、0 → 2 店 | `/agent/explain` |
