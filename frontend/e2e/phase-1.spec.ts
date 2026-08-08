import { expect, test } from "@playwright/test";

const backendUrl = "http://127.0.0.1:8010";
const demoPath = "/repositories/acme/checkout-service";
const answer = "The checkout flow starts in the API layer, validates the cart, and coordinates payment with inventory.";

test.beforeEach(async ({ request }) => {
  const response = await request.post(`${backendUrl}/__test/reset`);
  expect(response.status()).toBe(204);
});

async function openDemoWorkspace(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try the demo repository/i }).click();
  await expect(page).toHaveURL(new RegExp(`${demoPath}$`));
  await expect(page.getByRole("heading", { name: "Ask the codebase" })).toBeVisible();
}

test("connects the demo, exposes progress, and completes indexing", async ({ page }) => {
  await openDemoWorkspace(page);
  await expect(page.getByText(/Indexing \d+%/)).toBeVisible();
  await expect(page.getByText("Indexed just now")).toBeVisible();
});

test("streams an answer and focuses its cited source lines", async ({ page }) => {
  await openDemoWorkspace(page);
  const question = "How does the checkout flow work?";
  await page.getByPlaceholder("Ask anything about this repository...").fill(question);
  await page.getByRole("button", { name: "Send question" }).click();

  await expect(page.getByText(answer)).toBeVisible();
  const citation = page.getByRole("button", { name: /src\/api\/checkout\.ts/ }).last();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(page.locator('[data-line-number="5"]')).toHaveClass(/highlighted/);
  await expect(page.locator('[data-line-number="20"]')).toHaveClass(/highlighted/);
});

test("starts a fresh conversation", async ({ page }) => {
  await openDemoWorkspace(page);
  const question = "What happens when inventory is unavailable?";
  await page.getByPlaceholder("Ask anything about this repository...").fill(question);
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText(answer)).toBeVisible();

  await page.getByRole("button", { name: /new chat/i }).click();
  await expect(page.getByText(question)).toHaveCount(0);
  await expect(page.getByPlaceholder("Ask anything about this repository...")).toHaveValue("");
});

test("recovers after a stream failure with a subsequent answer", async ({ page }) => {
  await openDemoWorkspace(page);
  await page.getByPlaceholder("Ask anything about this repository...").fill("__stream_error__");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("The answer stream could not be completed.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();

  await page.getByPlaceholder("Ask anything about this repository...").fill("How does checkout work?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText(answer)).toBeVisible();
});

test("shows a recoverable state for an unknown repository", async ({ page }) => {
  await page.goto("/repositories/unknown/repository");
  await expect(page.getByRole("heading", { name: "We couldn’t open this repository." })).toBeVisible();
  await expect(page.getByText("Repository was not found.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry workspace" })).toBeVisible();
});

test("shows a backend-unavailable state", async ({ page }) => {
  await page.route("**/api/repositories/**", (route) => route.abort("connectionrefused"));
  await page.goto(demoPath);
  await expect(page.getByRole("heading", { name: "We couldn’t open this repository." })).toBeVisible();
  await expect(page.getByText("The backend is unavailable. Check that FastAPI is running.")).toBeVisible();
});
