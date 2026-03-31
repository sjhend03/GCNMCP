import requests
import uuid
import json
import os


class MCPClient:
    """
    Middleware that allows the agent to connect to the MCP server.
    """
    def __init__(self, url=None, timeout=60):
        self.url = url or os.getenv("MCP_URL", "http://localhost:8080/mcp")
        self.timeout = timeout
        self._initialize()

    def _parse_json_or_sse(self, response: requests.Response) -> dict:
        # Try standard JSON first
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

        # Fallback for simple SSE responses
        text = response.text.strip()
        data_lines = []

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                chunk = line[len("data:"):].strip()
                if chunk and chunk != "[DONE]":
                    data_lines.append(chunk)

        if not data_lines:
            raise RuntimeError(f"Unexpected non-JSON response: {text[:500]}")

        data_blob = "\n".join(data_lines)

        try:
            payload = json.loads(data_blob)
        except Exception as exc:
            raise RuntimeError(
                f"Could not parse SSE payload as JSON: {exc}; raw={data_blob[:500]}"
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected parsed payload type: {type(payload)}")

        return payload

    def _normalize_tool_result(self, result):
        """Normalize MCP tool results into list[dict] expected by agent.py."""
        if isinstance(result, list):
            normalized = []
            for item in result:
                if isinstance(item, dict):
                    normalized.append(item)
                else:
                    normalized.append({"type": "text", "text": str(item)})
            return normalized

        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list):
                normalized = []
                for item in content:
                    if isinstance(item, dict):
                        normalized.append(item)
                    else:
                        normalized.append({"type": "text", "text": str(item)})
                return normalized

            structured = result.get("structuredContent")
            if structured is not None:
                return [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}]

            return [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]

        return [{"type": "text", "text": str(result)}]

    def _post(self, method, params=None):
        r = requests.post(
            self.url,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": method,
                "params": params or {},
            },
            timeout=self.timeout,
        )
        r.raise_for_status()

        payload = self._parse_json_or_sse(r)

        if "result" in payload:
            return payload["result"]

        if "error" in payload:
            raise RuntimeError(f"Tool server error: {json.dumps(payload['error'], ensure_ascii=False)}")

        raise RuntimeError(f"Unexpected tool response: {payload}")

    def _initialize(self):
        self._post("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "gcnmcp-cli",
                "version": "0.1.0",
            },
        })

    def list_tools(self):
        result = self._post("tools/list")
        return result["tools"]

    def call(self, name, args):
        raw = self._post("tools/call", {
            "name": name,
            "arguments": args,
        })
        return self._normalize_tool_result(raw)