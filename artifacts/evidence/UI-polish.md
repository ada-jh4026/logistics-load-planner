# 前端易用性四项 —— 验收证据

日期：2026-10-11（英国时间 01:40）。执行者：前端/智能体线（Claude Code）。四项各一个提交：`f17aeda` KPI 行、`3525c48` 卸货动画、`3e9cf8c` 三法对比、`7951368` 作业单。

## 1. KPI 行（`KpiRow.tsx`）
中央视图上方五格：配送门店（含完成率与箱数）、启用车辆（含体积/载重利用率）、总费用（含里程）、准时率（含卸货阻挡）、独立校验。只读响应 `metrics` 与 `validation`，不计算新值；颜色只在「独立校验」与「部分配送」两处承担含义。截图 `artifacts/demo/ui/kpi-row_standard-11.png`。

## 2. 卸货动画（`CargoView.tsx`）
已卸箱件沿 −x 从后门滑出车厢约 0.45 m 并淡至 12% 透明，速度由帧间隔插值；`prefers-reduced-motion` 时直接跳到终态。材质常驻 transparent、动画只改 opacity 与 depthWrite。画布开启 `preserveDrawingBuffer` 供作业单截图。截图 `unload-animation_small-11.png`（两步后 B022 已滑出车外淡化）。

## 3. 对比三种方法（`useMethodCompare.ts`、`MethodCompare.tsx`）
顶栏按钮；同一请求依次以 greedy / sequential / coupled 提交求解（串行，不占队列），不在前端重算指标。表格并排：门店、车辆、费用、里程、体积利用率、独立校验、协同修复状态、耗时；每列「查看」切换页面展示的方案；完成后默认展示协同。费用改善率只在服务门店集合相同且均通过校验时计算，否则写明不可比原因。实测 small-11：贪心 912.3 / 顺序 869.2 / 协同 869.2 元，协同相对贪心 −4.7%、相对顺序 0.0%，协同修复「未触发」。截图 `method-compare_small-11.png`。

## 4. 现场装卸作业单（`worksheet.ts`）
卸货步骤条「打印作业单」→ 新窗口 A4：配送顺序（到达、时间窗、卸箱数）、作业规则、卸货顺序表（步、门店、箱件、尺寸、重量、易碎、最小角坐标、完成勾选）、装货顺序表（卸货逆序，距后门/离左壁/离地）、签字栏、3D 车厢截图。全部字段来自响应与请求，不推算。实测 V02（small-11）：17 行卸货、17 行装货、截图嵌入成功。截图 `worksheet_V02_small-11.png`。

## 实际命令
```
cd frontend && npx tsc -b && npm run build                 → exit 0（每个提交各跑一次）
node _tools/shot_compare_ws.mjs http://127.0.0.1:5173/ …    → 对比表、动画、作业单弹窗均通过，控制台无错误
```

## 发现并修复
- `window.open` 带 `noopener` 时拿不到窗口引用，`document.write` 写入空白；改为 Blob URL 打开。
- 对比表三列中文表头在 336 px 侧栏里换行成四行；改为「贪心 / 顺序 / 协同」短标签，完整名放 title 与结论行。

## 限制
- 作业单用浏览器打印对话框，未生成 PDF 文件。
- 三法对比每次重新提交三个任务，不缓存。
