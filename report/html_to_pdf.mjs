// Prints an HTML file to A4 PDF with headless Chromium (Playwright from e2e/node_modules).
// Usage: node report/html_to_pdf.mjs <in.html> <out.pdf>
import { createRequire } from 'node:module'
const require = createRequire(new URL('../e2e/package.json', import.meta.url))
const { chromium } = require('@playwright/test')

const [, , input, output] = process.argv
const browser = await chromium.launch()
const page = await browser.newPage()
await page.goto('file://' + input, { waitUntil: 'load' })
await page.pdf({ path: output, format: 'A4', printBackground: true, preferCSSPageSize: true })
await browser.close()
