# 调度助手智能体服务

在求解器之上的独立服务：把真实求解结果解释给调度员听、把自然语言指令变成受控的请求补丁、比较两次方案。模型不做调度决策；它只输出解释与补丁，补丁需人确认后再提交求解器。接口见 [AGENT_CONTRACT.md](../docs/playbook/AGENT_CONTRACT.md)，原则见 DECISIONS.md D08。

## 运行
```bash
# 仓库根目录。依赖装进根目录 .venv（与后端共用）
uv venv .venv --python 3.12            # 已有则跳过
uv pip install --python .venv/Scripts/python.exe -r agent/requirements.txt
.venv/Scripts/python.exe -m uvicorn agent.app:app --host 127.0.0.1 --port 8001
```
测试：
```bash
.venv/Scripts/python.exe -m pytest -q agent/tests
```

## 模型配置
复制 `agent/.env.example` 为 `agent/.env`，填入 `DEEPSEEK_API_KEY`。不填也能跑：所有接口进入模板模式（`mode="template"`），核心流程不中断。任何 OpenAI 兼容接口都可替换（`DEEPSEEK_BASE_URL`、`AGENT_MODEL`），便于对接企业私有化部署的模型。`agent/.env` 已被 .gitignore 排除。

## 可信机制
- 事实表：`facts.py` 从请求与响应确定性推导，单车利用率、载重、等待与松弛时间都按请求重算；模型只看事实表，不看坐标。
- 数字核对：`grounding.py` 提取回答中的数字、百分数、时刻，逐个在事实表中匹配；带单位的数字只在同类事实里找。首轮不通过带提示重试一次，仍不通过回退模板，`warnings` 写明未匹配数字。
- 回退：无密钥、超时、异常、输出不合格都回退模板，HTTP 不返回 5xx。

## 目录
```
agent/
  app.py          FastAPI 入口与错误外壳
  schemas.py      CONTRACT v0.1 镜像 + Agent 接口模型
  facts.py        事实表推导
  grounding.py    数字核对
  templates.py    模板模式文本
  llm.py          OpenAI 兼容客户端、NullLLM、FakeLLM
  explain.py      解释生成（模型 + 核对 | 模板）
  tests/          pytest，不依赖网络
```
