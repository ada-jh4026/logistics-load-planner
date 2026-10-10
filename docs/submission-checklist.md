# 提交清单

截止：英国时间 2026-10-12 11:00（北京时间 18:00）。内部冻结 07:30，正式提交 09:30。

## 冻结前（功能）
- [x] 主线已采纳增量费用修正，重跑三套基准并更新 README 实验表（见 `docs/results.md`）。
- [x] 主线 I02：21 条实验记录齐全，`docs/results.md` 有表格与原始文件对应。
- [x] F06：3 分钟演示脚本 `docs/demo-script.md` 已按新功能更新；关键截图在 `artifacts/demo/`（含 repair/、ui/）。录屏未制作。
- [ ] README 团队信息、队名补齐（当前为占位；官方要求 README 介绍团队，简历才是可选项）。

## 冻结后（只修阻断）
- [x] 干净目录复现（2026-10-11 02:20，本方）：`git clone` 1c5adc6 → `pip install -r requirements-dev.txt -r agent/requirements.txt` → `pytest tests agent/tests` 248 passed → `npm ci && npm run build` 通过。三服务与浏览器流程在工作目录已验（F05/F07/O04/UI-polish 证据）。
- [x] GPT 只读审查（2026-10-10 晚，基准 d9b7ebc）：阻断 B3、重要 I1–I7、I9、建议 S1–S5 由本方修复（`artifacts/evidence/review-fixes.md`）；**B1/B2（独立校验器漏检）归主线，探针在 `artifacts/probes/validator_tamper_probe.py`，待主线修复后重跑 `pytest tests` 并在此勾选**。
- [ ] 主线修复 B1/B2 后：`.venv/Scripts/python.exe -X utf8 artifacts/probes/validator_tamper_probe.py` 8/8 CAUGHT；README「独立校验器重算全部约束和指标」的说法届时成立。
- [x] 仓库内无凭据（2026-10-11 复核）：`git grep` 无匹配；`agent/.env` 未被跟踪。
- [x] 模拟数据、手工样例、人工环节在 README「数据来源」一节标注。
- [x] 第三方组件与许可在 README「外部依赖」一节列出。
- [ ] `docs/playbook/board.json` 状态与实际一致，不把未完成标 done。

## 提交（用户执行）
- [ ] GitHub 私有仓库 `ada-c38f0bb79f/logistics-load-planner` 邀请官方账号 **DsChHack** 为 Collaborator（仓主 ada-c38f0bb79f 操作：Settings → Collaborators → Add people）。
- [ ] 确认 DsChHack **已接受**邀请（仓库 Settings → Collaborators 里显示为成员，而不是 Pending invite）。pending 不等于评审方能访问；若截止前仍 pending，在提交渠道备注并保留邀请，评审期间不要撤销。
- [ ] 团队知悉官方「参赛后提交作品的知识产权归主办方所有」条款（赛题原文合规要求一节），确认后再提交。
- [ ] 通过赛事指定渠道提交仓库链接 `https://github.com/ada-c38f0bb79f/logistics-load-planner`。
- [ ] 若有网盘附件：链接有效期覆盖评审期，提取码写进 README。
- [ ] 提交后在 `docs/playbook/STATE.md` 记录提交时间与渠道。
