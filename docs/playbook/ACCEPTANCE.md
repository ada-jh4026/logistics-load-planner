# 验收案例与精确预期
这些是要实现的测试规格，尚未执行。测试应使用构造数据及手算预期，不从被测函数生成“正确答案”。

## C01 正常配送与等待
使用examples/request-success.json。距离(0,0)到(3,4)=5km，速度30km/h，出发480，抵达490，门店窗口500..600，服务5分钟；开始500，离开505，回仓515。往返10km，费用100+2×10=120元。
两箱共150kg，总体积2,000,000,000mm³；车厢4,000,000,000mm³，500kg容量。体积利用率0.5、载重利用率0.3。
成功样例将B01放(1000,0,0)，B02放(1000,0,1000)，B02为易碎箱，先卸B02再B01合法。算法无须复制此布局，只需最终校验通过。
测试文件：test_routing.py、test_geometry.py、test_metrics.py、test_pipeline.py。

## C02 总体积够但单件尺寸不合
车厢2000×1000×2000mm；一箱2100×500×500，允许水平旋转。体积足够，但0度长超限、90度宽超限。必须未分配，BOX_TOO_LARGE。用它测试不能仅看体积。
反例：1900×500×500同条件应能放入。
测试文件：test_packing.py、test_pipeline.py。

## C03 时间窗无法到达
仓库(0,0)、出发480、门店(30,0)，速度30，最早到540，窗口490..500。该门店未分配，TIME_WINDOW。
边界：窗口结束540时准时；539.999时不合格（考虑统一1e-6容差）。等待与service_start口径用C01验证。
测试文件：test_routing.py。

## C04 易碎和承托
车高2000，A/B均1000立方，A在(0,0,0)，B在(0,0,1000)。
A.fragile=true时拒绝FRAGILE_LOAD；设false后可承托。B改为(500,0,1000)，底面超出A则UNSUPPORTED；B.z改为1100则浮空也UNSUPPORTED。
边界：B底面恰等于A顶面合法；碰撞是严格正交集，接触不报OVERLAP。
测试文件：test_geometry.py。

## C05 卸货阻挡
车长3000、宽1000、高1000，两箱均1000立方。先送店S1的A放x=2000，后送S2的B放x=0，y/z均0。按S1→S2时A的取出路径被B挡住，UNLOAD_BLOCKED。
交换箱位置后顺序不变应通过；或交换路线且时间窗许可也可通过。
测试文件：test_unloading.py。

## C06 堆叠抽底
A=(0,0,0)，B=(0,0,1000)，大小1000立方，A非易碎。即使A向门口的水平路径空，也不允许先抽A，因B在其顶上；报SUPPORT_DEPENDENCY。同站先B后A合法；A属早站、B属晚站则该路线不可执行。
测试文件：test_unloading.py。

## C07 车辆不足与门店原子性
仅一车容量100kg，S1两箱各30kg，S2一箱60kg，空间和时间均宽裕。最多服务一店；剩余整店进入unassigned。S1不可拆成一箱配送、一箱未分配。有效计划不能超载，不能伪报100%完成。
测试文件：test_validation.py、test_pipeline.py。

## C08 数据错误
重复箱ID、未知store_id、负尺寸、NaN/Infinity、反向时间窗、不合法options。HTTP422且不创建任务；不能生成零尺寸箱继续求解。
测试文件：test_models.py、test_api.py。

## C09 方案完整性及指标篡改
正常候选中复制同箱、漏掉一箱、同车重复出现、route门店不含对应箱门店、伪造total_cost=1；分别触发BOX_DUPLICATE、BOX_MISSING、VEHICLE_REUSED、STORE_SPLIT或STEP_MISMATCH、METRIC_MISMATCH。
校验器必须独立重算，不能信任validation.valid字段。
测试文件：test_validation.py、test_metrics.py。

## C10 协同修复回归
构造两种车型：小车2000×1000×1000、载重500、固定费10；大车3000×1500×1500、载重1000、固定费100；相同里程费。某店单箱2500×500×500，允许旋转，两车总体积预筛均可，小车实际几何不合，大车可以。路线策略可能优先小车；coupled应识别失败并尝试剩余大车。
基线若已预筛单件尺寸自动选大车，就不要删正确预筛来制造优势；改用多箱空间/卸货冲突的通用回归，保留C10作为正向可行性测试。先保存输入与失败候选，再验证有真实修复动作，禁止case_id特殊逻辑。
即使修复得到的费用更高，也应准确报告“从不可执行到可执行”，不能写降本。
测试文件：test_coupled.py。

## C11 超时、预算和可复现
在solver可注入的单调时钟上构造预算耗尽，检查终止原因time_limit；已验证可行快照保留，未配送明确列出，无可行快照时全部unassigned。别通过长时间sleep实现单元测试。
相同seed、固定迭代数及足够预算结果应相同（不比较run_id/elapsed_ms）。不同输入不能返回同一固定布局。
测试文件：test_budget.py、test_pipeline.py。

## C12 前端状态与坐标
固定请求配套成功/部分/失败响应都可展示；部分情况有未配送列表；failed不保留上次成功的数字冒充新结果。
B02箱底z=1000，三维位置要加半个箱高后转成渲染中心。若Three.js采用Y轴向上，使用业务(x,y,z)→场景(x,z,y)并统一单位mm→m；箱体中心和车门方向同样转换。
通过截图与实际交互确认：车辆切换、路线顺序、箱体高亮、逐步卸货、错误提示、mock标记、刷新后重新提交。
验收文件：artifacts/evidence/F03.md、F04.md、F05.md。

## C13 指令解释与受控补丁（智能体）
以 examples/request-partial.json 为输入。
- 「S01 最早 9 点半收货」→ patch 仅含 `/stores/0/window_start_min`=570；其余字段逐一相等。
- 「V01 今天不出车」→ 因只剩一辆车，操作进入 rejected_ops（至少保留一辆），patched_request 等于原请求，understood=true。
- 「把 B03 标为易碎」→ `/boxes/2/fragile`=true。
- 「S01 最晚 8 点收货」→ 导致 window_end 480 < window_start 500，校验失败进入 rejected_ops。
- 「把 B01 长度改成 500」→ 字段不在白名单，rejected_ops，不生成 patch。
- 「S99 改时间窗」→ 未知 ID，understood=false，patch=[]。
- 「时间预算 20 秒」→ `/options/time_limit_ms`=20000。
以上在模板（规则）模式下必须全部通过；模型模式用 FakeLLM 注入 intent_ops 验证解析、白名单与校验链路相同。
测试文件：agent/tests/test_interpret.py。

## C14 解释证据绑定（智能体）
以 examples/response-partial.json 为输入，FactSheet 必含：total_cost 120、volume_utilization 0.5、S02 未分配且 reason_code=BOX_TOO_LARGE、V01 到 S01 等待 10 分钟（490→500）。
- FakeLLM 输出「总费用 120 元，利用率 50%，S01 等待 10 分钟」→ grounding.passed=true，mode=llm。
- FakeLLM 输出「总费用 150 元」→ unmatched 含 150，重试一次仍错则 mode=template，warnings 非空，text 为模板文本。
- FakeLLM 抛异常或超时 → mode=template，HTTP 200。
- response.status=failed → HTTP 422。
测试文件：agent/tests/test_grounding.py、agent/tests/test_explain_llm.py。

