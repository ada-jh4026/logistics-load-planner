# 数据与接口协议 v0.1
本文件是字段的唯一依据。examples目录给出完整UI示例，非求解或性能证据。

## 输入 SolveRequest
- schema_version: 固定"0.1"。
- case_id: 非空字符串。
- data_source: 固定"synthetic"；后续真实数据需显式修订使用流程。
- depot: {id:"DEPOT", x_km:number, y_km:number, departure_min:number}。
- stores: 数组，每项{id, x_km, y_km, window_start_min, window_end_min, service_min}。
- vehicles: 数组，每项{id, length_mm, width_mm, height_mm, max_weight_kg, fixed_cost, cost_per_km}，每项是一辆真实可用车，不能重复使用。
- boxes: 数组，每项{id, store_id, length_mm, width_mm, height_mm, weight_kg, fragile:boolean, allow_rotate_xy:boolean}。
- options: {method:"greedy"|"sequential"|"coupled", seed:整数, time_limit_ms:整数, max_iterations:整数, speed_kmph:正数}。
- 默认options：coupled、42、10000、200、30。时间预算允许100..60000ms；迭代1..10000。
- 不接受重复ID、非法门店引用、非有限数、非正尺寸/重量/载重/速度、负费用或服务时间、颠倒时间窗。每个门店至少一箱；stores、vehicles、boxes均非空。出发/窗口时间在0..1440内。
- 输入非法属于HTTP 422，返回{schema_version:"0.1", error:{code:"INVALID_INPUT",message,details:[{path,message}]}}，不创建任务。
- JSON以UTF-8读写；不得用truthy判断吞掉有效0值。

## 网络模型和时效
distance(a,b)=sqrt((xa-xb)^2+(ya-yb)^2)，分钟=distance/speed_kmph*60，不提前四舍五入。
第一站arrival=departure+travel；service_start=max(arrival,window_start)；departure=service_start+service_min。service_start<=window_end才合格。第二站从上一站departure计算；回仓计里程与时间，不另设回仓截止。
UI可四舍五入，内部保留精度。所有门店和仓库之间均可直达，这是模拟假设。

## API
1. GET /api/health → {status:"ok",schema_version:"0.1"}。
2. GET /api/examples → [{case_id,label,description}]，列表来自实际存在的data/cases/*.json。
3. GET /api/examples/{case_id} → SolveRequest；未知ID为404。
4. POST /api/solve，body=SolveRequest → HTTP202，{schema_version:"0.1",run_id,status:"queued"}。
5. GET /api/jobs/{run_id} → JobResponse；未知ID为404。

## JobResponse
- schema_version、run_id、case_id：字符串。
- status: queued | running | succeeded | partial | failed。
- data_source: synthetic；is_mock:boolean；实际服务返回false，文档UI样例true。
- method: greedy | sequential | coupled。
- termination_reason: null | completed | time_limit | iteration_limit | internal_error。
- elapsed_ms: 非负数；queued可为0。
- result: null或Result，queued/running/failed为null。
- error: null或{code,message}；failed为INTERNAL_ERROR。后端详细堆栈写本地日志，页面不显示凭据或堆栈。
- succeeded要求全部门店被服务且验证通过；partial要求已服务部分通过验证，未服务明确列出。零门店服务也用partial；没有空车路线。
- time_limit可以与succeeded同时出现：已找到全覆盖可行解但没完成改善搜索。不要把超时自动当异常。
- 内存任务重启会丢失，404页面提示重新提交。

## Result
routes: 每辆被使用的车一项：
- vehicle_id, store_ids:配送顺序；
- stops:[{store_id,arrival_min,service_start_min,departure_min}]；
- return_min,distance_km,cost；
- box_ids:本车所有箱件；
- placements:[{box_id,x_mm,y_mm,z_mm,rotation_xy:0|90}]，旋转后尺寸从输入计算，禁止另造矛盾尺寸；
- unload_steps:[{step:1起连续整数,store_id,box_id}]，必须与store_ids顺序一致并逐件通过校验。

unassigned:[{store_id,box_ids,reason_code,message}]。门店原子分配，全箱都在该项。不允许同箱在routes和unassigned同时出现，不允许缺失。
reason_code取BOX_TOO_LARGE、CAPACITY_LIMIT、TIME_WINDOW、SEARCH_EXHAUSTED、TIME_LIMIT；只有能确证的原因才使用前三种，否则SEARCH_EXHAUSTED。

validation:{valid:boolean,violations:[{code,vehicle_id:null或string,box_ids:[],store_id:null或string,message}]}。
返回可执行result的valid必须为true；诊断失败放diagnostics而非冒充可执行方案。

metrics:{
total_stores,served_stores,total_boxes,served_boxes,completion_rate,
used_vehicles,total_distance_km,total_cost,on_time_rate,
volume_utilization,weight_utilization,unload_block_count
}。
指标定义见EVALUATION。空配送时利用率和准时率为null，成本/里程/车辆数为0。
diagnostics:[{iteration,action,reason_code,message}]；诊断文本描述实际发生的尝试，不输出虚构修复过程。
以上字段全部必需；没有内容时使用空数组/null，不任意省略。

## 错误码
输入：INVALID_INPUT。
校验：BOX_DUPLICATE、BOX_MISSING、STORE_SPLIT、VEHICLE_REUSED、OUT_OF_BOUNDS、OVERLAP、OVERWEIGHT、UNSUPPORTED、FRAGILE_LOAD、TIME_WINDOW、UNLOAD_BLOCKED、SUPPORT_DEPENDENCY、STEP_MISMATCH、METRIC_MISMATCH。
服务：INTERNAL_ERROR、NOT_FOUND、QUEUE_FULL。HTTP404/429使用与422相同的错误外壳，details为空数组，code分别为NOT_FOUND/QUEUE_FULL。新错误码先登记后使用。

## 调用与轮询
前端POST一次后每500ms轮询；任务结束立即停止。重复点击禁用，不每次轮询重发POST。网络错误保留用户输入并允许重新查询；约75秒未结束提示查看服务状态。后端限制排队数量（默认8），超限返回HTTP429和明确消息。


## 关联协议
调度助手智能体服务的接口见 AGENT_CONTRACT.md；它只消费本协议的 SolveRequest / JobResponse，不新增、不修改本协议字段。
