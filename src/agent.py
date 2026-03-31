import json
import re
from llm_client import LocalLLM
from tool_client import MCPClient

print("STRICT AGENT LOADED")


class MCPAgent:
    """
    Middleware that connects a locally run LLM to a locally run MCP server.
    """

    def __init__(self):
        self.llm = LocalLLM()
        self.client = MCPClient()
        self.tools = self.client.list_tools()

        self.tool_map = {}
        for t in self.tools:
            schema = t.get("input_schema", {})
            self.tool_map[t["name"]] = {
                "tool": t,
                "properties": schema.get("properties", {}),
                "required": set(schema.get("required", [])),
            }

        tool_desc = "\n\n".join(self._format_tool(t) for t in self.tools)

        self.router_system_prompt = f"""
You are a CLI assistant connected to tools through an MCP server.

You must respond in EXACTLY ONE of these two formats:

CHAT: your response here

or

TOOL: tool_name {{"arg": "value"}}

AVAILABLE TOOLS:
{tool_desc}

RULES:
- Never invent tool results.
- Only use tool names that exist in AVAILABLE TOOLS.
- Only use argument names explicitly listed in the tool schema.
- Never include code blocks.
- Never include both CHAT and TOOL in the same response.
- If the user asks for circulars, IDs, subjects, event names, or circular contents, use a tool.
- Do not answer from memory when a tool is needed.
- Do not invent example circulars or placeholder IDs.
- Output exactly one line of action, either CHAT or TOOL.
"""

        self.summary_system_prompt = """
You are summarizing tool output for a CLI user.

Respond in EXACTLY this format:
CHAT: <concise grounded answer>

RULES:
- Do not use TOOL.
- Do not invent information.
- Only use the provided tool result.
- If the tool result is empty, say no results were found.
- Keep the answer brief and factual.
"""

    def _format_tool(self, tool: dict) -> str:
        lines = [f"- {tool['name']}: {tool['description']}"]
        schema = tool.get("input_schema", {})
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        if props:
            lines.append("  Arguments:")
            for arg_name, arg_info in props.items():
                arg_type = arg_info.get("type", "any")
                arg_desc = arg_info.get("description", "")
                req = "required" if arg_name in required else "optional"
                lines.append(f"    - {arg_name} ({arg_type}, {req}): {arg_desc}")

        return "\n".join(lines)

    def run(self, prompt: str):
        prompt = prompt.strip()

        router_messages = [
            {"role": "system", "content": self.router_system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            reply = self.llm.chat(router_messages).strip()
        except Exception as e:
            return f"LLM error: {e}"

        print(f"[LLM RAW] {reply}")

        kind = self.classify_reply(reply)

        if kind == "chat":
            return reply[len("CHAT:"):].strip()

        if kind != "tool":
            return (
                "The model returned an invalid response format. "
                "It must return either CHAT: ... or TOOL: tool_name {...}"
            )

        try:
            name, args = self.parse_tool(reply)
            self.validate_tool_call(name, args)
        except Exception as e:
            return f"Invalid tool call: {e}"

        try:
            result = self.client.call(name, args)
        except Exception as e:
            return f"Tool error: {e}"

        self.log_tool_result(result)

        direct = self.format_tool_result(name, result)
        if direct is not None:
            return direct

        summary = self.summarize_tool_result(prompt, name, result)
        if summary is not None:
            return summary

        return json.dumps(result, indent=2, ensure_ascii=False)

    def classify_reply(self, text: str) -> str:
        if text.startswith("CHAT:"):
            if "\nTOOL:" in text or "```" in text:
                return "invalid"
            return "chat"

        if text.startswith("TOOL:"):
            if "\nCHAT:" in text or "```" in text:
                return "invalid"
            return "tool"

        return "invalid"

    def parse_tool(self, text: str):
        match = re.fullmatch(
            r"TOOL:\s*([a-zA-Z0-9_\-]+)\s*(\{.*\})",
            text,
            re.DOTALL,
        )
        if not match:
            raise ValueError(f"Expected exactly one tool call, got: {text}")

        name = match.group(1)
        raw_args = match.group(2).strip()

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON arguments: {raw_args}") from e

        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a JSON object.")

        return name, args

    def validate_tool_call(self, name: str, args: dict):
        if name not in self.tool_map:
            raise ValueError(f"Unknown tool '{name}'.")

        schema = self.tool_map[name]
        allowed_args = set(schema["properties"].keys())
        required_args = schema["required"]

        unknown = set(args.keys()) - allowed_args
        if unknown:
            raise ValueError(
                f"Unknown arguments for {name}: {sorted(unknown)}. "
                f"Allowed: {sorted(allowed_args)}"
            )

        missing = required_args - set(args.keys())
        if missing:
            raise ValueError(
                f"Missing required arguments for {name}: {sorted(missing)}"
            )

    def summarize_tool_result(self, user_prompt: str, tool_name: str, result):
        summary_messages = [
            {"role": "system", "content": self.summary_system_prompt},
            {
                "role": "user",
                "content": (
                    f"Original user request: {user_prompt}\n\n"
                    f"Tool name: {tool_name}\n\n"
                    f"Tool result:\n{json.dumps(result, indent=2, ensure_ascii=False)}"
                ),
            },
        ]

        try:
            reply = self.llm.chat(summary_messages).strip()
        except Exception:
            return None

        print(f"[LLM RAW SUMMARY] {reply}")

        if reply.startswith("CHAT:") and "```" not in reply and "\nTOOL:" not in reply:
            return reply[len("CHAT:"):].strip()

        return None

    def format_tool_result(self, tool_name: str, result):
        """
        Optional direct formatter for simple tool outputs.
        Keeps things generic enough to avoid hardcoding routing logic.
        """
        if not isinstance(result, list) or not result:
            return "No results were found."

        texts = []
        for item in result[:5]:
            if isinstance(item, dict):
                text = item.get("text", "")
            else:
                text = str(item)

            if text:
                texts.append(text.strip())

        if not texts:
            return "No results were found."

        if len(texts) == 1:
            return texts[0]

        joined = "\n\n".join(f"[{i+1}]\n{text}" for i, text in enumerate(texts))
        return joined

    def log_tool_result(self, result):
        if isinstance(result, list):
            print(f"[TOOL RESULT] {len(result)} items returned")
            for i, item in enumerate(result):
                text = item.get("text", "") if isinstance(item, dict) else str(item)
                print(f"  [{i}]: {text[:300]}")
        else:
            print("[TOOL RESULT] non-list result returned")
            print(str(result)[:500])