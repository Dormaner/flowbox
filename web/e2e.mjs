// 用本机 Edge 驱动一次真实交互：建卡、就地改名、连线、撤销、抽屉
// 跑之前先起 bridge（指向临时目录）和 vite dev。
import puppeteer from 'puppeteer-core'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const URL = process.env.FB_URL || 'http://localhost:5173/'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok, extra = '') => {
  results.push(ok)
  console.log((ok ? 'OK   ' : 'FAIL ') + name + (extra ? '  ' + extra : ''))
}

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: 'new',
  args: ['--window-size=1500,950', '--disable-gpu'],
  defaultViewport: { width: 1500, height: 950 },
})
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})

await page.goto(URL, { waitUntil: 'networkidle2' })
await page.waitForSelector('.card', { timeout: 20000 })
const n0 = await page.$$eval('.card', (els) => els.length)
check('打开项目并渲染卡片', n0 > 0, n0 + ' 张')

// 1) 双击空白 → 新卡片，并且直接进改名状态
const pane = await page.evaluate(() => {
  const p = document.querySelector('.react-flow__pane')
  const r = p.getBoundingClientRect()
  return { x: Math.round(r.x + 140), y: Math.round(r.y + r.height - 160) }
})
await page.mouse.click(pane.x, pane.y, { delay: 10 })
await page.mouse.click(pane.x, pane.y, { delay: 10 })
await sleep(400)
const n1 = await page.$$eval('.card', (els) => els.length)
const hasEdit = await page.$('.card textarea.edit')
check('双击空白新建卡片', n1 === n0 + 1, `${n0} -> ${n1}`)
check('新卡片自动进入改名', Boolean(hasEdit))

// 2) 就地打字 + 回车提交
await page.keyboard.type('测试步骤')
await page.keyboard.press('Enter')
await sleep(300)
const title = await page.$$eval('.card .ttl', (els) =>
  els.map((e) => e.textContent || '').filter((t) => t.includes('测试步骤')).length,
)
check('就地改名生效', title === 1, title + ' 张')

// 3) 点卡片 → 右侧抽屉
const cards = await page.$$('.card')
await cards[0].click()
await sleep(300)
const drawer = await page.$('.drawer .dname')
check('点卡片打开抽屉', Boolean(drawer))

// 4) 拖连线：最后一张的右圆点 → 第一张
await page.keyboard.press('Escape')
await sleep(150)
const handles = await page.evaluate(() => {
  const cards = [...document.querySelectorAll('.react-flow__node')]
  const pick = (el, sel) => {
    const h = el.querySelector(sel)
    const r = h.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  }
  return {
    from: pick(cards[cards.length - 1], '.react-flow__handle.right'),
    to: pick(cards[0], '.react-flow__handle.left'),
  }
})
const e0 = await page.$$eval('.react-flow__edge', (els) => els.length)
await page.mouse.move(handles.from.x, handles.from.y)
await page.mouse.down()
await page.mouse.move(handles.to.x - 20, handles.to.y, { steps: 12 })
await page.mouse.move(handles.to.x, handles.to.y, { steps: 4 })
await page.mouse.up()
await sleep(400)
const e1 = await page.$$eval('.react-flow__edge', (els) => els.length)
check('拖圆点连成线', e1 === e0 + 1, `${e0} -> ${e1}`)

// 5) Ctrl+Z 撤销连线，再撤销一次把新卡片也撤掉
await page.keyboard.down('Control')
await page.keyboard.press('z')
await page.keyboard.up('Control')
await sleep(300)
const e2 = await page.$$eval('.react-flow__edge', (els) => els.length)
check('Ctrl+Z 撤销连线', e2 === e0, `${e1} -> ${e2}`)

let n2 = n1
for (let i = 0; i < 4 && n2 !== n0; i++) {
  await page.keyboard.down('Control')
  await page.keyboard.press('z')
  await page.keyboard.up('Control')
  await sleep(250)
  n2 = await page.$$eval('.card', (els) => els.length)
}
check('继续撤销能回到初始状态', n2 === n0, `${n1} -> ${n2}`)

// 6) 滚轮缩放
const zoom0 = await page.$eval('.tb .meta', (e) => e.textContent || '')
await page.mouse.move(700, 480)
await page.mouse.wheel({ deltaY: -400 })
await sleep(300)
const zoom1 = await page.$eval('.tb .meta', (e) => e.textContent || '')
check('滚轮改变缩放', zoom0 !== zoom1, `${zoom0} -> ${zoom1}`)

await page.screenshot({ path: process.env.FB_SHOT || 'e2e.png' })
check('没有 JS 报错', errors.length === 0, errors.slice(0, 2).join(' | '))

await browser.close()
const bad = results.filter((x) => !x).length
console.log(bad ? `\n${bad} 项失败` : '\n全部通过')
process.exit(bad ? 1 : 0)
