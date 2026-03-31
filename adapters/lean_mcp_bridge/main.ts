import "reflect-metadata";
import { createHTTPServer, MCPServer } from "@leanmcp/core";
import { GcnBridgeService } from "./mcp/gcn/index.js";

const serverFactory = () => {
  const server = new MCPServer({
    name: "gcnmcp-leanmcp-bridge",
    version: "0.1.0",
    logging: true,
  });

  server.registerService(new GcnBridgeService());
  return server.getServer();
};

const port = Number(process.env.PORT || 3001);
await createHTTPServer(serverFactory, {
  port,
  cors: true,
  logging: true,
});

console.log(`Server running on http://localhost:${port}`);
console.log(`MCP endpoint: http://localhost:${port}/mcp`);
console.log(`Health check: http://localhost:${port}/health`);
