# 提交清单

截止：英国时间 2026-10-12 11:00（北京时间 18:00）。内部冻结 07:30，正式提交 09:30。

## 冻结前（功能）
- [x] 主线已采纳增量费用修正，重跑三套基准并更新 README 实验表（见 `docs/results.md`）。
- [x] 主线 I02：21 条实验记录齐全，`docs/results.md` 有表格与原始文件对应。
- [x] F06：3 分钟演示脚本 `docs/demo-script.md` 已按新功能更新；关键截图在 `artifacts/demo/`（含 repair/、ui/）。录屏未制作。
- [x] README 团队信息：两名成员简介已补（2026-10-11）。
- [ ] 队名待确认（登记问卷「团队名字」一项需要）。

## 冻结后（只修阻断）
- [x] 干净目录复现（2026-10-11 02:20，本方）：`git clone` 1c5adc6 → `pip install -r requirements-dev.txt -r agent/requirements.txt` → `pytest tests agent/tests` 248 passed → `npm ci && npm run build` 通过。三服务与浏览器流程在工作目录已验（F05/F07/O04/UI-polish 证据）。
- [x] GPT 只读审查（2026-10-10 晚，基准 d9b7ebc）：阻断 B3、重要 I1–I7、I9、建议 S1–S5 由本方修复（`artifacts/evidence/review-fixes.md`）；**B1/B2（独立校验器漏检）归主线，探针在 `artifacts/probes/validator_tamper_probe.py`，已于d95c251修复并复跑，见下项**。
- [x] 2026-10-11 主线修复 B1/B2：8/8 有效篡改 CAUGHT；修正原单站换序探针无实际变动的问题。275 项测试、前端构建通过；205 份历史实验输出重新校验通过。见 `artifacts/evidence/H02.md`，修复已提交d95c251，本轮授权推送GitHub。
- [x] 仓库内无凭据（2026-10-11 复核）：`git grep` 无匹配；`agent/.env` 未被跟踪。
- [x] 模拟数据、手工样例、人工环节在 README「数据来源」一节标注。
- [x] 第三方组件与许可在 README「外部依赖」一节列出。
- [x] `docs/playbook/board.json` 补齐 H01、O04、H02，I04技术验收done；外部资料、访问和赛事提交仍待办。
- [x] d95c251独立克隆、新环境275测试、8/8探针、前端安装/构建与三服务浏览器流程通过；见I04.md。附加改动仅成员简介、文档与截图。

## 提交（用户执行）
- [ ] GitHub 私有仓库 `ada-c38f0bb79f/logistics-load-planner` 邀请官方账号 **DsChHack** 为 Collaborator（仓主 ada-c38f0bb79f 操作：Settings → Collaborators → Add people）。
- [ ] 确认 DsChHack **已接受**邀请（仓库 Settings → Collaborators 里显示为成员，而不是 Pending invite）。pending 不等于评审方能访问；若截止前仍 pending，在提交渠道备注并保留邀请，评审期间不要撤销。
- [ ] 团队知悉官方「参赛后提交作品的知识产权归主办方所有」条款（赛题原文合规要求一节），确认后再提交。
- [ ] 通过https://v.wjx.cn/vm/rmEuv50.aspx提交仓库链接（本轮按用户要求暂不提交） `https://github.com/ada-c38f0bb79f/logistics-load-planner`。
- [ ] 若有网盘附件：链接有效期覆盖评审期，提取码写进 README。
- [ ] 提交后在 `docs/playbook/STATE.md` 记录提交时间与渠道。
