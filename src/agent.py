import json
from llm_client import LocalLLM
from tool_client import MCPClient
import re


class MCPAgent:

    def __init__(self):
        self.llm = LocalLLM()
        self.client = MCPClient()

        self.tools = self.client.list_tools()  # list of full tool dicts

        # Build a richer description including argument schemas
        tool_desc = "\n\n".join(
            self._format_tool(t) for t in self.tools
        )

        self.system_prompt = f"""
You are a tool-using assistant.

AVAILABLE TOOLS:
{tool_desc}

RULES:
- NEVER invent tool results.
- When a tool response is provided, base your answer ONLY on that data.
- If the tool returned a list, display that list exactly.
- If tool output is empty, say no results found.
- Do NOT fabricate filenames or data.
- You may call tools multiple times in sequence to complete a task.
- When asked to load the "first N" files, first list the files, then call fetch_gcn_circular_local
  with a "paths" list containing exactly those N file path strings.

TO CALL A TOOL:
Respond ONLY in this exact format (one tool call per response):
TOOL: tool_name {{"arg": "value"}}

Otherwise answer normally.
"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _format_tool(self, tool: dict) -> str:
        lines = [f"- {tool['name']}: {tool['description']}"]
        schema = tool.get("input_schema", {})
        props = schema.get("properties", {})
        if props:
            lines.append("  Arguments:")
            for arg_name, arg_info in props.items():
                arg_type = arg_info.get("type", "any")
                arg_desc = arg_info.get("description", "")
                lines.append(f"    - {arg_name} ({arg_type}): {arg_desc}")
        return "\n".join(lines)

    def run(self, prompt):
        self.messages.append({"role": "user", "content": prompt})
        with open("memory.txt", "a") as file:
            file.write(json.dumps(self.messages, indent=2))
        while True:
            reply = self.llm.chat(self.messages).strip()
            self.messages.append({"role": "assistant", "content": reply})

            if "TOOL:" not in reply:
                return reply

            name, args = self.parse_tool(reply)
            result = self.client.call(name, args)
            print("[TOOL RESULT]", result)

            self.messages.append({
                "role": "tool",
                "content": json.dumps(result, indent=2)
            })

    def parse_tool(self, text):
        match = re.search(
            r"TOOL:\s*([a-zA-Z0-9_\-]+)\s*(\{.*?\})",
            text,
            re.DOTALL
        )

        if not match:
            raise ValueError("No tool call detected")

        name = match.group(1)

        try:
            args = json.loads(match.group(2))
        except Exception:
            args = {}

        return name, args