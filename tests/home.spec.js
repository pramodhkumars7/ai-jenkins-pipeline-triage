const { test, expect } = require('@playwright/test');
const path = require('path');

const HOME = `file://${path.resolve(__dirname, '../src/index.html')}`;

test.describe('Home Page', () => {

  test('should have correct page title', async ({ page }) => {
    await page.goto(HOME);
    // FAIL: actual title is "Home | MyApp", not "MyApp Dashboard"
    await expect(page).toHaveTitle('MyApp Dashboard');
  });

  test('should show Sign Up Now button', async ({ page }) => {
    await page.goto(HOME);
    // FAIL: button text is "Get Started", not "Sign Up Now"
    const btn = page.getByRole('link', { name: 'Sign Up Now' });
    await expect(btn).toBeVisible();
  });

  test('should display 4 feature cards', async ({ page }) => {
    await page.goto(HOME);
    // FAIL: there are only 3 cards (.card), not 4
    const cards = page.locator('.card');
    await expect(cards).toHaveCount(4);
  });

});
