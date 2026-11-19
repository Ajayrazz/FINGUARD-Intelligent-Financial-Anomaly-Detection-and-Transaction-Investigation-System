import { expect, test } from '@playwright/test'
import { login, type Role } from './helpers'

// The sidebar a role sees: the browser-level check of the permission matrix (the API enforces it independently).
const NAV: Record<Role, string[]> = {
  'super-admin': ['Dashboard', 'Transactions', 'Imports', 'Anomaly Detection', 'Relationship Graph', 'Duplicate Detection', 'Risk Analysis', 'Alerts', 'Investigations', 'Model Performance', 'User Management', 'Audit Logs'],
  'financial-analyst': ['Dashboard', 'Transactions', 'Imports', 'Anomaly Detection', 'Relationship Graph', 'Duplicate Detection', 'Risk Analysis', 'Alerts', 'Investigations', 'Model Performance'],
  'fraud-investigator': ['Dashboard', 'Transactions', 'Imports', 'Anomaly Detection', 'Relationship Graph', 'Duplicate Detection', 'Risk Analysis', 'Alerts', 'Investigations', 'Model Performance'],
  auditor: ['Dashboard', 'Transactions', 'Imports', 'Anomaly Detection', 'Relationship Graph', 'Duplicate Detection', 'Risk Analysis', 'Alerts', 'Investigations', 'Model Performance', 'User Management', 'Audit Logs'],
  management: ['Dashboard'],
}

for (const [role, expected] of Object.entries(NAV) as [Role, string[]][]) {
  test(`the ${role} sees exactly the pages their role allows`, async ({ page }) => {
    await login(page, role)
    const nav = page.getByRole('navigation', { name: 'Main' })
    const links = await nav.getByRole('link', { name: 'Dashboard', exact: true }).allInnerTexts()
    for (const group of await nav.getByRole('button', { expanded: false }).filter({ hasText: /▾/ }).all()) {
      await group.click()
      links.push(...(await nav.locator('[data-group-panel] a').locator('span.font-medium').allInnerTexts()))
      await page.keyboard.press('Escape')
    }
    expect(links.filter((l) => l !== 'FinGuard').sort()).toEqual([...expected].sort()) // order is by menu group
  })
}

test('typing the address of a page the role may not open shows Access denied, not the page', async ({ page }) => {
  await login(page, 'management')
  await page.getByRole('navigation', { name: 'Main' }).waitFor()
  await page.evaluate(() => { window.history.pushState({}, '', '/alerts'); window.dispatchEvent(new PopStateEvent('popstate')) })
  await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
  await expect(page.getByRole('button', { name: /acknowledge|close alert/i })).toHaveCount(0)
})

test('the API refuses what the screen hides: management cannot read alert records', async ({ page, request }) => {
  await login(page, 'management')
  const token = await page.evaluate(async () => (await (await fetch('/api/v1/auth/refresh/', { method: 'POST', credentials: 'same-origin' })).json()).access as string)
  const res = await request.get('/api/v1/alerts/', { headers: { Authorization: `Bearer ${token}` } })
  expect(res.status()).toBe(403)
  const summary = await request.get('/api/v1/alerts/summary/', { headers: { Authorization: `Bearer ${token}` } })
  expect(summary.status()).toBe(200)
})
