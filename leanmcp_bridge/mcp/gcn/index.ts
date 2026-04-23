import { Optional, SchemaConstraint, Tool } from "@leanmcp/core";
import { callPythonTool } from "../../bridge/python_bridge.js";

class EmptyInput {}

class FetchGcnCircularsInput {
  @SchemaConstraint({
    description: "Start index (0-based, inclusive)",
    minimum: 0,
  })
  start_index!: number;

  @SchemaConstraint({
    description: "End index (exclusive)",
    minimum: 1,
  })
  end_index!: number;

  @Optional()
  @SchemaConstraint({
    description: "Optional directory containing circular JSON files",
  })
  data_dir?: string;
}

class SearchGcnCircularsInput {
  @SchemaConstraint({
    description: "Keyword query text",
    minLength: 1,
  })
  query!: string;

  @Optional()
  @SchemaConstraint({
    description: "Optional exact event filter, e.g. GRB 260120B or EP260119a",
  })
  event?: string;

  @Optional()
  @SchemaConstraint({
    description: "Maximum results",
    minimum: 1,
    maximum: 100,
    default: 10,
  })
  limit?: number;
}

class FetchAndCheckCircularForGrbInput {
  @SchemaConstraint({
    description: "Raw circular file index",
    minimum: 0,
  })
  index!: number;

  @Optional()
  @SchemaConstraint({
    description: "Ollama model name",
    default: "mistral",
  })
  model?: string;

  @Optional()
  @SchemaConstraint({
    description: "Optional directory containing circular JSON files",
  })
  data_dir?: string;
}

class CheckForGrbRegexInput {
  @SchemaConstraint({
    description: "Raw circular file index",
    minimum: 0,
  })
  index!: number;

  @Optional()
  @SchemaConstraint({
    description: "Optional directory containing circular JSON files",
  })
  data_dir?: string;
}

function unwrapPythonTextItems(result: unknown): string[] {
  const items = Array.isArray(result) ? result : [result];

  return items.map((item) => {
    if (
      typeof item === "object" &&
      item !== null &&
      "text" in item
    ) {
      return String((item as { text: unknown }).text);
    }

    if (typeof item === "string") {
      return item;
    }

    return JSON.stringify(item, null, 2);
  });
}

export class GcnService {
  @Tool({
    description: "Simple TypeScript ping for testing LeanMCP",
    inputClass: EmptyInput,
  })
  async ping(_: EmptyInput) {
    return {
      message: "pong from typescript",
    };
  }

  @Tool({
    description: "Simple Python ping for testing the TS to Python bridge",
    inputClass: EmptyInput,
  })
  async ping_python(_: EmptyInput) {
    const texts = unwrapPythonTextItems(await callPythonTool("ping_python", {}));
    return {
      count: texts.length,
      results: texts,
    };
  }

  @Tool({
    description: "Load raw GCN circular JSON files by local file index range",
    inputClass: FetchGcnCircularsInput,
  })
  async fetch_gcn_circulars(input: FetchGcnCircularsInput) {
    const texts = unwrapPythonTextItems(
      await callPythonTool("fetch_gcn_circulars", {
        start_index: input.start_index,
        end_index: input.end_index,
        data_dir: input.data_dir,
      })
    );

    return {
      count: texts.length,
      circulars: texts,
    };
  }

  @Tool({
    description: "Search indexed GCN circulars by keyword in the subject and body text",
    inputClass: SearchGcnCircularsInput,
  })
  async search_gcn_circulars(input: SearchGcnCircularsInput) {
    const texts = unwrapPythonTextItems(
      await callPythonTool("search_gcn_circulars", {
        query: input.query,
        event: input.event,
        limit: input.limit,
      })
    );

    return {
      count: texts.length,
      results: texts,
    };
  }

  @Tool({
    description: "Load one raw circular by local file index and use an LLM to decide whether it is about a GRB and whether it reports a redshift",
    inputClass: FetchAndCheckCircularForGrbInput,
  })
  async fetch_and_check_circular_for_grb(
    input: FetchAndCheckCircularForGrbInput
  ) {
    const texts = unwrapPythonTextItems(
      await callPythonTool("fetch_and_check_circular_for_grb", {
        index: input.index,
        model: input.model,
        data_dir: input.data_dir,
      })
    );

    return {
      count: texts.length,
      results: texts,
    };
  }

  @Tool({
    description: "Load one raw circular by local file index and check whether its subject line contains a GRB designation using regex",
    inputClass: CheckForGrbRegexInput,
  })
  async check_for_grb_regex(input: CheckForGrbRegexInput) {
    const texts = unwrapPythonTextItems(
      await callPythonTool("check_for_grb_regex", {
        index: input.index,
        data_dir: input.data_dir,
      })
    );

    return {
      count: texts.length,
      results: texts,
    };
  }
}