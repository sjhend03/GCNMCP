import requests
import uuid


class MCPClient:

    def __init__(self, url="http://localhost:8080/mcp"):
        self.url = url
        self._initialize()

    def _post(self, method, params=None):
        r = requests.post(
            self.url,
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": method,
                "params": params or {}
            }
        )
        print(r)
        return r.json()["result"]

    def _initialize(self):
        self._post("initialize")

    def list_tools(self):
        result = self._post("tools/list")
        return result["tools"]

    def call(self, name, args):
        return self._post("tools/call", {
            "name": name,
            "arguments": args
        })
