# web-auto-form

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

> **基于 JSON 配置驱动的浏览器自动化工具，专注表单填写、提交与数据提取。**
>
> 用 JSON 描述你的工作流。无需写代码，无需写脚本，一份配置搞定一切。

---

## 为什么用 web-auto-form？

大部分浏览器自动化工具要求你写代码。**web-auto-form** 与众不同 —— 你只需要在 JSON 文件中描述 *做什么*，引擎会自动处理 *怎么做*。它只做一件事：可靠地、安全地填写网页表单。

### 什么时候用哪个？

| 维度 | web-auto-form | Playwright | Selenium | Browser-Use |
| --- | --- | --- | --- | --- |
| **工作方式** | JSON 配置 | 编写代码 | 编写代码 | 自然语言 |
| **学习曲线** | 零门槛 | 中等 | 陡峭 | 零门槛 |
| **最适合** | 批量表单填写、数据录入、注册自动化、CI 表单测试、LLM Agent 工具 | 现代 Web 测试、复杂 SPA 场景 | 遗留企业系统、跨浏览器测试 | 一次性探索任务、调研爬取 |
| **AI Agent 集成** | **原生支持** — 内置 JSON 工具模式和系统提示 | 需自行封装 | 需自行封装 | 内置（但间接） |
| **确定性** | 100% 确定性 | 确定性 | 确定性 | 非确定性（LLM 决策） |
| **执行速度** | 快（无 LLM 推理） | 快 | 中等 | 慢（每步调用 LLM） |
| **隐私脱敏** | **内置** — 自动脱敏邮箱、电话、身份证号 | 手动处理 | 手动处理 | 手动处理 |
| **条件逻辑** | JSON 声明式 `if`/`else` | 代码驱动 | 代码驱动 | 提示词驱动 |
| **选择器韧性** | 自动检测 + 回退链 | 手动处理 | 手动处理 | LLM 驱动（不可靠） |
| **调试产物** | 每步自动截图 + HTML 快照 | Trace viewer | 手动截图 | 有限 |
| **单次运行成本** | 免费（本地执行） | 免费 | 免费 | 每步产生 LLM API 费用 |
| **典型用例** | "用不同数据填 500 份申请表" | "测试带 WebSocket 的 React 仪表盘" | "自动化 IE 专用的内网表单" | "在全网找最便宜的机票" |

**一句话选型：**
- 填**表单** → 用 web-auto-form
- 写**测试** → 用 Playwright
- **IE11 / 老旧系统** → 用 Selenium
- **一次性探索** → 用 Browser-Use

---

## 功能特性

| 特性 | 说明 |
| --- | --- |
| **13 种动作** | navigate, fill, select, check, click, upload, wait, scroll, extract, press_key, handle_dialog, if, assert |
| **结构化定位器** | 10 种 strategy——`role`、`label`、`testid`、`text`、`placeholder`、`id`、`name`、`attr`、`css`、`xpath`——外加回退链 |
| **模板注入防护** | 不可信数据只能填值槽位，永不进语法位置；无法转义的写法在浏览器启动前就被拒绝 |
| **模板变量** | `{{user.name}}` 语法，支持嵌套点号访问 |
| **结构化错误** | 每个失败都带机器可读的 `error_code` 与 `retryable` 标志 |
| **失败策略** | `on_fail` 驱动 abort / continue / retry；重试只有一个 owner——引擎本身 |
| **条件分支** | `if`/`else`，支持基于状态或基于值的条件，最多 3 层嵌套 |
| **断言** | 验证页面状态，每次尝试只检查一次，重试不会被重复计数 |
| **隐私脱敏** | 自动脱敏邮箱、电话、中国 18 位身份证号、美国 SSN |
| **结构化提取** | 从多个元素提取文本、属性或 HTML 到命名结果字典 |
| **调试模式** | 每步自动截图与 HTML 快照 |
| **双接口** | `web_auto_form run` CLI 或 `from web_auto_form import run` Python API |
| **LLM 工具集成** | 内置 JSON 工具模式和系统提示，可直接被 AI Agent（Claude、Cursor 等）调用 |

---

## 快速开始

### 安装

```bash
pip install web-auto-form
playwright install chromium
```

### 第一个自动化任务

创建 `my_form.json`：

```json
{
  "url": "https://example.com/apply",
  "consent_statement": "自动化填写个人数据。",
  "steps": [
    {"action": "fill", "selector": "#name", "value": "张三"},
    {"action": "fill", "selector": "#email", "value": "zhangsan@example.com"},
    {"action": "click", "selector": "button[type='submit']"}
  ]
}
```

运行：

```bash
web_auto_form run my_form.json
```

新配置建议优先用结构化 `locator` 而非 `selector` 字符串——原因见[定位器](#定位器)
（既更抗改版，也是唯一能安全地用模板变量参数化的写法）。

---

## CLI 用法

```bash
# 基础运行
web_auto_form run config.json

# 命令行覆盖数据变量
web_auto_form run config.json --data user.name=李四 --data user.email=lisi@test.com

# 强制有头模式 + 调试输出
web_auto_form run config.json --no-headless --debug

# 保存输出到文件
web_auto_form run config.json --output result.json
```

---

## Python API

```python
from web_auto_form import run, run_from_path

# 从字典执行
result = run({
    "url": "https://example.com",
    "consent_statement": "测试用途。",
    "steps": [{"action": "fill", "selector": "#name", "value": "测试"}],
})

# 从 JSON 文件执行
result = run_from_path("config.json")

print(result["status"])       # "success" | "partial" | "failed"
print(result["extracted"])    # {"字段名": "提取的值", ...}
```

### 返回值

```python
{
    "status": "success",           # success | partial | failed
    "consent_logged": "...",
    "aborted": False,              # True 表示 workflow 提前终止
    "steps_executed": 14,          # 已执行步骤数
    "steps_skipped": 1,            # 跳过的可选步骤数
    "steps_failed": 0,             # 失败步骤数
    "results": [                   # 每步结果
        {"step": 0, "action": "fill", "status": "ok", "duration_ms": 340},
        # 失败步骤额外带 error_code 与 retryable
        {"step": 1, "action": "click", "status": "failed", "duration_ms": 5000,
         "error": "Timeout 5000ms exceeded.", "error_code": "ELEMENT_NOT_VISIBLE",
         "retryable": True}
    ],
    "extracted": {                 # 结构化提取输出
        "confirmation_message": "您的申请已提交成功。"
    },
    "step_screenshots": [],
    "final_screenshot": None,
    "errors": [                    # 结构化，调用方可直接按 code / field 处理
        {"code": "CONFIG_VALIDATION_ERROR", "message": "Field required",
         "field": "consent_statement", "type": "missing"}
    ]
}
```

`run()` 对配置错误**不会抛异常**——非法配置以结构化失败返回，调用方可以直接修正，
而不是收到一段 traceback。

---

## 配置参考

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url` | string | 是 | 起始 URL |
| `consent_statement` | string | 是 | 自动化目的声明（记录在日志中，有头模式下展示并确认） |
| `steps` | StepConfig[] | 是 | 有序动作列表（1–50 步） |
| `data` | dict | 否 | 模板变量，通过 `{{key}}` 访问 |
| `extract_schema` | ExtractSchemaConfig | 否 | 执行后提取规则 |
| `options` | OptionsConfig | 否 | 全局执行设置 |

### 全局选项

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `headless` | `true` | 无头模式运行浏览器 |
| `viewport_width` / `viewport_height` | `1280` / `800` | 浏览器视口 |
| `user_agent` / `locale` | — / `"en-US"` | 自定义 User-Agent 与浏览器 locale |
| `step_delay_ms` | `500` | 步骤间延迟（最小 100ms） |
| `max_total_ms` | `300000` | 整个 workflow 的预算。唯一的执行时长旋钮：超过它不再启动新步骤，`wait` 超出剩余预算直接以 `TIMEOUT` 失败 |
| `max_retries` | `1` | 每步**首次尝试之外**的额外次数（`2` → 最多执行 3 次） |
| `retry_on` | `["NETWORK_ERROR"]` | 允许自动重试的错误码 |
| `redact_pii` | `true` | 在日志和提取输出中自动脱敏 |
| `debug` | `false` | 保存每步截图与 HTML 快照 |
| `debug_output_path` | `"./web_auto_form_debug_<timestamp>/"` | 调试产物输出目录 |
| `sandbox` | `true` | 浏览器沙盒模式 |
| `keep_open` | `false` | 完成后保持浏览器打开 |
| `upload_enforce_extension` | `false` | `file_name` 扩展名与 MIME 类型矛盾时阻止上传 |
| `diagnose_on_failure` | `true` | 在最后一次失败时采集截图与页面表单元素 |

---

## 动作类型

### 导航与交互

| 动作 | 说明 | 必填字段 |
| --- | --- | --- |
| `navigate` | 打开 URL | `value` (URL) |
| `fill` | 在输入框中输入文本 | *target*, `value` |
| `click` | 点击元素 | *target* |
| `select` | 按 value 或标签选择下拉选项 | *target*, `value` |
| `check` | 选中或取消复选框 | *target*, `value` ("true"/"false") |
| `upload` | 上传文件（本地路径、URL 或 data URI） | *target*, `value` |
| `press_key` | 按下键盘按键 | `value`（如 "Enter", "Tab"） |
| `scroll` | 滚动页面 | `value`（"up"/"down"/像素值） |
| `handle_dialog` | 接受或关闭浏览器对话框 | `value`（"accept"/"dismiss"） |

*target* 是 `selector`（字符串）或 `locator`（结构化）之一，详见[定位器](#定位器)。
二者互斥。

### 流程控制

| 动作 | 说明 | 关键字段 |
| --- | --- | --- |
| `wait` | 等待元素、导航、超时或 JS 表达式 | `type`, *target* 或 `value` |
| `if` | 条件分支 | `condition`, `then`, `else`（可选） |
| `assert` | 验证元素状态（每次尝试只检查一次，重试由 `on_fail` 驱动） | *target*, `state`, `on_fail` |

### 等待子类型

| 类型 | 行为 | `value` |
| --- | --- | --- |
| `element`（默认） | 轮询直到目标出现 | — |
| `navigation` | 等待页面加载 | — |
| `timeout` | 无条件等待，受剩余 `max_total_ms` 预算约束 | 毫秒数字符串（如 `"3000"`） |
| `function` | 轮询直到 JS 表达式返回真值 | JS 表达式字符串——**不允许模板变量** |

### 条件类型

**基于状态**（`exist`, `not_exist`, `visible`, `hidden`, `checked`）：

```json
{ "selector": "#checkbox", "state": "checked" }
```

**基于值**（`eq`, `ne`, `contains`, `matches_regex`）：

```json
{ "selector": ".status", "attribute": "textContent", "operator": "eq", "expected_value": "已通过" }
```

---

## 失败语义

每个失败都会被归类为机器可读的 `error_code`（`ELEMENT_NOT_FOUND`、`INVALID_SELECTOR`、`TIMEOUT`、`NETWORK_ERROR`、`ASSERTION_FAILED`、`FILE_UPLOAD_FAILED` 等），并在人类可读的 `error` 之外附带 `retryable` 标志。

`on_fail` 决定后续行为：

| `on_fail` | 失败时 |
| --- | --- |
| `abort`（默认） | 记录失败并终止 workflow——后续步骤不再执行 |
| `continue` | 记录失败并继续；最终状态为 `partial` |
| `retry` | 最多重试 `max_retries` 次，仍失败则终止 workflow |

`optional: true` 优先级最高：该步骤记为 `skipped`，workflow 继续（`on_skip: abort` 是仍会终止的例外）。

**重试只有一个 owner——引擎本身。** Action handler 只执行一次并回报结果，是否再试由引擎决定。`max_retries` 是**首次尝试之外**的额外次数，`max_retries: 2` 表示最多 3 次。错误码在 `retry_on` 列表中且本身可重试，或步骤设置 `on_fail: retry` 时才会重试。嵌套 `if` 内触发的 abort 会向外传播并终止整个 workflow。

---

## 定位器

定位元素有两种写法。字符串 `selector` 行为完全不变；结构化 `locator` 直接声明
*怎么找*，而不是依赖对一个字符串的解析，新配置推荐使用。

```json
{ "action": "fill", "locator": { "strategy": "label", "value": "Email" }, "value": "a@b.com" }
{ "action": "click", "locator": { "strategy": "role", "role": "button", "name": "Submit" } }
```

| strategy | 解析为 |
| --- | --- |
| `role`、`label`、`text`、`placeholder`、`testid` | Playwright 原生 `get_by_*` 匹配器 |
| `id`、`name`、`attr` | CSS 属性测试 |
| `css`、`xpath` | 原样使用 |

**优先级：`role` / `label` / `testid` → `placeholder` / `text` / `name` → 稳定 CSS → XPath 最后。**
语义定位绑定可访问语义，能扛住会击垮脆弱选择器的 id 与 class 改名。

旧的 `selector` 字符串仍按前缀自动检测（`//` XPath、`#` ID、`[name=`、
`[placeholder=`、`[data-testid=`，其余为 CSS），`selector_fallbacks` 仍可串起回退链。

### 模板安全

定位器是不可信 `data` 与解析器唯一相遇的地方，规则很明确：**数据只能填值槽位，永不能进语法位置。**

```json
{ "locator": { "strategy": "label", "value": "{{field}}" } }   // 值作为参数传入
{ "selector": "input[name='{{field}}']" }                      // 值被转义进属性
```

`role`/`label`/`text`/`placeholder`/`testid` 把渲染后的值作为参数交给 Playwright，
根本不进入选择器语法。`id`、`name`、`attr` 把它转义进带引号的 CSS 属性值。
其余任何位置——`div.{{cls}}`、`//div[@id='{{x}}']`、`[{{attr}}='v']`——在浏览器启动前
就以 `TEMPLATE_ERROR` 失败。不含模板变量的选择器属于作者配置，原样使用。

### 回退链

引擎先尝试主定位器，再按序尝试每个回退；先匹配者胜出。**结构性非法**的定位器
（语法错误）会以 `INVALID_SELECTOR` 终止整条链，而不是静默跳到下一个——配置写错了，
静默兜底会掩盖它。仅当所有候选都没匹配上时才触发 `optional` 逻辑。

---

## 隐私脱敏

当 `options.redact_pii` 为 `true`（默认）：

- **日志**：所有 `value` 字段显示为 `<redacted>`
- **提取文本**：邮箱、电话、中国 18 位身份证号、美国 SSN 被替换为 `***`
- **按字段覆盖**：在 `extract_schema.fields[]` 中设置 `redact: false` 可保留特定字段的原始值

---

## AI Agent 集成

web-auto-form 内置了作为 LLM 工具调用所需的全部资源：

- **JSON 工具模式**（[web_auto_form_tool.json](web_auto_form_tool.json)）—— 可直接接入任何 OpenAI/Claude function-calling 管道
- **系统提示**（[SYSTEM_PROMPT.md](SYSTEM_PROMPT.md)）—— 触发条件、安全约束、重试策略和输出格式

### 演示：一句话让 Claude/Cursor 帮你填表

详见 [docs/AI_AGENT_INTEGRATION.md](docs/AI_AGENT_INTEGRATION.md)，包含逐步操作指南和可运行的演示脚本。

**一句话总结：** 对 Claude 说"用我的简历填一下这个职位申请表"，Claude 会自动调用 web-auto-form 在真实浏览器中完成填写。

---

## 示例

| 示例 | 说明 |
| --- | --- |
| [job_application.json](examples/job_application.json) | 完整工作流：模板、条件、断言、回退、文件上传 |
| [google_form.json](examples/google_form.json) | 最小示例：填写 + 点击 + 导航等待 |
| [conditional_form.json](examples/conditional_form.json) | 条件分支：嵌套 if/else、基于值的条件、多重断言与重试 |

---

## 文档

- [步骤参考](docs/STEPS.md) — 每种动作类型及全部参数
- [选择器指南](docs/SELECTORS.md) — 自动检测、回退链、最佳实践
- [隐私脱敏](docs/PII_REDACTION.md) — 脱敏原理与配置
- [AI Agent 集成](docs/AI_AGENT_INTEGRATION.md) — Claude/Cursor/Agent 设置指南
- [JSON 工具模式](web_auto_form_tool.json) — LLM function-calling 完整输入模式
- [系统提示](SYSTEM_PROMPT.md) — AI Agent 集成指南
- [贡献指南](docs/CONTRIBUTING.md) — 开发者设置与 PR 流程
- [行为准则](docs/CODE_OF_CONDUCT.md) — Contributor Covenant 2.1

---

## 开发

```bash
git clone https://github.com/DUZ1287/WebAutoForm.git
cd web-auto-form

make dev          # 安装依赖 + Playwright Chromium
make test         # 运行单元测试
make lint         # flake8 + mypy
make format       # black + isort

# 运行示例
make example

# 清理构建产物
make clean
```

### 不使用 Make 的设置

```bash
pip install -e ".[dev]"
playwright install chromium
python -m pytest -v
```

---

## 在线 Playground

本地运行 Playground，或一键部署到 Hugging Face Spaces —— 详见 [playground/README.md](playground/README.md)。

```bash
pip install gradio
python playground/app.py
```

详见 [playground/README.md](playground/README.md)。

---

## CI

GitHub Actions，Python 3.9–3.12（Ubuntu）：

- **代码检查**：flake8
- **类型检查**：mypy
- **格式检查**：black + isort
- **测试**：pytest

配置文件：[`.github/workflows/ci.yml`](.github/workflows/ci.yml)

---

## 许可证

[MIT](LICENSE)

---

## 项目结构

```text
web-auto-form/
├── src/web_auto_form/
│   ├── __init__.py          # 公共 API：run(), run_from_path()
│   ├── cli.py               # Click CLI
│   ├── browser.py           # Playwright 浏览器生命周期
│   ├── models.py            # Pydantic 模型：StepConfig、LocatorSpec、全局选项
│   ├── runner.py            # 执行引擎：步骤循环、重试、失败策略
│   ├── errors.py            # 错误码、异常分类、可重试性
│   ├── selectors.py         # 定位器 normalize → render → resolve 与回退链
│   ├── templates.py         # {{变量}} 渲染及其安全规则
│   ├── redact.py            # PII 脱敏（基于正则）
│   └── actions/             # 13 个动作处理器
│       ├── navigate.py      # page.goto
│       ├── fill.py          # 输入填写
│       ├── click.py         # 元素点击
│       ├── select.py        # 下拉选择
│       ├── check.py         # 复选框切换
│       ├── upload.py        # 文件上传（本地/URL/data URI）
│       ├── wait.py          # 元素/导航/超时/函数等待
│       ├── scroll.py        # 页面滚动
│       ├── extract.py       # 文本/属性提取
│       ├── press_key.py     # 键盘按键
│       ├── handle_dialog.py # 对话框接受/关闭
│       ├── if_branch.py     # 条件求值
│       └── assertion.py     # 状态验证
├── tests/                   # 单元测试 + 真实浏览器套件（--run-integration）
├── docs/                    # 参考文档
├── demo/                    # 交互式演示 + MCP server
├── examples/                # 示例配置
├── playground/              # Gradio 在线 Playground
├── pyproject.toml           # 构建与工具配置
├── web_auto_form_tool.json  # JSON 工具模式（LLM 集成）
├── SYSTEM_PROMPT.md         # AI Agent 集成指南
└── .github/workflows/ci.yml # CI 管道
```
