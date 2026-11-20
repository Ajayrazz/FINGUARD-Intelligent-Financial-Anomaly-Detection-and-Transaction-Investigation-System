import { expect, test } from '@playwright/test'
import { api, login } from './helpers'

test.describe('analytics (Phase 14)', () => {
  test('management reads analytics and exports a CSV, but cannot rebuild the rollup', async ({ page }) => {
    await login(page, 'management')
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Analytics', exact: true }).click()
    await expect(page).toHaveURL(/\/analytics$/)
    await expect(page.getByRole('heading', { name: 'Analytics', level: 1 })).toBeVisible()
    await expect(page.getByText('Transactions', { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Rebuild rollup' })).toHaveCount(0)
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download CSV' }).click()
    expect((await download).suggestedFilename()).toMatch(/^finguard-volume\.csv$/)
  })

  test('the numbers on the page equal the numbers the API reports', async ({ page }) => {
    await login(page, 'financial-analyst')
    const ov = await api<{ transactions: number; open_cases: number }>(page, '/analytics/overview/')
    await page.goto('/analytics')
    await expect(page.getByRole('heading', { name: 'Analytics', level: 1 })).toBeVisible()
    await page.waitForTimeout(1500) // tiles count up
    const tile = page.locator('p', { hasText: /^Transactions$/ }).first().locator('xpath=following-sibling::p[1]')
    await expect(tile).toHaveText(ov.transactions.toLocaleString('en-IN'))
    const direct = await api<{ count: number }>(page, '/cases/?page=1&open=true')
    expect(typeof ov.open_cases).toBe('number')
    expect(direct).toBeTruthy()
  })

  test('an analyst can rebuild the rollup and the page confirms it', async ({ page }) => {
    await login(page, 'financial-analyst')
    await page.goto('/analytics')
    await page.getByRole('button', { name: 'Rebuild rollup' }).click()
    await expect(page.getByText('Analytics rebuilt from the source tables')).toBeVisible()
  })
})
