import { expect, test, type Page } from '@playwright/test'
import { api, login } from './helpers'

interface Paged<T> { results: T[] }

async function overflow(page: Page): Promise<{ doc: number; view: number; widest: string }> {
  return page.evaluate(() => {
    const view = window.innerWidth
    let widest = ''
    let max = 0
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      const r = el.getBoundingClientRect()
      if (r.right > max && r.width > 0) {
        // ignore elements that scroll internally (tables inside overflow-x containers)
        let p: Element | null = el.parentElement
        let clipped = false
        while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { clipped = true; break } p = p.parentElement }
        if (!clipped) { max = r.right; widest = `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)}` }
      }
    }
    return { doc: document.documentElement.scrollWidth, view, widest }
  })
}

for (const width of [360, 768]) {
  test(`no page scrolls sideways at ${width}px wide`, async ({ page }) => {
    test.setTimeout(240_000)
    await page.setViewportSize({ width, height: 800 })
    await login(page, 'super-admin')
    const tx = (await api<Paged<{ id: number }>>(page, '/transactions/?page_size=1')).results[0]!
    const account = (await api<Paged<{ id: number }>>(page, '/accounts/?page_size=1')).results[0]!
    const cases = (await api<Paged<{ id: number }>>(page, '/cases/?page_size=1')).results[0]!
    const routes = ['/dashboard', '/analytics', '/transactions', `/transactions/${tx.id}`, `/accounts/${account.id}`, `/accounts/${account.id}/behavior`, `/accounts/${account.id}/graph`, '/imports', '/imports/new',
      '/detection', '/graph', '/duplicates', '/risk', '/alerts', '/cases', `/cases/${cases.id}`, '/models', '/users', '/audit']
    const bad: string[] = []
    for (const path of routes) {
      await page.goto(path)
      await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
      await page.waitForLoadState('networkidle')
      const o = await overflow(page)
      if (o.doc > o.view + 1) bad.push(`${path}: page is ${o.doc}px wide in a ${o.view}px window (widest unclipped: ${o.widest})`)
    }
    console.log(`\nOVERFLOW at ${width}px\n` + (bad.join('\n') || 'none'))
    expect(bad).toEqual([])
  })
}

test('at phone width the main content gets most of the screen (the menu does not permanently take a third of it)', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await login(page, 'financial-analyst')
  const main = await page.locator('main').boundingBox()
  expect(main!.width).toBeGreaterThan(360 * 0.85)
})
