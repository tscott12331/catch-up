import { defineConfig, devices } from "@playwright/test";

const backendUrl = "http://127.0.0.1:8010";
const frontendUrl = "http://127.0.0.1:3100";
const externalServers = process.env.CATCH_UP_E2E_EXTERNAL_SERVERS === "1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: frontendUrl,
    trace: "retain-on-failure",
  },
  webServer: externalServers ? undefined : [
    {
      command: "uv run --project backend python backend/run.py",
      cwd: "..",
      url: `${backendUrl}/ready`,
      timeout: 30_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        ENVIRONMENT: "test",
        HOST: "127.0.0.1",
        PORT: "8010",
        FRONTEND_ORIGINS: frontendUrl,
        DEMO_JOB_DURATION_SECONDS: "10",
      },
    },
    {
      command: "bun run dev -- --hostname 127.0.0.1 --port 3100",
      url: frontendUrl,
      timeout: 45_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        NEXT_PUBLIC_API_BASE_URL: backendUrl,
        NEXT_DIST_DIR: ".next-e2e",
      },
    },
  ],
});
