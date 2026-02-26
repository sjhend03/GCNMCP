import requests
import uuid


class MCPClient:
    """
    Middleware that allows the agent to connect to the mcp server.
    Note: this could probably be merged with agent.py
    url: url of mcp server
    """
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

    def _initialize(self): # Initializes server
        self._post("initialize")

    def list_tools(self): # Lists tools
        result = self._post("tools/list")
        return result["tools"]

    def call(self, name, args): # Call specified tool
        return self._post("tools/call", {
            "name": name,
            "arguments": args
        })
