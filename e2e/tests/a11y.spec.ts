import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { api, login } from './helpers'

interface Paged<T> { results: T[] }

async function scan(page: Page, label: string) {
  await page.waitForLoadState('networkidle')
  // entrance animations change opacity/position; scan the settled page (endless decorative loops are ignored)
  await page.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations !== Infinity).map((a) => a.finished.catch(() => undefined))))
  const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  return r.violations.map((v) => ({ page: label, id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, sample: v.nodes[0]?.target.join(' ') ?? '' }))
}

test('every page, as the Super Admin, has no WCAG 2.1 A/AA violations that axe can detect', async ({ page }) => {
  test.setTimeout(240_000)
  await login(page, 'super-admin')
  const tx = (await api<Paged<{ id: number; sender: string }>>(page, '/transactions/?page_size=1')).results[0]!
  const account = (await api<Paged<{ id: number }>>(page, '/accounts/?page_size=1')).results[0]!
  const cases = (await api<Paged<{ id: number }>>(page, '/cases/?page_size=1')).results[0]!
  const alerts = (await api<Paged<{ id: number }>>(page, '/alerts/?page_size=1')).results[0]!
  const routes: [string, string][] = [
    ['login', '/login'], ['dashboard', '/dashboard'], ['analytics', '/analytics'], ['transactions', '/transactions'], ['transaction detail', `/transactions/${tx.id}`], ['account', `/accounts/${account.id}`],
    ['account behaviour', `/accounts/${account.id}/behavior`], ['account network', `/accounts/${account.id}/graph`], ['imports', '/imports'], ['import wizard', '/imports/new'],
    ['detection', '/detection'], ['graph', '/graph'], ['duplicates', '/duplicates'], ['risk', '/risk'], ['alerts', `/alerts?open=${alerts.id}`], ['cases', '/cases'],
    ['case workspace', `/cases/${cases.id}`], ['models', '/models'], ['users', '/users'], ['audit', '/audit'],
  ]
  const found: Awaited<ReturnType<typeof scan>> = []
  for (const [label, path] of routes) {
    if (label === 'login') continue // scanned in its own test (needs a signed-out browser)
    await page.goto(path)
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
    found.push(...(await scan(page, label)))
  }
  console.log('\nAXE VIOLATIONS\n' + (found.length ? found.map((f) => `${f.impact?.padEnd(8)} ${f.page.padEnd(20)} ${f.id.padEnd(28)} x${f.nodes}  ${f.sample.slice(0, 70)}`).join('\n') : 'none'))
  expect(found, 'axe violations').toEqual([])
})

test('the sign-in and account pages have no WCAG 2.1 A/AA violations', async ({ page }) => {
  for (const [label, path] of [['login', '/login'], ['register', '/register'], ['forgot password', '/forgot-password'], ['verify email', '/verify-email?token=x'], ['reset password', '/reset-password?uid=MQ&token=x']] as const) {
    await page.goto(path)
    expect(await scan(page, label), label).toEqual([])
  }
})

test('the public landing page has no WCAG 2.1 A/AA violations', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  expect(await scan(page, 'landing')).toEqual([])
})
