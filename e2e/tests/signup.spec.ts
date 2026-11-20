import { expect, test } from '@playwright/test'
import { goto, login } from './helpers'

const password = () => process.env.E2E_PASSWORD!

test.describe('self-registration, approval and password reset', () => {
  test('the register page validates, then tells the visitor to check their email', async ({ page }) => {
    await page.goto('/register')
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByText('Enter your name')).toBeVisible()
    await page.getByLabel('Full name').fill('Asha Rao')
    await page.getByLabel('Work email').fill(`asha.${Date.now()}@example.com`)
    await page.getByLabel('Password', { exact: true }).fill('Correct-Horse-Battery-9')
    await page.getByLabel('Repeat password').fill('Correct-Horse-Battery-9')
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByText('You must accept the terms')).toBeVisible()
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
    await expect(page.getByText(/administrator has to approve/)).toBeVisible()
  })

  test('a weak password is rejected by the server and shown on the field', async ({ page }) => {
    await page.goto('/register')
    await page.getByLabel('Full name').fill('Weak Pass')
    await page.getByLabel('Work email').fill(`weak.${Date.now()}@example.com`)
    await page.getByLabel('Password', { exact: true }).fill('password1234')
    await page.getByLabel('Repeat password').fill('password1234')
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByText(/too common/i)).toBeVisible()
  })

  test('landing page offers Create account and the login page links to sign-up and password reset', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Create account' }).click()
    await expect(page).toHaveURL(/\/register$/)
    await page.goto('/login')
    await expect(page.getByRole('link', { name: 'Forgot your password?' })).toBeVisible()
    await page.getByRole('link', { name: 'Create an account' }).click()
    await expect(page).toHaveURL(/\/register$/)
  })

  test('someone who has not confirmed their email, or is not approved yet, cannot sign in and is told why', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill('e2e-unverified@example.com')
    await page.getByLabel('Password').fill(password())
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toContainText('Confirm your email address first')
    await expect(page.getByRole('button', { name: 'Resend the confirmation email' })).toBeVisible()
    await page.getByLabel('Email').fill('e2e-pending@example.com')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toContainText('administrator still has to approve')
    await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0)
  })

  test('a wrong password reveals nothing about the account state', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill('e2e-pending@example.com')
    await page.getByLabel('Password').fill('not-the-right-password-1')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.')
  })

  test('verify and reset pages refuse bad links', async ({ page }) => {
    await page.goto('/verify-email?token=not-a-real-token')
    await expect(page.getByRole('alert')).toContainText('invalid or has expired')
    await page.goto('/reset-password')
    await expect(page.getByRole('alert')).toContainText('incomplete')
    await page.goto('/reset-password?uid=MQ&token=bogus')
    await page.getByLabel('New password', { exact: true }).fill('Brand-New-Passphrase-42')
    await page.getByLabel('Repeat password').fill('Brand-New-Passphrase-42')
    await page.getByRole('button', { name: 'Change password' }).click()
    await expect(page.getByRole('alert')).toContainText('invalid or has expired')
  })

  test('forgot password answers the same for any address', async ({ page }) => {
    await page.goto('/forgot-password')
    await page.getByLabel('Email').fill('nobody-at-all@example.com')
    await page.getByRole('button', { name: 'Send reset link' }).click()
    await expect(page.getByText(/If an account exists for/)).toBeVisible()
  })

  test('an administrator approves a waiting user with a role, and that user can then sign in', async ({ page, browser }) => {
    await login(page, 'super-admin')
    await goto(page, 'User Management')
    const card = page.getByRole('region', { name: /Waiting for approval/ })
    await expect(card).toBeVisible()
    await expect(card.getByText('e2e-pending@example.com')).toBeVisible()
    await expect(card.getByText('e2e-unverified@example.com')).toBeVisible()
    // the unconfirmed address cannot be approved yet
    await card.getByLabel('Role for e2e-unverified@example.com').selectOption('auditor')
    await expect(card.getByRole('button', { name: 'Approve e2e-unverified@example.com' })).toBeDisabled()
    await card.getByLabel('Role for e2e-pending@example.com').selectOption('auditor')
    await card.getByRole('button', { name: 'Approve e2e-pending@example.com' }).click()
    await expect(page.getByText('Account approved')).toBeVisible()
    await expect(card.getByText('e2e-pending@example.com')).toHaveCount(0)

    const ctx = await browser.newContext()
    const p = await ctx.newPage()
    await p.goto('/login')
    await p.getByLabel('Email').fill('e2e-pending@example.com')
    await p.getByLabel('Password').fill(password())
    await p.getByRole('button', { name: 'Sign in' }).click()
    await expect(p).toHaveURL(/\/dashboard$/)
    await expect(p.getByRole('navigation', { name: 'Main' })).toBeVisible()
    await ctx.close()
  })
})
