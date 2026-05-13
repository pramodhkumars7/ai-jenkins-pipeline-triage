const { test, expect } = require('@playwright/test');
const path = require('path');

const LOGIN = `file://${path.resolve(__dirname, '../src/login.html')}`;

test.describe('Login Page', () => {

  test('should show Sign In button', async ({ page }) => {
    await page.goto(LOGIN);
    // FAIL: button text is "Login", not "Sign In"
    const btn = page.getByRole('button', { name: 'Sign In' });
    await expect(btn).toBeVisible();
  });

  test('should redirect to dashboard on valid login', async ({ page }) => {
    await page.goto(LOGIN);
    await page.fill('#username', 'admin');
    await page.fill('#password', 'password123');
    await page.click('#login-btn');

    // FAIL: file:// protocol navigation won't trigger location.href correctly in all cases,
    // and we check for a #dashboard element that doesn't exist on dashboard.html
    await expect(page.locator('#dashboard-header')).toBeVisible({ timeout: 3000 });
  });

  test('should show error for wrong credentials', async ({ page }) => {
    await page.goto(LOGIN);
    await page.fill('#username', 'wronguser');
    await page.fill('#password', 'wrongpass');
    await page.click('#login-btn');

    // FAIL: error msg id is "error-msg", not "auth-error-banner"
    await expect(page.locator('#auth-error-banner')).toBeVisible();
  });

});
