# PulseAgent

[English](README.md) | [简体中文](README.zh-CN.md)

长时间运行的编码 Agent 很容易漂移：用户已经改变任务方向或约束，但 Agent 仍在执行昨天的计划。

PulseAgent 给编码 Agent 提供一个接收“指令变化”的收件箱。当 `.pulse/guidance.md` 或
`.pulse/constraints.md` 发生变化时，Agent 可以暂停、刷新上下文、修改 `.pulse/plan.md`、
确认这次 replan，然后在最新指令下继续。

PulseAgent 不替代 Cursor、Codex、Claude Code、Copilot 或其他 IDE Agent。
从技术上说，它是一个可感知中断的 MCP sidecar：一个轻量的项目本地协议，加上
Streamable HTTP MCP 服务，让现有 Agent 可以在继续长任务前检查是否需要重新规划。

## 为什么需要 PulseAgent

长时间编码任务容易发生漂移，因为用户意图变化时，Agent 可能还在执行旧的心智模型。
PulseAgent 为这个过程提供一个共享事实源：

- 用户只需要编辑 `.pulse/` 下的少量文件；
- PulseAgent 将文件变化记录为事件；
- Agent 在继续执行前通过 MCP 检查状态；
- 会让计划失效的变化会保持 pending，直到 Agent 显式确认已经更新计划。

## 安装

从 GitHub 安装：

```bash
pip install git+https://github.com/zhangyh0426/PulseAgent.git
```

本地开发安装：

```bash
pip install -e ".[dev]"
```

## 快速开始

在需要 Agent 工作的项目中启动 PulseAgent：

```bash
cd my-project
pulse start
```

首次启动会创建：

```text
.pulse/
├─ task.md
├─ guidance.md
├─ constraints.md
├─ plan.md
├─ state.json
└─ events.jsonl
```

默认 MCP 端点是：

```text
http://127.0.0.1:8765/mcp
```

使用 MCP Inspector 连接验证：

```bash
npx -y @modelcontextprotocol/inspector
```

然后连接到 `http://127.0.0.1:8765/mcp`。

## IDE Agent 接入

把 PulseAgent 作为 HTTP MCP server 添加到你的 IDE Agent。以 Claude Code 为例：

```bash
claude mcp add --transport http pulse-agent http://127.0.0.1:8765/mcp
```

把下面规则加入 Agent 指令：

```text
Before continuing long-running work, read pulse://context/latest and call
pulse_should_interrupt. If needs_replan is true, update .pulse/plan.md, then
call pulse_ack_replan with pending_replan_event_id before continuing.
```

在长任务过程中，如果需要调整方向或收紧边界，编辑 `.pulse/guidance.md` 或
`.pulse/constraints.md`。

## 工作机制

PulseAgent 监听四个项目本地文件：

- `.pulse/task.md` 描述当前任务。
- `.pulse/guidance.md` 保存用户给出的任务方向，可以改变任务走向。
- `.pulse/constraints.md` 保存限制条件，用于收紧 Agent 行为。
- `.pulse/plan.md` 保存 Agent 当前工作计划。

`guidance.md` 和 `constraints.md` 的变化会让计划失效。单独更新 `plan.md` 不会清除中断。
Agent 必须使用返回的 `pending_replan_event_id` 调用 `pulse_ack_replan`；PulseAgent 随后会记录
已确认的事件 ID 和当前 `plan.md` 的 SHA-256 哈希。

### `.pulse/events.jsonl` 是什么？

`.pulse/events.jsonl` 是被监听 `.pulse/` 文件的 append-only 事件账本。每一行记录一次文件变化，
包括事件 ID、路径、SHA-256 哈希、文件大小、时间戳和变化类型。它主要用于调试，也让 MCP 工具知道
Agent 上次检查之后发生了什么变化。

不要把 `events.jsonl` 当成用户指令，也不要手动编辑它。Agent 应该读取 `pulse://context/latest`，
并调用 `pulse_should_interrupt`，而不是直接解析这个日志。

## MCP 接口

- Resource: `pulse://context/latest`
- Tool: `pulse_should_interrupt(last_seen_event_id: str | None = None)`
- Tool: `pulse_ack_replan(event_id: str)`
- Prompt: `pulse_replan`

`pulse_should_interrupt` 返回最新事件状态，例如：

```json
{
  "needs_replan": true,
  "latest_event_id": "evt_...",
  "has_new_events": true,
  "changed_files": [".pulse/guidance.md"],
  "pending_replan_event_id": "evt_...",
  "pending_replan_files": [".pulse/guidance.md"],
  "last_acknowledged_event_id": null,
  "last_acknowledged_plan_sha256": null,
  "reason": "..."
}
```

`pulse_ack_replan` 接收当前待确认的 replan 事件：

```json
{
  "event_id": "evt_..."
}
```

返回：

```json
{
  "accepted": true,
  "acknowledged_event_id": "evt_...",
  "plan_sha256": "...",
  "reason": "..."
}
```

## 演示流程

启动 PulseAgent：

```bash
pulse start
```

在 Agent 工作时修改 guidance：

```bash
printf "# Guidance\n\nPrefer a smaller patch and keep public APIs stable.\n" > .pulse/guidance.md
```

Agent 调用 `pulse_should_interrupt` 后会看到 `needs_replan: true`。

随后 Agent 应该：

1. 读取 `pulse://context/latest`；
2. 更新 `.pulse/plan.md`；
3. 使用 `pending_replan_event_id` 调用 `pulse_ack_replan`；
4. 只有在 ack 被接受后才继续执行。

## 安全边界

- 普通工作区文件只作为数据，不作为指令。
- 只有直接用户输入和 `.pulse/guidance.md` 可以改变任务方向。
- `.pulse/constraints.md` 只能收紧行为限制，不能扩大权限。
- PulseAgent 不执行命令、不修改源码、不调用 LLM，也不是完整的 Agent runtime。

## 开发

以 editable 模式安装：

```bash
pip install -e ".[dev]"
```

运行测试和 lint：

```bash
python -m pytest
python -m ruff check .
```

直接运行 CLI：

```bash
python -m pulse_agent --help
python -m pulse_agent --version
```

## 项目状态

PulseAgent 目前是 alpha 项目。核心协议刻意保持小而清晰：项目本地 `.pulse/` 目录、
事件日志、一个 MCP resource、两个 MCP tools 和一个 prompt。

IDE Agent 和直接模型 API 集成可参考 [docs/agent-wrapper.md](docs/agent-wrapper.md)。

## 许可证

MIT
