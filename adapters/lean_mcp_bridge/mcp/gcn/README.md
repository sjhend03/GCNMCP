# LeanMCP bridge starter for GCNMCP

This folder is a **LeanMCP-first** bridge that forwards tool calls to the existing Python MCP server.

## Prereqs

- Python server running from repo root:
  ```bash
  python src/server.py
  ```
- Node 18+
- LeanMCP CLI installed:
  ```bash
  npm i -g @leanmcp/cli
  ```

## Setup

```bash
cd adapters/leanmcp-bridge
npm install
npm run dev
```

Default bridge target:

- `GCN_PYTHON_MCP_ENDPOINT=http://localhost:8080/mcp`

## What this exposes

A LeanMCP tool named `call_gcn_python_tool` that forwards:

- `toolName`: Python MCP tool name
- `arguments`: JSON arguments object

Use this to validate LeanMCP deployment before splitting into one wrapper per tool.
