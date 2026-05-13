const { test, expect } = require('@playwright/test');
const path = require('path');

const DASHBOARD = `file://${path.resolve(__dirname, '../src/dashboard.html')}`;

test.describe('Dashboard Page', () => {

  test('should display revenue chart section', async ({ page }) => {
    await page.goto(DASHBOARD);
    // FAIL: there is no .revenue-chart element on this page
    await expect(page.locator('.revenue-chart')).toBeVisible();
  });

  test('should show correct active sessions count', async ({ page }) => {
    await page.goto(DASHBOARD);
    const sessions = await page.locator('#active-sessions').textContent();
    // FAIL: actual value is "87", not "120"
    expect(sessions.trim()).toBe('120');
  });

  test('should have 5 rows in the activity table', async ({ page }) => {
    await page.goto(DASHBOARD);
    const rows = page.locator('#recent-activity tbody tr');
    // FAIL: there are only 3 rows, not 5
    await expect(rows).toHaveCount(5);
  });

  test('should show logout button in nav', async ({ page }) => {
    await page.goto(DASHBOARD);
    // FAIL: there is no logout button in the nav
    await expect(page.getByRole('button', { name: 'Logout' })).toBeVisible();
  });

});
