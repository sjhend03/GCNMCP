import logging
from aiohttp import web
from tools import list_tools, call_tool
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPHTTPServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = web.Application()
        self.app.router.add_post('/mcp', self.handle_mcp_request)

    async def handle_mcp_request(self, request):
        try:
            body = await request.json()
            logger.info(f"Request: {body.get('method')}")

            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")

            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "gcn-mcp-server",
                        "version": "0.1.0"
                    }
                }

            elif method == "tools/list":
                tools = await list_tools()
                result = {
                    "tools": [
                        {"name": t.name, "description": t.description}
                        for t in tools
                    ]
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                content = await call_tool(tool_name, arguments)

                # Normalize output so JSON serialization always works
                if isinstance(content, list):
                    normalized = []
                    for item in content:
                        if hasattr(item, "text"):
                            normalized.append({
                                "type": "text",
                                "text": item.text
                            })
                        else:
                            normalized.append(item)
                    result = normalized
                else:
                    result = content

            else:
                raise ValueError(f"Unknown method: {method}")

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }

            return web.json_response(
                response,
                headers={"Access-Control-Allow-Origin": "*"}
            )

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id") if "body" in locals() else None,
                    "error": {"code": -32603, "message": str(e)}
                },
                status=500
            )

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.port)
        await site.start()
        logger.info(f"MCP Server running at http://localhost:{self.port}/mcp")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down MCP server...")

async def main():
    server = MCPHTTPServer(port=8080)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())