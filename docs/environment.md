# 环境记录

更新时间：2026-10-10（B01 完成时填写）

## 已确认版本

| 组件 | 版本 | 来源命令 |
| --- | --- | --- |
| Python | 3.14.8 | `python --version` |
| Node.js | v24.21.0 | `node --version` |
| npm | 11.19.0 | `npm --version` |
| pip | 26.2.1 | `python -m pip --version` |
| 操作系统 | Windows（用户 jh4026） | — |

## 后端虚拟环境与依赖

- 虚拟环境：项目根目录 `.venv/`，由 `python -m venv --without-pip .venv` 创建，随后用 `ensurepip` 补装 pip。
- 实际锁定版本（`pip install -r requirements-dev.txt` 后实测）：

| 包 | 版本 |
| --- | --- |
| fastapi | 0.143.0 |
| uvicorn | 0.54.0 |
| pydantic | 2.14.0 |
| pydantic-core | 2.50.0 |
| starlette | 1.7.0 |
| pytest | 9.1.1 |
| httpx | 0.28.1 |
| anyio | 4.15.1 |

## 环境问题与 workaround（重要，可复现性依赖此条）

Python 3.14 会把 `os.mkdir(path, mode)` 的 `mode` 应用到 Windows DACL。`tempfile` 模块固定用 `os.mkdir(dir, 0o700)` 创建临时目录，在 DSH 沙箱（受限 token）下会生成一个连创建者本人都无法访问的目录，导致 `ensurepip` 和所有 `pip install` 解压临时目录时 `PermissionError`。

**解决**：`.venv/Lib/site-packages/sitecustomize.py` 在解释器启动时 patch `os.mkdir`，忽略 `mode` 参数（Windows 上 0o700 本无实际意义）。该文件在 `.venv` 内，不进入版本库。

**重新搭建环境的完整步骤**（换机器/重建时按此执行）：

```powershell
python -m venv --without-pip .venv
# 把 sitecustomize.py 写入 .venv\Lib\site-packages\sitecustomize.py（内容见下）
.\.venv\Scripts\python.exe -m ensurepip --default-pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

sitecustomize.py 内容：

```python
import os as _os
_original_mkdir = _os.mkdir
def _mkdir(path, mode=0o777, **kwargs):
    return _original_mkdir(path, **kwargs)
_os.mkdir = _mkdir
```

## 启动命令（Windows）

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

健康检查：`http://127.0.0.1:8000/api/health` → `{"status":"ok","schema_version":"0.1"}`

## 测试命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_health.py
```
