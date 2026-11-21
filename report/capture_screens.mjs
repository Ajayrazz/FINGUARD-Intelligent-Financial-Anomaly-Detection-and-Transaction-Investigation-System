// Captures real screenshots of the running development stack for the project report.
// Usage: FG_REFRESH=<refresh token> node report/capture_screens.mjs   (stack on :5173, run from the repo root)
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
const require = createRequire(new URL('../e2e/package.json', import.meta.url))
const { chromium } = require('@playwright/test')

const BASE = 'http://localhost:5173'
const OUT = fileURLToPath(new URL('./screens/', import.meta.url))
const TX = process.env.FG_TX ?? '3305342'
const ACC = process.env.FG_ACC ?? '4707298'
const BEH_ACC = process.env.FG_BEH_ACC ?? ACC
const ONLY = process.env.FG_ONLY ? process.env.FG_ONLY.split(',') : null

const pub = [
  ['01-landing', '/'],
  ['02-login', '/login'],
  ['03-register', '/register'],
  ['04-forgot-password', '/forgot-password'],
]
const priv = [
  ['05-dashboard', '/dashboard', 4500],
  ['06-analytics', '/analytics', 4500],
  ['07-transactions', '/transactions', 2500],
  ['08-transaction-detail', `/transactions/${TX}`, 3500],
  ['09-imports', '/imports', 2000],
  ['10-import-wizard', '/imports/new', 2000],
  ['11-detection', '/detection', 2500],
  ['12-model-performance', '/models', 3500],
  ['13-account-behavior', `/accounts/${BEH_ACC}/behavior`, 3000],
  ['14-graph-overview', '/graph', 3500],
  ['15-relationship-graph', `/accounts/${ACC}/graph`, 4000],
  ['16-duplicates', '/duplicates', 2500],
  ['17-risk-analysis', '/risk', 3500],
  ['18-alerts', '/alerts', 2500],
  ['19-cases', '/cases', 2500],
  ['20-case-detail', '/cases/1', 3000],
  ['21-users', '/users', 2500],
  ['22-audit-logs', '/audit', 2500],
]

const browser = await chromium.launch()
// Personal mailbox addresses of the developers/testers are replaced by example.com addresses in the images.
const redact = (page) =>
  page.evaluate(() => {
    const map = new Map()
    const swap = (t) =>
      t.replace(/[\w.+-]+@gmail\.com/gi, (m) => {
        if (!map.has(m)) map.set(m, `user${map.size + 1}@example.com`)
        return map.get(m)
      })
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeValue = swap(n.nodeValue)
    document.querySelectorAll('input,textarea').forEach((i) => { if (i.value) i.value = swap(i.value) })
  })
const shot = async (page, name, wait) => {
  await page.waitForTimeout(wait)
  await redact(page)
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage: false })
  console.log('saved', name, page.url())
}
const anon = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const p0 = await anon.newPage()
for (const [name, path] of pub.filter(([n]) => !ONLY || ONLY.includes(n))) {
  await p0.goto(BASE + path, { waitUntil: 'networkidle' })
  await shot(p0, name, 2500)
}
await anon.close()

const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await ctx.addCookies([{ name: 'fg_refresh', value: process.env.FG_REFRESH, url: BASE + '/api/v1/auth/', httpOnly: true, sameSite: 'Strict' }])
const page = await ctx.newPage()
for (const [name, path, wait] of priv.filter(([n]) => !ONLY || ONLY.includes(n))) {
  try {
    await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 45000 })
  } catch (e) {
    console.log('networkidle timeout', name)
  }
  if (name === '13-account-behavior') {
    // the synthetic demo history is older than 90 days: widen the window to the largest option
    const sel = page.locator('select').nth(1)
    const n = await sel.locator('option').count()
    await sel.selectOption({ index: n - 1 })
    await page.waitForTimeout(1500)
  }
  await shot(page, name, wait)
}
await browser.close()
