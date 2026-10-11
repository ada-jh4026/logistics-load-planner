# 只读审查（GPT，2026-10-10 晚，基准 d9b7ebc）后的修复记录

执行者：前端/智能体线（Claude Code）。审查报告由队友侧模型在临时克隆上只读完成，逐条先复现再改；每条一个提交。后端两条（B1/B2）不在本方目录，转为探针交主线。

## 处理一览

| 编号 | 审查结论 | 复现 | 处理 | 提交 |
|---|---|---|---|---|
| B1 / B2 | 独立校验器：placements + unload_steps 同时清空、里程 / 费用改写、时刻清零、stops 顺序错位均不报违规 | 复现：`artifacts/probes/validator_tamper_probe.py` 8 条篡改 5 条 LEAK（其中 B2d 在单站 c01 上并未真正换序，主线改为 small-11 多站） | 归主线：探针 + 修法建议写在 `artifacts/probes/README.md` 探针 3；**主线已于 d95c251 修复**（`artifacts/evidence/H02.md`），本方 2026-10-11 在干净克隆复跑探针 8/8 CAUGHT、205 份历史结果复审通过 | 2ad0589 → d95c251 |
| B3 | 数字核对可被绕过：紧邻中文的数字、中文数字、万 / 亿倍率、推算合计、借用全局总费用描述单车 | 复现：FakeLLM 注入五句均 `passed=true` | `agent/grounding.py` 重写提取与匹配范围（见下）；README / limitations / architecture / AGENT_CONTRACT / 页面提示改口径 | b6978a0 |
| I1 | 快照回放混用：KPI / 指标 / 校验 / 未配送是最终方案，车辆栏和 3D 是快照，路线图非选中车是最终路线 | 复现：geometry-22 修复前快照 KPI 仍 2 店 146 元、车辆栏 0 辆 | 整个工作台改读事件的 routes + metrics；未配送按快照路线推导；校验格改说明；横幅加关闭 | 5eb1002 |
| I2 | 演示脚本点 V01（未启用）；旁白数字来自 small-11；引用仓库外脚本 | 复现：standard-11 移除 V02 为 0.0% | 脚本按今晚 standard-11 真实运行重写：V02；「V02 和 V04 今天都不出车」+2.5% | c1a277a |
| I3 | 规则模式静默遗漏越权子句；坐标修改无结构化拒绝 | 复现：「把 S01 的坐标改成 999，同时 V01 今天不出车」只移除 V01 | 未识别子句入 warnings 与 summary；坐标类生成 `set store.x_km` 被白名单拒绝；两模式通用的实体覆盖检查；模型提示第 6 条 | bb0aa82、3f3a986 |
| I4 | 「近似线性」「远未触及预算」未覆盖混合箱件；架构文档耗时表与 README 不一致 | 核实：混合 stress 13.6–18.2 s，基线出现 time_limit | README 第 8 节与 architecture 改为分数据集、带机器与预算的耗时表；线性改为待验证假设 | （docs 提交） |
| I5 | 「覆盖相同」低估混合组优势；留出集「不是过拟合」过强；+9% 应为约 10% | 核实：standard-11-mixed-1 +9.87%；stress 60/60 对 32–36/60 | README 5.3 / 第 7 节、limitations 按实验组分别陈述 | （docs 提交） |
| I6 | 全天时间窗显示 00:00–00:00 | 复现：geometry-22 行程表 | `windowText`：[0,1440] 显示「全天」，1440 显示 24:00；作业单、智能体模板、指令摘要一致 | 5eb1002、0ca6a06 |
| I7 | 「不含坐标」只对结构化输入成立，自由文本原样进提示 | 核实 | README「模型与数据安全」、architecture 职责表、limitations 如实写明，并写明真实数据阶段的内网要求 | （docs 提交） |
| I8 | 团队表占位 | 核实 | 待用户提供（提交清单保留未勾选） | — |
| I9 | 资源、成本、维护责任说明不足 | 实测：求解服务常驻 39 MB、混合 stress 峰值 100 MB；智能体 81 MB；提示 7–36 千字符 | README 第 8 节新增「资源与成本」，实测与估算分开标注 | （docs 提交） |
| S1 | Git Bash 下 `.venv\Scripts\python.exe` 报错；macOS 无 `copy` | 复现 | README 第 3 节分 Windows / POSIX 两组命令，注明工作目录 | （docs 提交） |
| S2 | Node 下限过宽；建议 `npm ci` | 核实：Vite 8.3.4 要求 ^20.19 ‖ ≥22.12 | README 写明 Node 下限与实测版本、`npm ci`、锁定文件位置 | （docs 提交） |
| S3 | 主包 1342 kB | 核实 | CargoView 懒加载：主包 394 kB（gzip 120 kB），Three.js 950 kB 分包 | 4261229 |
| S4 | 1366×768 顶栏换行、KPI 截断 | 复现：2 格 KPI 说明 clipped | ≤1400 px 紧凑布局；复测 5 格均不截断、顶栏单行 | 4261229 |
| S5 | README 测试数 162/49 过时、AGENT_CONTRACT 路径、limitations「无过渡动画」、START_HERE「O04 待办」 | 核实 | README 185/72 与路径修正、limitations 修正；`START_HERE.md` 属主线文档，已告知 | （docs 提交） |

审查中「评审访问」一项：提交清单已把「pending」与「已接受」区分，并加入知识产权条款知悉项。

## B3 的具体改动与验证

`agent/grounding.py`：
- 数字边界由 `(?<![\w.:])` 改为只排除 ASCII 字母数字，紧邻中文的数字（「费用99999元」「启用5辆车」）也提取；
- 新增 `cn_to_number`：「九万九千九百九十九」「一千二」「两」「百分之七十」先换算再核对；换算不了记未匹配；「一处」「第一站」「下一站」视为量词 / 序数不计入；
- 「万 / 亿」倍率：「751.6 万公里」按 7,516,000 km 核对，不再按 751.6 匹配；
- 子句（按。；，换行切分）只提到一个已知车辆 / 门店 ID 时，元 / km / kg / 分钟 / 百分数 / 时刻只在该实体的事实（车辆行、它的到站、它的卸货）里找，不借用全局合计；件数类单位仍允许退回全局；
- 「2003.2 + 2003.2 = 4006.4 元」这类推算合计：4006.4 不在任何事实里，记未匹配。

验证：
```
.venv/Scripts/python.exe -X utf8 -m pytest -q agent/tests      → 72 passed（新增 6 条 B3 回归 + 3 条 I3 回归）
_tools/probe_grounding.py（审查五句）                          → 全部 unmatched 非空；13 句正常表述全部通过
_tools/probe_grounding_regress.py                              → 24 组模板文本（4 案例 × 4 focus + 2 手工样例 × 4）0 未匹配
真实 DeepSeek：standard-11 overview / vehicle / unload，geometry-22 overview / unassigned → 全部 mode=llm，passed=true
```
一处回归：geometry-22 总览里模型写「V01 送 1 家门店」，「家」原只映射 store 路径，车辆事实里是 `stop_count` → 首轮被拦、重试仍拦、回退模板。把「家」同时映射到 stop 后通过（24 个数字）。模板文本「另有 N 次采用未逐条列出」在 stress 混合案例里 N=37 不在事实表内，改为引用 `accepted_count`。

## I1 的验证（浏览器自动化 `_tools/shot_snapshot.mjs`，未入库）

geometry-22 真实求解 → 采用事件 → 「查看修复前布局」：

| 区域 | 修复前快照 | 修复后快照 | 关闭快照 |
|---|---|---|---|
| KPI | 0 / 2 店，0 辆，0 元，独立校验格「快照」 | 2 / 2 店，2 辆，146 元，「快照」 | 2 / 2 店，2 辆，146 元，「通过」 |
| 车辆栏 | 0 / 2 辆启用；未配送 S01、S02（无原因码） | 2 / 2；所有门店已安排 | 同最终 |
| 路线图 | 无连线；S01、S02 标未配送 | V01：S02，V02：S01 | 同最终 |
| 侧栏 | 「部分配送 · 修复事件 2 的修复前快照」；校验段改说明 | 「全部配送 · 修复后快照」 | 校验明细恢复 |

截图：`artifacts/demo/repair/10-snapshot-before-unified.png`、`11-snapshot-before-map.png`。历史记录五种状态与三法对比、作业单回归脚本均通过，控制台无错误。

## 收尾复核（2026-10-11 18:00 英国时间，合并主线 1c11e1c 后）

- 干净克隆 `1c11e1c`：新建 venv → `pip install` → `pip check` 无冲突 → `pytest tests agent/tests` 275 passed → 探针 8/8 CAUGHT → `npm ci && npm run build` 通过。
- 本地三服务重启到合并后代码：small-11 / standard-11 / stress-44 / geometry-22 / time-geometry-22 / c02 / c07 求解全部通过新校验器；浏览器流程（standard-11 指令确认重算、geometry-22 快照回放）复跑通过。

## 未做

- 团队信息中本方成员一栏（用户本人填写）与队名。
- 录屏。
