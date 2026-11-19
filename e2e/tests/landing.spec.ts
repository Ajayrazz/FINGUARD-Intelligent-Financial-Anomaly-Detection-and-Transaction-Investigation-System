import { expect, test } from '@playwright/test'
import { credentials } from './helpers'

test.describe('public landing page and entry to the app', () => {
  test('anyone can open the landing page without signing in', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Spot anomalies')
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible()
  })

  test('the landing page has no sideways scroll on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 })
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    const o = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, view: window.innerWidth }))
    expect(o.doc).toBeLessThanOrEqual(o.view + 1)
  })

  test('Sign in on the landing page leads to the login page, then the dashboard with charts', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Email').fill(credentials('super-admin').email)
    await page.getByLabel('Password').fill(credentials('super-admin').password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
    await expect(page.getByRole('img', { name: /3D bar chart of open alerts/ })).toBeVisible()
    await expect(page.locator('canvas').first()).toBeVisible()
  })

  test('app pages still require sign-in', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })
})
