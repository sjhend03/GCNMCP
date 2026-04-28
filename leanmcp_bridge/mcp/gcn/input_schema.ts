import { Optional, SchemaConstraint } from "@leanmcp/core";


export class EmptyInput {}

export class FetchGcnCircularsInput {
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

export class SearchGcnCircularsInput {
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

export class FetchAndCheckCircularForGrbInput {
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

export class CheckForGrbRegexInput {
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