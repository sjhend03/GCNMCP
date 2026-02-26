import logging
from aiohttp import web
from tools import list_tools, call_tool
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPHTTPServer:
    """
    MCP server that handles calls to endpoints tools/call and tools/list
    port: port that the MCP server will run on the local host
    """
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = web.Application()
        self.app.router.add_post('/mcp', self.handle_mcp_request)

    async def handle_mcp_request(self, request):
        """
        Handler function for any web request to the mcp server
        """
        try:
            body = await request.json()
            logger.info(f"Request method: {body.get('method')}")
            logger.info(f"Request params: {body.get('params')}")


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

            elif method == "tools/list": # Handles list tools requests
                tools = await list_tools()
                result = {
                    "tools": [
                        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                        for t in tools
                    ]
                }

            elif method == "tools/call": # Handles tool call requests
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                content = await call_tool(tool_name, arguments) # Tool call

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
                    print(f"Call results{normalized}")
                    result = normalized
                else:
                    print(f"Call results{content}")
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
                headers={"Access-Control-Allow-Origin": "*"} # Make sure it works with CORS
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

    async def start(self): # Starts server
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