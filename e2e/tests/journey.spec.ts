import { expect, test } from '@playwright/test'
import { api, goto, login } from './helpers'

type Paged<T> = { results: T[] }

test.describe('cross-page journeys (Phase 13)', () => {
  test('analyst: dashboard → transactions → transaction → account', async ({ page }) => {
    await login(page, 'financial-analyst')
    await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
    await goto(page, 'Transactions')
    await expect(page.getByRole('heading', { name: 'Transactions', level: 1 })).toBeVisible()
    const tx = (await api<Paged<{ id: number; sender: number }>>(page, '/transactions/?page_size=1')).results[0]!
    await page.goto(`/transactions/${tx.id}`)
    await expect(page).toHaveURL(new RegExp(`/transactions/${tx.id}$`))
    await page.goto(`/accounts/${tx.sender}`)
    await expect(page).toHaveURL(new RegExp(`/accounts/${tx.sender}$`))
  })

  test('investigator: alerts → open an alert → cases', async ({ page }) => {
    await login(page, 'fraud-investigator')
    await goto(page, 'Alerts')
    await expect(page.getByRole('heading', { name: 'Alerts', level: 1 })).toBeVisible()
    await page.getByRole('button', { name: /^\d+$/ }).first().click()
    await expect(page.getByRole('region').first()).toBeVisible()
    await goto(page, 'Investigations')
    await expect(page.getByRole('heading', { name: 'Investigations', level: 1 })).toBeVisible()
    const c = (await api<Paged<{ id: number }>>(page, '/cases/?page=1')).results[0]
    if (c) {
      await page.goto(`/cases/${c.id}`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    }
  })

  test('auditor: audit logs record the sign-in that just happened', async ({ page }) => {
    await login(page, 'auditor')
    await goto(page, 'Audit Logs')
    await expect(page.getByRole('heading', { name: 'Audit logs', level: 1 })).toBeVisible()
    await expect(page.getByText('auth.login').first()).toBeVisible()
  })
})
