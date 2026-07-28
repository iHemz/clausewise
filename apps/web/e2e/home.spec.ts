import { expect, test } from '@playwright/test';

// E2E covers the money path only — if the uploader does not render, nothing
// else about the product matters.
test('the home page renders the uploader', async ({ page }) => {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: /Every risky clause, flagged and quoted/i }),
  ).toBeVisible();
  await expect(page.getByText('Drop a contract here')).toBeVisible();
});
