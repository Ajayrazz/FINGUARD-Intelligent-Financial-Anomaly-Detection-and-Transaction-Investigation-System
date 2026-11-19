import { expect, test } from '@playwright/test'
import { credentials, login } from './helpers'

test.describe('sign in and session', () => {
  test('shows validation messages for an empty form and an error for wrong credentials', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText('Email is required')).toBeVisible()
    await expect(page.getByText('Password is required')).toBeVisible()
    await page.getByLabel('Email').fill(credentials('auditor').email)
    await page.getByLabel('Password').fill('definitely-not-the-password')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText('Invalid email or password.')).toBeVisible()
  })

  test('signs in, keeps the session across a reload, and signs out', async ({ page }) => {
    await login(page, 'financial-analyst')
    await expect(page.getByText('E2E Financial Analyst')).toBeVisible()
    await page.reload()
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible() // the httpOnly refresh cookie restores the session
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
    await page.goto('/alerts')
    await expect(page).toHaveURL(/\/login/) // signed out: protected pages redirect
  })

  test('returns to the page that was asked for after signing in', async ({ page }) => {
    await page.goto('/alerts')
    await expect(page).toHaveURL(/\/login/)
    await page.getByLabel('Email').fill(credentials('fraud-investigator').email)
    await page.getByLabel('Password').fill(credentials('fraud-investigator').password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/alerts$/)
    await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible()
  })

  test('the access token is not stored in the browser (memory only)', async ({ page }) => {
    await login(page, 'auditor')
    const storage = await page.evaluate(() => JSON.stringify({ l: { ...localStorage }, s: { ...sessionStorage } }))
    expect(storage).not.toMatch(/eyJ[A-Za-z0-9_-]{10,}/) // no JWT in localStorage / sessionStorage
    const cookies = await page.context().cookies()
    const refresh = cookies.find((c) => c.name === 'fg_refresh')
    expect(refresh?.httpOnly).toBe(true)
    expect(refresh?.sameSite).toBe('Strict')
  })
})
