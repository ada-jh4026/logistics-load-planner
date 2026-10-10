# 前端 · 配载工作台

城市配送智能配载的调度员工作台：选择案例、运行求解、查看车辆路线、按真实坐标查看 3D 装载、逐步播放卸货、查看未配送原因与指标，以及（F07）与调度助手对话。

## 技术栈
Vite 8 · React 19 · TypeScript 6 · Three.js（@react-three/fiber + drei）· zod。字体 Barlow / Barlow Condensed 由 `@fontsource` 自托管，不依赖外网字体服务。

## 运行
```bash
cd frontend
npm install
npm run dev      # http://127.0.0.1:5173
npm run build    # 产物在 frontend/dist
```
开发服务器把 `/api/*` 代理到求解器 `127.0.0.1:8000`，`/agent/*` 代理到智能体 `127.0.0.1:8001`（见 `vite.config.ts`）。两者未启动时页面仍可用样例数据演示。

## 数据来源
- 协议类型与运行时校验：`src/protocol/contract.ts`，与 `docs/playbook/CONTRACT.md` v0.1 一一对应。
- 演示样例直接引用 `docs/playbook/examples/*.json`（`src/lib/mock.ts`），响应 `is_mock=true`，页面顶栏显示「演示数据」标记。这些是手工构造的界面样例，不是算法结果。

## 坐标约定
业务坐标：后门 x=0，x 向车头，y 沿车宽，z 向上，单位 mm，位置为箱件最小角。
场景坐标：Three.js Y 轴向上，单位 m。转换只在 `src/lib/geometry.ts` 一处完成：业务 (x, y, z) → 场景 (x, z, y) / 1000，中心 = 最小角 + 半尺寸；旋转 90° 交换长宽。

## 着色
箱件按「到站顺序」着色，≤8 站使用固定顺序分类色（已用色彩校验脚本验证通过），>8 站退化为单色深浅序列。易碎箱用红色描边。后门用码头黄黑斜纹标记。

## 目录
```
src/
  protocol/contract.ts   协议 schema 与类型
  lib/mock.ts            样例加载
  lib/geometry.ts        坐标与尺寸转换
  lib/derive.ts          请求/响应索引与中文文案
  lib/palette.ts         着色规则
  lib/format.ts          时刻/百分数/数字格式
  components/            顶栏、车辆栏、3D 车厢、路线图、卸货步骤、右侧详情
  App.tsx                状态与布局
```
