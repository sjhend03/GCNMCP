import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export class GcnHttpMcpClient {
  private readonly pythonBin = process.env.GCN_PYTHON_BIN ?? "python";
  private readonly bridgeScript =
    process.env.GCN_PYTHON_BRIDGE_SCRIPT ??
    resolve(__dirname, "python_tool_bridge.py");

  async callTool(name: string, arguments_: Record<string, unknown>) {
    const payload = JSON.stringify({
      name,
      arguments: arguments_,
    });

    return new Promise<unknown>((resolvePromise, rejectPromise) => {
      const child = spawn(this.pythonBin, [this.bridgeScript], {
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      child.stdout.setEncoding("utf-8");
      child.stderr.setEncoding("utf-8");

      child.stdout.on("data", (chunk) => {
        stdout += chunk;
      });

      child.stderr.on("data", (chunk) => {
        stderr += chunk;
      });

      child.on("error", (err) => {
        rejectPromise(new Error(`Failed to launch Python bridge: ${err.message}`));
      });

      child.on("close", (code) => {
        const out = stdout.trim();

        if (!out) {
          rejectPromise(
            new Error(
              `Python bridge returned empty stdout (exit=${code}). stderr: ${stderr.trim()}`
            )
          );
          return;
        }

        let parsed: { result?: unknown; error?: string };
        try {
          parsed = JSON.parse(out);
        } catch (err) {
          rejectPromise(
            new Error(
              `Invalid JSON from Python bridge (exit=${code}): ${String(err)}\nstdout: ${out}\nstderr: ${stderr.trim()}`
            )
          );
          return;
        }

        if (code !== 0 || parsed.error) {
          rejectPromise(
            new Error(
              `Python bridge error (exit=${code}): ${parsed.error ?? "unknown"}\nstderr: ${stderr.trim()}`
            )
          );
          return;
        }

        resolvePromise(parsed.result);
      });

      child.stdin.write(payload);
      child.stdin.end();
    });
  }
}
