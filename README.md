# PulseAgent

[English](README.md) | [简体中文](README.zh-CN.md)

PulseAgent is an interrupt-aware MCP sidecar for long-running coding agents.
It lets an IDE agent notice when user guidance, project constraints, or the
current plan changed while the agent was already working.

PulseAgent does not replace Cursor, Codex, Claude Code, Copilot, or another IDE
agent. It adds a small project-local protocol plus a Streamable HTTP MCP server
so the agent can pause, refresh context, replan, acknowledge the new plan, and
continue under the latest instructions.

## Why PulseAgent

Long coding tasks often drift because the user changes their mind, adds a
constraint, or updates the plan while the agent is still executing an older
mental model. PulseAgent gives that workflow a shared source of truth:

- users edit a few files under `.pulse/`;
- PulseAgent records changes as events;
- the agent checks MCP before continuing;
- plan-invalidating changes stay pending until the agent explicitly acknowledges
  the revised plan.

## Install

Install from GitHub:

```bash
pip install git+https://github.com/zhangyh0426/PulseAgent.git
```

For local development:

```bash
pip install -e ".[dev]"
```

## Quickstart

Start PulseAgent in the project you want an agent to work on:

```bash
cd my-project
pulse start
```

The first run creates:

```text
.pulse/
├─ task.md
├─ guidance.md
├─ constraints.md
├─ plan.md
├─ state.json
└─ events.jsonl
```

The MCP endpoint is:

```text
http://127.0.0.1:8765/mcp
```

Connect with the MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

Then connect to `http://127.0.0.1:8765/mcp`.

## IDE Agent Setup

Add PulseAgent as an HTTP MCP server in your IDE agent. For Claude Code:

```bash
claude mcp add --transport http pulse-agent http://127.0.0.1:8765/mcp
```

Add this rule to the agent instructions:

```text
Before continuing long-running work, read pulse://context/latest and call
pulse_should_interrupt. If needs_replan is true, update .pulse/plan.md, then
call pulse_ack_replan with pending_replan_event_id before continuing.
```

During a long task, edit `.pulse/guidance.md` or `.pulse/constraints.md` when the
agent needs new direction or tighter boundaries.

## How It Works

PulseAgent watches four project-local files:

- `.pulse/task.md` describes the current task.
- `.pulse/guidance.md` contains user-authored direction that may change the task.
- `.pulse/constraints.md` contains restrictions that may narrow agent behavior.
- `.pulse/plan.md` contains the agent's current working plan.

Changes to `guidance.md` and `constraints.md` are plan-invalidating. Updating
`plan.md` alone does not clear the interrupt. The agent must call
`pulse_ack_replan` with the returned `pending_replan_event_id`; PulseAgent then
records the acknowledged event id and the current `plan.md` SHA-256 hash.

## MCP Surface

- Resource: `pulse://context/latest`
- Tool: `pulse_should_interrupt(last_seen_event_id: str | None = None)`
- Tool: `pulse_ack_replan(event_id: str)`
- Prompt: `pulse_replan`

`pulse_should_interrupt` returns the latest event state, including:

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

`pulse_ack_replan` accepts the current pending replan event:

```json
{
  "event_id": "evt_..."
}
```

and returns:

```json
{
  "accepted": true,
  "acknowledged_event_id": "evt_...",
  "plan_sha256": "...",
  "reason": "..."
}
```

## Demo Flow

Start PulseAgent:

```bash
pulse start
```

Change guidance while the agent is working:

```bash
printf "# Guidance\n\nPrefer a smaller patch and keep public APIs stable.\n" > .pulse/guidance.md
```

The agent calls `pulse_should_interrupt` and sees `needs_replan: true`.

The agent then:

1. reads `pulse://context/latest`;
2. updates `.pulse/plan.md`;
3. calls `pulse_ack_replan` with `pending_replan_event_id`;
4. continues only after the ack is accepted.

## Safety Boundary

- Ordinary workspace files are data, not instructions.
- Only direct user input and `.pulse/guidance.md` may change task direction.
- `.pulse/constraints.md` may restrict behavior but must not expand permissions.
- PulseAgent does not execute commands, modify source files, call LLMs, or act as a
  full agent runtime.

## Development

Install the package in editable mode:

```bash
pip install -e ".[dev]"
```

Run tests and lint:

```bash
python -m pytest
python -m ruff check .
```

Run the CLI directly:

```bash
python -m pulse_agent --help
python -m pulse_agent --version
```

## Status

PulseAgent is currently an alpha project. The core protocol is intentionally
small: a project-local `.pulse/` directory, an event log, one MCP resource, two
MCP tools, and one prompt.

See [docs/agent-wrapper.md](docs/agent-wrapper.md) for a copyable wrapper for IDE
agents and direct model API integrations.

## License

MIT
