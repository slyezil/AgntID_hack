import { expect, test } from "@playwright/test";

test("mobile conversation reconnects to durable SSE and submits once on a double tap", async ({ page, request }) => {
  await page.goto("/");
  await page.getByLabel("Invitation code").fill("mock-invitation-code");
  await page.getByRole("button", { name: "Open workspace" }).click();

  const composer = page.getByLabel("Message CounterOffer");
  await composer.fill("Quote 200 small cartons");
  await page.getByRole("button", { name: "Send message" }).dblclick();

  await expect(page.getByText("Your draft is ready for review.")).toBeVisible();
  await expect(page.getByText("Your draft is ready for review.")).toHaveCount(1);
  await expect(page.getByText("Ready for your next request.")).toBeVisible();

  const state = await (await request.get("http://127.0.0.1:8000/test-state")).json() as {
    turnPosts: number;
    eventConnections: number;
    lastEventId: string;
  };
  expect(state.turnPosts).toBe(1);
  expect(state.eventConnections).toBeGreaterThanOrEqual(2);
  expect(state.lastEventId).toBe("1");

  const viewport = await page.evaluate(() => ({
    width: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(viewport.documentWidth).toBeLessThanOrEqual(viewport.width);
});
