# 提交清单

截止：英国时间 2026-10-12 11:00（北京时间 18:00）。内部冻结 07:30，正式提交 09:30。

## 冻结前（功能）
- [x] 主线已采纳增量费用修正，重跑三套基准并更新 README 实验表（见 `docs/results.md`）。
- [x] 主线 I02：21 条实验记录齐全，`docs/results.md` 有表格与原始文件对应。
- [ ] F06：3 分钟演示脚本 `docs/demo-script.md` 走通一遍；录屏或关键截图在 `artifacts/demo/`。
- [ ] README 团队信息、队名补齐（当前为占位）。

## 冻结后（只修阻断）
- [ ] 干净目录复现：`git clone` → 按 README 安装 → `pytest` 后端 + 智能体 → `npm run build` → 启动三服务 → 浏览器跑 standard-11 与 c02。
- [ ] 仓库内无凭据：`git grep -nE "sk-[A-Za-z0-9]{10,}|DEEPSEEK_API_KEY=.+"` 为空；`agent/.env` 未被跟踪。
- [ ] 模拟数据、手工样例、人工环节在 README「数据来源」一节标注。
- [ ] 第三方组件与许可在 README「外部依赖」一节列出。
- [ ] `docs/playbook/board.json` 状态与实际一致，不把未完成标 done。

## 提交（用户执行）
- [ ] GitHub 私有仓库 `ada-c38f0bb79f/logistics-load-planner` 邀请官方账号 **DsChHack** 为 Collaborator（仓主 ada-c38f0bb79f 操作：Settings → Collaborators → Add people）。
- [ ] 确认 DsChHack 已接受邀请或邀请处于 pending（评审期间保持）。
- [ ] 通过赛事指定渠道提交仓库链接 `https://github.com/ada-c38f0bb79f/logistics-load-planner`。
- [ ] 若有网盘附件：链接有效期覆盖评审期，提取码写进 README。
- [ ] 提交后在 `docs/playbook/STATE.md` 记录提交时间与渠道。
