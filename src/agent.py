import json
from llm_client import LocalLLM
from tool_client import MCPClient
import re


class MCPAgent:
    """
    Middleware that connects a locally run LLM to a locally run MCP server
    """
    def __init__(self):
        self.llm = LocalLLM()
        self.client = MCPClient()

        # Initialize tools that can be seen by local LLM
        self.tools = self.client.list_tools() 

        # Build a richer description including argument schemas
        tool_desc = "\n\n".join(
            self._format_tool(t) for t in self.tools
        )
        
        # System prompt that tells the local LLM how to interact with the tools on the mcp server
        self.system_prompt = f"""
        You are a tool-calling assistant. When the user asks you to fetch, analyze, or do anything with data, you MUST call a tool immediately.

        TO CALL A TOOL respond in EXACTLY this format and nothing else:
        TOOL: tool_name {{"arg": "value"}}

        Example:
        TOOL: fetch_gcn_circulars {{"start_index": 0, "end_index": 10}}

        AVAILABLE TOOLS:
        {tool_desc}

        RULES:
        - ALWAYS call a tool when the user asks for data. Never describe, explain, or write code instead.
        - NEVER invent tool results.
        - NEVER write shell commands, aliases, code, or anything other than a TOOL: call when fetching data.
        - When a tool response is provided, base your answer ONLY on that data.
        - After receiving a tool result, either call another tool or give a brief answer. Never repeat the raw data back.
        - If tool output is empty, say no results found.
        - After receiving a tool result, respond in ONE sentence only. No code, no explanations, no examples.
        - NEVER reference functions, code, or methods that don't exist as tools.
        - NEVER include code blocks in your responses.
        - ONLY use argument names that are explicitly listed in the tool schema. Never invent new argument names.
        """
        self.messages = [{"role": "system", "content": self.system_prompt}] # Keeps memory of previous chats and adds them to the system prompt

    def _format_tool(self, tool: dict) -> str:
        """
        Helper function to organize the tools the local LLM can see in a way
        it understands how each tool works and how to format it's reponses
        """
        lines = [f"- {tool['name']}: {tool['description']}"]
        schema = tool.get("input_schema", {}) # Tells llm how to use the available argument of each tool
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
        with open("memory.txt", "w") as file:
            file.write(json.dumps(self.messages, indent=2))

        while True:
            reply = self.llm.chat(self.messages).strip()
            print(f"[LLM RAW] {reply}")
            self.messages.append({"role": "assistant", "content": reply})

            # No tool call — just a conversational response
            if "TOOL:" not in reply:
                return reply

            # Parse and call tool
            name, args = self.parse_tool(reply)
            result = self.client.call(name, args)

            print(f"[TOOL RESULT] {len(result)} items returned")
            for i, item in enumerate(result):
                text = item.get("text", "")
                try:
                    parsed = json.loads(text)
                    print(f"  [{i}]: subject={parsed.get('subject')} | body={parsed.get('body', '')[:300]}...")
                except Exception:
                    print(f"  [{i}]: {text[:200]}")

            self.messages.append({
                "role": "tool",
                "content": json.dumps(result, indent=2)
            })

    def parse_tool(self, text):
        """
        Helper tool for parsing the LLM's output to see if there is a tool call
        """
        match = re.search(
            r"TOOL:\s*([a-zA-Z0-9_\-]+)\s*(\{.*?\})",
            text,
            re.DOTALL
        )

        if not match:
            raise ValueError(f"Expected tool call but none found in: {text}")

        name = match.group(1)
        try:
            args = json.loads(match.group(2))
        except Exception:
            args = {}

        return name, args