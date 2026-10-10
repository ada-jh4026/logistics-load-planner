# 实验与指标
## 固定公式
completion_rate=served_stores/total_stores。served_boxes另报，不能用箱件完成率替换门店完成率。
on_time_rate=已服务且service_start<=window_end的门店数/served_stores；零服务为null。
total_distance_km=所有已服务路线“仓库→各店→仓库”距离之和。
total_cost=各已用车fixed_cost+cost_per_km*该车距离之和。
volume_utilization=已服务箱总体积/已用车总体积；weight_utilization=已服务箱总重量/已用车总载重。零使用车辆时两者null；不得把未使用车辆计入分母。
unload_block_count=对最终执行计划模拟卸货的阻挡数；有效计划为0。失败候选的阻挡另入diagnostics，不能混进最终指标。
体积利用率不等于空间最优性；几何限制可能导致低利用率仍是当前可行解。

## 对照设计
小规模10店/约40箱、标准30店/约120箱，各seed为11、22、33；压力案例60店/约240箱，seed44。实际生成箱数写入结果。
所有数据生成一次后落盘，三个方法读取同一文件；默认每方法每案例10秒，压力案例30秒。每组保存方法、seed、配置、数据哈希、系统/依赖版本、终止原因、有效性及所有指标。
小/标准共18条运行记录，压力3条，共21条，全部保留失败与超时。性能只描述记录机器上的结果。
费用改善率=(基线费用-本方案费用)/基线费用，仅在相同已服务门店集合、均验证通过、基线费用>0时计算；否则null并说明不可比。不能仅检查完成率相同。
分别比较greedy与coupled、sequential与coupled。不同完成率先报告覆盖变化，不给降本百分比。
表格展示单例与汇总范围，不只摘最佳样例。真实企业收益列为待验证目标。

## 证据保存
artifacts/benchmarks/<run_stamp>/：
manifest.json、runs.csv、summary.json、每次request.json/response.json/validation.json、日志。
UI示例is_mock=true不能进入实验数据。脚本发现mock响应应立即拒绝计分。
任务B14/I02实现这些命令，当前不存在：
python -m scripts.benchmark --suite standard --output artifacts/benchmarks/latest
python -m scripts.benchmark --suite stress --output artifacts/benchmarks/stress

## 智能体评估（不计入 21 条求解对比记录）
- 指令解释准确率：agent/tests/data/instructions.jsonl（≥10 条，含应拒绝与应澄清的样例）。规则模式逐条断言；模型模式用 agent/scripts/eval_interpret.py 统计「patched_request 与期望完全一致」的比例，保存到 artifacts/evidence/A03_eval.json，附模型名、温度、日期。
- 解释数字核对通过率：对实验中每个真实响应调用 explain(overview)，统计首轮 grounding.passed 比例与回退比例；首轮不通过的样例原文保留。
- 延迟：记录每次模型调用耗时的中位数与最大值；模板模式耗时另记。
- 口径：模型输出的任何业务收益表述都不是实验结论；README 中引用智能体文本须标注 mode。

