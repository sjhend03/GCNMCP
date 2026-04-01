import { Optional, SchemaConstraint, Tool } from "@leanmcp/core";
import { callPythonTool } from "../../bridge/python_bridge.js";

class EmptyInput {}

class CheckForGrbRegexInput {
    @SchemaConstraint({
        description: "Raw circular file index",
        minimum: 0,
    })
    index!: number;

    @Optional()
    @SchemaConstraint({
        description: "Optional direction to check for the regex. If not provided, checks both directions.",
    })
    data_dir?: string;
}

export class GcnService {
    @Tool({
        description: "Simple TypeScript ping for testing LeanMCP",
    })
    async ping(_: EmptyInput) {
        return {
            message: "pong from typescript",
        }
    }

    @Tool({
        description: "Simple Python ping for testing the TS to python bridge.",
        inputClass: EmptyInput,
    })
    async ping_python(_: EmptyInput) {
        return await callPythonTool("ping_python", {});
    }

    @Tool({
        description: "Check wether a circular subject contains a GRB identifier."
    })
    async check_for_grb_regex(input: CheckForGrbRegexInput) {
        return await callPythonTool("check_for_grb_regex", {
            index: input.index,
            data_dir: input.data_dir,
        });
    }
}