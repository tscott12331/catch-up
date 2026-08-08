import { readFile } from "node:fs/promises";

const target = process.argv[2];
if (!target) throw new Error("Expected the generated contract path.");

const generated = await new Response(Bun.stdin.stream()).text();
const tracked = await readFile(target, "utf8");

if (generated !== tracked) {
  console.error(`Generated OpenAPI types are stale: ${target}`);
  process.exitCode = 1;
}
