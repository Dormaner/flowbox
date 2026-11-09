// 截图助手：打开项目 → 点第一张卡 → 展开字段类型菜单 → 存图
// 用法：node shot.mjs [输出文件] [项目名]
import puppeteer from 'puppeteer-core'

const out = process.argv[2] || 'shot.png'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: 'new',
  defaultViewport: { width: 1500, height: 950 },
})
const page = await browser.newPage()
await page.goto(process.env.FB_URL || 'http://localhost:5173/', { waitUntil: 'networkidle2' })
await page.waitForSelector('.card', { timeout: 20000 })

const want = process.argv[3]
if (want) {
  await page.select('.tb select', want).catch(() => {})
  await sleep(800)
}

const cards = await page.$$('.card')
await cards[Math.min(1, cards.length - 1)].click()
await sleep(400)
await page.click('.addfield').catch(() => {})
await sleep(300)
await page.screenshot({ path: out })
await browser.close()
console.log('saved', out)
