// 新模型回归：卡片 = Markdown 文档
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
page.on('dialog', (d) => (d.type() === 'prompt' ? d.accept('测试分组') : d.accept()))

await page.goto(URL, { waitUntil: 'networkidle2' })
await page.waitForSelector('.card', { timeout: 20000 })
await page.select('.tb select', '测试项目').catch(() => {})
await sleep(900)
const projNow = await page.$eval('.tb select', (el) => el.value)
if (!['测试项目', '专利年费'].includes(projNow)) {
  console.error(`拒绝在「${projNow}」上跑测试，先起临时 bridge`)
  process.exit(2)
}
const n0 = await page.$$eval('.card', (els) => els.length)
check('打开项目并渲染卡片', n0 > 0, n0 + ' 张')

// 新建 + 就地改名
const pane = await page.evaluate(() => {
  const p = document.querySelector('.react-flow__pane')
  const r = p.getBoundingClientRect()
  return { x: Math.round(r.x + 140), y: Math.round(r.y + r.height - 160) }
})
await page.mouse.click(pane.x, pane.y, { delay: 10 })
await page.mouse.click(pane.x, pane.y, { delay: 10 })
await sleep(400)
const n1 = await page.$$eval('.card', (els) => els.length)
check('双击空白新建卡片', n1 === n0 + 1, `${n0} -> ${n1}`)
const tag = '步骤' + String(Date.now()).slice(-5)
await page.keyboard.type(tag)
await page.keyboard.press('Enter')
await sleep(300)
const title = await page.$$eval(
  '.card .ttl',
  (els, t) => els.filter((e) => (e.textContent || '').includes(t)).length,
  tag,
)
check('就地改名生效', title === 1, title + ' 张')

// 抽屉：Markdown 编辑器
const cards = await page.$$('.card')
await cards[0].click()
await sleep(500)
const mdEl = await page.$('.drawer textarea.md')
check('抽屉里是 Markdown 编辑器', Boolean(mdEl))

await mdEl.click()
await page.keyboard.down('Control')
await page.keyboard.press('End')
await page.keyboard.up('Control')
await page.keyboard.type('\n- [ ] 测试材料A')
await sleep(300)
const bodyTxt = await mdEl.evaluate((el) => el.value)
check('能直接写勾选清单', bodyTxt.includes('- [ ] 测试材料A'))

await page.click('#m-view')
await sleep(400)
const tasks = await page.$$eval('.mdview li.task', (e) => e.length)
check('预览渲染出清单条目', tasks >= 1, tasks + ' 条')
await page.click('#m-edit')
await sleep(250)

// 上传文件 → 正文里出现嵌入标记
const fileInput = await page.$('.drawer input[type=file]')
if (fileInput) {
  await fileInput.uploadFile(process.env.FB_IMG || 'C:/Users/niu/AppData/Local/Temp/fb_upload.png')
  await sleep(1800)
  const v = await page.$eval('.drawer textarea.md', (el) => el.value)
  check('上传文件写入正文', v.includes('![['), v.slice(-40))
} else {
  check('上传文件写入正文', false, '找不到文件输入')
}

// 多选 → 排版条 → 成组
await page.keyboard.press('Escape')
await sleep(200)
let cs = await page.$$('.card')
await cs[0].click()
await page.keyboard.down('Control')
await cs[1].click()
await page.keyboard.up('Control')
await sleep(350)
check('多选出现排版工具条', Boolean(await page.$('.selbar')))
await page.click('.selbar button[title="左对齐"]')
await sleep(350)
const xs = await page.$$eval('.card', (els) => els.map((e) => Math.round(e.getBoundingClientRect().x)))
const dup = xs.filter((x, i) => xs.indexOf(x) !== i).length
check('左对齐生效', dup >= 1, xs.slice(0, 6).join(','))
await page.click('.selbar button[title="把选中的卡片装进一个分组框"]')
await sleep(400)
check('成组出现分组框', Boolean(await page.$('.gbox')))

// 连线 / 撤销 / 缩放
await page.keyboard.press('Escape')
await sleep(200)
const handles = await page.evaluate(() => {
  const cards = [...document.querySelectorAll('.react-flow__node')].filter((el) => el.querySelector('.card'))
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

await page.keyboard.down('Control')
await page.keyboard.press('z')
await page.keyboard.up('Control')
await sleep(300)
const e2 = await page.$$eval('.react-flow__edge', (els) => els.length)
check('Ctrl+Z 撤销连线', e2 === e0, `${e1} -> ${e2}`)

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
