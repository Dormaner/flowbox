// 截图助手：node shot.mjs <输出> [multi|detail]
import puppeteer from 'puppeteer-core'

const out = process.argv[2] || 'shot.png'
const mode = process.argv[3] || 'multi'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: 'new',
  defaultViewport: { width: 1500, height: 950 },
})
const page = await browser.newPage()
page.on('dialog', (d) => (d.type() === 'prompt' ? d.accept('财务环节') : d.accept()))
await page.goto(process.env.FB_URL || 'http://localhost:5173/', { waitUntil: 'networkidle2' })
await page.waitForSelector('.card', { timeout: 20000 })
await sleep(600)

if (mode === 'multi') {
  const cards = await page.$$('.card')
  await cards[0].click()
  await page.keyboard.down('Control')
  await cards[1].click()
  await page.keyboard.up('Control')
  await sleep(400)
  await page.click('.selbar button[title="把选中的卡片装进一个分组框"]').catch(() => {})
  await sleep(500)
} else {
  const cards = await page.$$('.card')
  for (const c of cards) {
    await c.click()
    await sleep(300)
    if (await page.$('.imgcell')) break
  }
  await sleep(300)
  await page.click('.drawer .dh button[title*="浮动"]').catch(() => {})
  await sleep(400)
}

await page.screenshot({ path: out })
await browser.close()
console.log('saved', out)
