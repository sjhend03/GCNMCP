import { Optional, SchemaConstraint, Tool } from "@leanmcp/core";
import { GcnHttpMcpClient } from "../../src/gcn_http_mcp_client.js";

class CallGcnPythonToolInput {
  @SchemaConstraint({
    description: "Name of Python MCP tool (example: search_gcn_circulars)",
    minLength: 1,
  })
  toolName!: string;

  @Optional()
  @SchemaConstraint({
    description: "Arguments object passed to the Python tool",
    default: {},
  })
  arguments?: Record<string, unknown>;
}

class SearchGcnCircularsInput {
  @SchemaConstraint({ description: "Keyword query text", minLength: 1 })
  query!: string;

  @Optional()
  @SchemaConstraint({ description: "Optional event filter, e.g. GRB 260120B" })
  event?: string;

  @Optional()
  @SchemaConstraint({ description: "Maximum results", default: 10, minimum: 1, maximum: 100 })
  limit?: number;
}

class GetEventCircularsInput {
  @SchemaConstraint({ description: "Event identifier, e.g. EP260119a", minLength: 1 })
  event!: string;

  @Optional()
  @SchemaConstraint({ description: "Maximum results", default: 20, minimum: 1, maximum: 100 })
  limit?: number;
}

class GetGcnCircularInput {
  @SchemaConstraint({ description: "GCN circular numeric ID", minimum: 1 })
  circular_id!: number;
}

class FetchGcnCircularsInput {
  @SchemaConstraint({ description: "Start index (0-based)", minimum: 0 })
  start_index!: number;

  @SchemaConstraint({ description: "End index (exclusive)", minimum: 1 })
  end_index!: number;

  @Optional()
  @SchemaConstraint({ description: "Optional local data directory path" })
  data_dir?: string;
}

class CheckForGrbRegexInput {
  @SchemaConstraint({ description: "Raw circular file index", minimum: 0 })
  index!: number;

  @Optional()
  @SchemaConstraint({ description: "Optional local data directory path" })
  data_dir?: string;
}

class FetchAndCheckCircularForGrbInput {
  @SchemaConstraint({ description: "Raw circular file index", minimum: 0 })
  index!: number;

  @Optional()
  @SchemaConstraint({ description: "Ollama model name", default: "mistral" })
  model?: string;

  @Optional()
  @SchemaConstraint({ description: "Optional local data directory path" })
  data_dir?: string;
}

export class GcnBridgeService {
  private readonly client = new GcnHttpMcpClient();

  private async forward(toolName: string, args: Record<string, unknown>) {
    const result = await this.client.callTool(toolName, args);
    return {
      forwardedTool: toolName,
      result,
    };
  }

  @Tool({
    description: "Forward a tool call to the existing Python GCN MCP server",
    inputClass: CallGcnPythonToolInput,
  })
  async call_gcn_python_tool(input: CallGcnPythonToolInput) {
    return this.forward(input.toolName, input.arguments ?? {});
  }

  @Tool({
    description: "Search indexed GCN circulars with optional event filtering",
    inputClass: SearchGcnCircularsInput,
  })
  async search_gcn_circulars(input: SearchGcnCircularsInput) {
    return this.forward("search_gcn_circulars", {
      query: input.query,
      event: input.event,
      limit: input.limit,
    });
  }

  @Tool({
    description: "Get circulars associated with a specific event",
    inputClass: GetEventCircularsInput,
  })
  async get_event_circulars(input: GetEventCircularsInput) {
    return this.forward("get_event_circulars", {
      event: input.event,
      limit: input.limit,
    });
  }

  @Tool({
    description: "Fetch one indexed GCN circular by circular ID",
    inputClass: GetGcnCircularInput,
  })
  async get_gcn_circular(input: GetGcnCircularInput) {
    return this.forward("get_gcn_circular", {
      circular_id: input.circular_id,
    });
  }

  @Tool({
    description: "Fetch and preview raw GCN circular JSON records by index range",
    inputClass: FetchGcnCircularsInput,
  })
  async fetch_gcn_circulars(input: FetchGcnCircularsInput) {
    return this.forward("fetch_gcn_circulars", {
      start_index: input.start_index,
      end_index: input.end_index,
      data_dir: input.data_dir,
    });
  }

  @Tool({
    description: "Regex-only GRB check on raw circular subject",
    inputClass: CheckForGrbRegexInput,
  })
  async check_for_grb_regex(input: CheckForGrbRegexInput) {
    return this.forward("check_for_grb_regex", {
      index: input.index,
      data_dir: input.data_dir,
    });
  }

  @Tool({
    description: "Use Ollama model to detect GRB and redshift in a raw circular",
    inputClass: FetchAndCheckCircularForGrbInput,
  })
  async fetch_and_check_circular_for_grb(input: FetchAndCheckCircularForGrbInput) {
    return this.forward("fetch_and_check_circular_for_grb", {
      index: input.index,
      model: input.model,
      data_dir: input.data_dir,
    });
  }
}
