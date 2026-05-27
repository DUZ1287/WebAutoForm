# WebAutoForm — Agent Skill

基于 JSON 配置驱动的浏览器表单自动化工具。用 JSON 描述表单工作流，无需写代码。

## 触发判断

当用户请求满足以下任一条件时，使用 `web_auto_form` CLI 执行：

- **中文关键词**：填表、自动提交、网页操作、自动注册、登录、注册、报名、申请、批量录入、表单测试
- **英文关键词**：fill out form、submit form、auto-register、web automation、data entry、sign up
- **意图模式**：多步浏览器交互（navigate → fill → click → submit）、条件表单逻辑、批量数据录入

**不适用场景**：纯信息检索、API 调用、需要验证码识别、无表单的大规模爬取。

## 执行流程

### Step 1 — 理解意图

从用户请求中提取：
- 目标 URL
- 要填写的数据（姓名、邮箱、电话、文件路径等）
- 特殊逻辑（条件分支、需要等待的元素）

### Step 2 — 构造 JSON 配置

根据完整 Schema（参考 [SKILL.md](SKILL.md) 的"完整配置参考"章节），将 JSON 写入临时文件。

**关键规则**：
- `consent_statement` **必须填写**，声明自动化目的
- `options.redact_pii` 默认 `true`，自动脱敏敏感信息
- 单次最多 50 步，if/else 嵌套最多 3 层
- 使用 `{{variable}}` 模板语法引用数据，支持点号嵌套访问
- 为关键步骤（提交按钮、文件上传）提供 `selector_fallbacks`

### Step 3 — 执行

```bash
# 从文件执行
web_auto_form run <config.json>

# 从 stdin 管道输入（跨平台，无需临时文件）
echo '<json>' | web_auto_form run -

# 或使用 here-string (POSIX shell / bash)
web_auto_form run - <<< '<json>'
```

可选参数：
- `--no-headless` — 有头模式，用户可观察浏览器
- `--debug` — 每步截图 + HTML 快照
- `--data key=value` — 命令行覆盖模板变量
- `--output result.json` — 保存输出到文件

### Step 4 — 解析结果并汇报

返回 JSON 结构：

```json
{
  "status": "success|partial|failed",
  "steps_executed": 14,
  "steps_skipped": 1,
  "steps_failed": 0,
  "results": [{"step": 0, "action": "fill", "status": "ok", "duration_ms": 340}],
  "extracted": {"confirmation_message": "提交成功"},
  "errors": []
}
```

- `success` → 全部成功，展示 `extracted` 数据
- `partial` → 有 optional 步骤跳过但无错误，告知用户跳过了哪些
- `failed` → 有步骤失败，展示 `errors` 详情。**失败步骤的 `results[].diagnostics` 包含失败时刻的截图和页面表单元素列表**，Agent 可根据 `diagnostics.form_elements` 中实际存在的元素调整选择器策略后重试。

## 关键约束速查

| 约束 | 值 |
|------|----|
| consent_statement | 必填，声明自动化目的 |
| 最大步骤数 | 50 |
| 嵌套深度上限 | 3 层 |
| 单步超时 | 60s |
| 总执行时间 | 5 分钟 |
| 单步最大重试 | 5 次 |
| 文件上传上限 | 50 MB |
| 最小步骤延迟 | 100ms（默认 500ms） |
| PII 脱敏 | 默认开启，逐字段可覆盖 |
| 浏览器沙箱 | 默认开启 |

## 典型模式

### 模式 1：简单填写 + 提交

```json
{
  "url": "https://example.com/form",
  "consent_statement": "自动填写联系表单。",
  "steps": [
    {"action": "fill", "selector": "#name", "value": "张三"},
    {"action": "fill", "selector": "#email", "value": "zhangsan@example.com"},
    {"action": "click", "selector": "button[type='submit']"}
  ]
}
```

### 模式 2：带模板变量 + 等待 + 提取结果

```json
{
  "url": "https://example.com/register",
  "consent_statement": "自动注册账号。",
  "data": {"user": {"name": "李四", "email": "lisi@test.com"}},
  "steps": [
    {"action": "wait", "selector": "form#register", "type": "element", "timeout_ms": 10000},
    {"action": "fill", "selector": "#name", "value": "{{user.name}}"},
    {"action": "fill", "selector": "#email", "value": "{{user.email}}"},
    {"action": "click", "selector": "#submit"},
    {"action": "wait", "type": "navigation"},
    {"action": "assert", "selector": ".success", "state": "visible", "on_fail": "retry", "max_retries": 3}
  ],
  "extract_schema": {
    "fields": [
      {"name": "message", "selector": ".success", "attribute": "text", "redact": false}
    ]
  }
}
```

### 模式 3：条件分支 + 选择器回退 + 文件上传

```json
{
  "url": "https://example.com/apply",
  "consent_statement": "自动提交职位申请。",
  "data": {"resume": "file:///documents/resume.pdf", "has_exp": true},
  "steps": [
    {"action": "fill", "selector": "#name", "value": "王五"},
    {"action": "if", "condition": {"selector": "#has_experience", "state": "checked"}, "then": [
      {"action": "fill", "selector": "#years", "value": "5"}
    ], "else": [
      {"action": "check", "selector": "#fresh_graduate", "value": "true", "optional": true}
    ]},
    {"action": "upload", "selector": "input[type='file']", "value": "{{resume}}", "file_name": "resume.pdf"},
    {"action": "click", "selector": "button[type='submit']", "selector_fallbacks": ["[data-testid='submit-btn']"]}
  ]
}
```

### 模式 4：多种等待类型

```json
{"action": "wait", "type": "element", "selector": "#form", "timeout_ms": 10000},
{"action": "wait", "type": "navigation", "timeout_ms": 15000},
{"action": "wait", "type": "timeout", "value": "2000"},
{"action": "wait", "type": "function", "value": "document.readyState === 'complete'"}
```

## 完整 Schema

所有 13 种 action 的详细参数、选择器系统、条件分支、重试策略、调试模式等，查阅 [SKILL.md](SKILL.md) 的以下章节：

- [完整配置参考](SKILL.md#完整配置参考) — 顶层字段、全局选项
- [13 种 Action 类型详解](SKILL.md#13-种-action-类型详解) — 每种 action 的参数字段表
- [选择器系统](SKILL.md#选择器系统) — 自动检测、fallback 链、optional 逻辑
- [模板变量](SKILL.md#模板变量) — `{{}}` 语法与注入安全
- [条件分支](SKILL.md#if--条件分支) — 状态条件 vs 值条件
- [重试策略](SKILL.md#重试策略) — 错误分类、两级配置
- [调试模式](SKILL.md#调试模式) — 产物说明
- [限制与上限](SKILL.md#限制与上限) — 硬限制表
