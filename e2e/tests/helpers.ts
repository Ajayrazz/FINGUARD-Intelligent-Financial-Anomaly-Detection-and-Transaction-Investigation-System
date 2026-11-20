import { expect, type Page } from '@playwright/test'

export const ROLES = ['super-admin', 'financial-analyst', 'fraud-investigator', 'auditor', 'management'] as const
export type Role = (typeof ROLES)[number]

export function credentials(role: Role): { email: string; password: string } {
  const password = process.env.E2E_PASSWORD
  if (!password) throw new Error('E2E_PASSWORD is not set (see e2e/README.md)')
  return { email: `e2e-${role}@example.com`, password }
}

/** Sign in through the real login form and wait until the signed-in layout is on screen. */
export async function login(page: Page, role: Role, startAt = '/login'): Promise<void> {
  await page.goto(startAt)
  await page.getByLabel('Email').fill(credentials(role).email)
  await page.getByLabel('Password').fill(credentials(role).password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
  await page.waitForLoadState('networkidle') // the dashboard's own requests finish before tests call the API directly
}

/** Navigate inside the SPA through the sidebar (no full page load, so no extra token refresh). */
export async function goto(page: Page, label: string): Promise<void> {
  const nav = page.getByRole('navigation', { name: 'Main' })
  // menu links carry a one-line hint after the label, so match the start of the accessible name
  const link = nav.getByRole('link', { name: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\s|$)`) })
  if (!(await link.isVisible())) {
    // the page lives inside one of the grouped menus: open them until the link shows
    for (const group of await nav.getByRole('button', { expanded: false }).filter({ hasText: /▾/ }).all()) {
      await group.click()
      const shown = await link.waitFor({ state: 'visible', timeout: 800 }).then(() => true, () => false)
      if (shown) break
      await page.keyboard.press('Escape')
    }
  }
  await link.click()
}

/** Call the API as the signed-in user (token from the refresh cookie; nothing is stored). */
export async function api<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (p) => {
    const t = (await (await fetch('/api/v1/auth/refresh/', { method: 'POST', credentials: 'same-origin' })).json()) as { access: string }
    const res = await fetch(`/api/v1${p}`, { headers: { Authorization: `Bearer ${t.access}` } })
    return res.json()
  }, path) as Promise<T>
}
