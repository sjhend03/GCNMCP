import "reflect-metadata";
import { createHTTPServer, MCPServer } from "@leanmcp/core";
import { GcnService } from "./mcp/gcn/index.js";

const serverFactory = () => {
    // Create a new MCP server instance
    const server = new MCPServer({
        name: "gcnmcp-bridge",
        version: "0.1.0",
        logging: true,
    });

    // Attach GcnService to the server
    server.registerService(new GcnService());
    return server.getServer();
};

const port = Number(process.env.PORT || 3001);

// Use LeanMCP's server creation tool to take case of everything else
await createHTTPServer(serverFactory, {
    port,
    cors: true,
    logging: true,
});

console.log(`Server is running on port ${port}`);
console.log(`MCP endpoint: http://localhost:${port}/mcp`);  
console.log(`Health check: http://localhost:${port}/health`);