import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { PythonBridgeRequest, PythonBridgeResponse } from "./bridge_types.js";
import {
  PythonBridgeError,
  PythonBridgeLaunchError,
  PythonBridgeParseError,
} from "./bridge_errors.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export async function callPythonTool(
  tool: string,
  args: Record<string, unknown> = {}
): Promise<unknown> {
  const pythonBin = process.env.GCN_PYTHON_BIN ?? "python";
  const bridgeScript =
    process.env.GCN_PYTHON_BRIDGE_SCRIPT ?? resolve(__dirname, "../py_bridge.py");

  const payload: PythonBridgeRequest = {
    tool,
    arguments: args,
  };

  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(pythonBin, [bridgeScript], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.setEncoding("utf-8");
    child.stderr.setEncoding("utf-8");

    child.stdout.on("data", (data) => {
      stdout += data;
    });

    child.stderr.on("data", (data) => {
      stderr += data;
    });

    child.on("error", (err) => {
      rejectPromise(
        new PythonBridgeLaunchError(
          `Failed to launch Python process: ${err.message}`
        )
      );
    });

    child.on("close", (code) => {
      const out = stdout.trim();
      const err = stderr.trim();

      if (!out) {
        rejectPromise(
          new PythonBridgeLaunchError(
            `Python process exited with code ${code} and no output. Stderr: ${err}`
          )
        );
        return;
      }

      let parsed: PythonBridgeResponse;
      try {
        parsed = JSON.parse(out) as PythonBridgeResponse;
      } catch (parseErr) {
        rejectPromise(
          new PythonBridgeParseError(
            `Failed to parse Python output as JSON. Output: ${out}. Stderr: ${err}. Parse error: ${(parseErr as Error).message}`
          )
        );
        return;
      }

      if (!parsed.ok) {
        rejectPromise(new PythonBridgeError(`Python tool error: ${parsed.error}`));
        return;
      }

      resolvePromise(parsed.result);
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}