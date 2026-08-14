import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { compile } from "json-schema-to-typescript";

const root = resolve(import.meta.dirname, "..");
const contractPath = resolve(root, "app/_lib/generated/sse-events.json");
const outputPath = resolve(root, "app/_lib/generated/sse-events.ts");
const contract = JSON.parse(await readFile(contractPath, "utf8"));

if (!contract.schema || typeof contract.schema !== "object") {
  throw new Error(`Expected a nested JSON Schema at ${contractPath}`);
}

const generated = await compile(contract.schema, "ChatStreamEvent", {
  bannerComment: [
    "/**",
    " * This file was generated from the backend-owned chat SSE schema.",
    " * Do not make direct changes to this file.",
    " */",
  ].join("\n"),
});

if (process.argv.includes("--check")) {
  const tracked = await readFile(outputPath, "utf8").catch(() => "");
  if (tracked !== generated) {
    console.error(`Generated SSE types are stale: ${outputPath}`);
    process.exitCode = 1;
  }
} else {
  await writeFile(outputPath, generated, "utf8");
}
