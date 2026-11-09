// 新模型回归：卡片 = Markdown 文档
import puppeteer from 'puppeteer-core'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const URL = process.env.FB_URL || 'http://localhost:5173/'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok, extra = '') => {
  results.push({ name, ok })
  console.log((ok ? 'OK   ' : 'FAIL ') + name + (extra ? '  ' + extra : ''))
}
// 每一步都包住：某步挂了也继续跑，最后一次性报出来
const step = async (name, fn) => {
  try {
    await fn()
  } catch (e) {
    check(name, false, '异常 ' + String(e?.message || e).slice(0, 120))
  }
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
if (projNow !== '测试项目') {
  console.error(`拒绝在「${projNow}」上跑测试，只能跑临时目录里的「测试项目」`)
  await browser.close()
  process.exit(2)
}

// 视口内可点的卡片中心（避开右侧抽屉 / 顶部工具栏）
const cardCenters = () =>
  page.evaluate(() => {
    const w = document.querySelector('.drawer') ? window.innerWidth - 380 : window.innerWidth
    return [...document.querySelectorAll('.card')]
      .map((c) => {
        const r = c.getBoundingClientRect()
        return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
      })
      .filter((p) => p.x > 20 && p.x < w - 40 && p.y > 110 && p.y < window.innerHeight - 60)
  })

let n0 = 0
await step('打开项目并渲染卡片', async () => {
  n0 = await page.$$eval('.card', (els) => els.length)
  check('打开项目并渲染卡片', n0 > 0, n0 + ' 张')
})

await step('卡片高度自适应不裁字', async () => {
  const clip = await page.evaluate(() => {
    let bad = 0
    for (const c of document.querySelectorAll('.card')) {
      if (c.scrollHeight - c.clientHeight > 2) bad++
      for (const sel of ['.ttl', '.sum', '.mini']) {
        const el = c.querySelector(sel)
        if (el && el.scrollHeight - el.clientHeight > 2) bad++
      }
    }
    return bad
  })
  check('卡片高度自适应不裁字', clip === 0, clip + ' 处溢出')
})


// 新建 + 就地改名
const tag = '步骤' + String(Date.now()).slice(-5)
await step('双击空白新建卡片', async () => {
  const pane = await page.evaluate(() => {
    const p = document.querySelector('.react-flow__pane')
    const r = p.getBoundingClientRect()
    return { x: Math.round(r.x + 120), y: Math.round(r.y + r.height - 130) }
  })
  await page.mouse.click(pane.x, pane.y, { delay: 10 })
  await page.mouse.click(pane.x, pane.y, { delay: 10 })
  await sleep(500)
  const n1 = await page.$$eval('.card', (els) => els.length)
  check('双击空白新建卡片', n1 === n0 + 1, `${n0} -> ${n1}`)
  await page.keyboard.type(tag)
  await page.keyboard.press('Enter')
  await sleep(300)
  const hit = await page.$$eval(
    '.card .ttl',
    (els, t) => els.filter((e) => (e.textContent || '').includes(t)).length,
    tag,
  )
  check('就地改名生效', hit === 1, hit + ' 张')
})

// 抽屉：Markdown 编辑器
await step('抽屉里是 Markdown 编辑器', async () => {
  const c = await page.evaluate((t) => {
    const el = [...document.querySelectorAll('.card')].find((x) => (x.textContent || '').includes(t))
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
  }, tag)
  await page.mouse.click(c.x, c.y)
  await sleep(500)
  check('抽屉里是 Markdown 编辑器', Boolean(await page.$('.drawer textarea.md')))
})

await step('能直接写勾选清单', async () => {
  const md = await page.$('.drawer textarea.md')
  await md.click()
  await page.keyboard.down('Control')
  await page.keyboard.press('End')
  await page.keyboard.up('Control')
  await page.keyboard.type('\n- [ ] 测试材料A')
  await sleep(300)
  const v = await md.evaluate((el) => el.value)
  check('能直接写勾选清单', v.includes('- [ ] 测试材料A'))
})

await step('预览渲染出清单条目', async () => {
  await page.click('#m-view')
  await sleep(400)
  const tasks = await page.$$eval('.mdview li.task', (e) => e.length)
  check('预览渲染出清单条目', tasks >= 1, tasks + ' 条')
  await page.click('#m-edit')
  await sleep(250)
})

await step('上传文件写入正文', async () => {
  const input = await page.$('.drawer input[type=file]')
  if (!input) return check('上传文件写入正文', false, '找不到文件输入')
  await input.uploadFile(process.env.FB_IMG || 'C:/Users/niu/AppData/Local/Temp/fb_upload.png')
  await sleep(1800)
  const v = await page.$eval('.drawer textarea.md', (el) => el.value)
  check('上传文件写入正文', v.includes('![['), v.slice(-30).replace(/\n/g, ' '))
})


// 多选 → 排版条 → 成组
await step('多选出现排版工具条', async () => {
  await page.click('#d-close')
  await page.waitForFunction(() => !document.querySelector('.drawer'), { timeout: 5000 })
  await sleep(300)
  const cs = await cardCenters()
  await page.mouse.click(cs[0].x, cs[0].y)
  await sleep(250)
  await page.keyboard.down('Control')
  await page.mouse.click(cs[1].x, cs[1].y)
  await page.keyboard.up('Control')
  await sleep(350)
  check('多选出现排版工具条', Boolean(await page.$('.selbar')))
})

const clickSelbar = async (word) => {
  const p = await page.evaluate((w) => {
    const b = [...document.querySelectorAll('.selbar button')].find((x) =>
      (x.getAttribute('title') || x.textContent || '').includes(w),
    )
    if (!b) return null
    const r = b.getBoundingClientRect()
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
  }, word)
  if (!p) return false
  await page.mouse.click(p.x, p.y)
  await sleep(400)
  return true
}

await step('左对齐生效', async () => {
  if (!(await clickSelbar('左对齐'))) return check('左对齐生效', false, '找不到按钮')
  const xs = await page.$$eval('.card', (els) =>
    els.map((e) => Math.round(e.getBoundingClientRect().x)),
  )
  const dup = xs.filter((x, i) => xs.indexOf(x) !== i).length
  check('左对齐生效', dup >= 1, xs.slice(0, 6).join(','))
})

await step('成组出现分组框', async () => {
  if (!(await clickSelbar('分组'))) return check('成组出现分组框', false, '找不到按钮')
  await sleep(200)
  check('成组出现分组框', Boolean(await page.$('.gbox')))
})

// 连线：先回到 100%（把手在低缩放下只有 3px，真人也不会那么点），再拖
await step('拖圆点连成线', async () => {
  await page.keyboard.press('Escape')
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.tb button')].find((x) => x.textContent.includes('100%'))
    b?.click()
  })
  await sleep(700)
  const grab = await page.evaluate(() => {
    const inView = (p) =>
      !!p && p.x > 30 && p.x < window.innerWidth - 40 && p.y > 110 && p.y < window.innerHeight - 50
    const nodes = [...document.querySelectorAll('.react-flow__node')].filter((el) =>
      el.querySelector('.card'),
    )
    const pick = (el, cls) => {
      const h = [...el.querySelectorAll('.react-flow__handle')].find((x) =>
        x.classList.contains(cls),
      )
      if (!h) return null
      const r = h.getBoundingClientRect()
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
    }
    const isHandle = (p) =>
      inView(p) && !!document.elementFromPoint(p.x, p.y)?.classList?.contains('react-flow__handle')
    for (const a of nodes) {
      const from = pick(a, 'right')
      if (!isHandle(from)) continue
      for (const b of nodes) {
        if (a === b) continue
        const to = pick(b, 'left')
        if (!isHandle(to)) continue
        return { from, to }
      }
    }
    return null
  })
  if (!grab) return check('拖圆点连成线', false, '找不到能点的把手')
  const e0 = await page.$$eval('.react-flow__edge', (els) => els.length)
  await page.mouse.move(grab.from.x, grab.from.y)
  await sleep(120)
  await page.mouse.down()
  await sleep(120)
  await page.mouse.move(grab.from.x + 20, grab.from.y + 6, { steps: 6 })
  await page.mouse.move(grab.to.x - 16, grab.to.y, { steps: 12 })
  await page.mouse.move(grab.to.x, grab.to.y, { steps: 6 })
  await sleep(200)
  await page.mouse.up()
  await sleep(500)
  const e1 = await page.$$eval('.react-flow__edge', (els) => els.length)
  check('拖圆点连成线', e1 === e0 + 1, `${e0} -> ${e1}  ${JSON.stringify(grab)}`)
})

await step('Ctrl+Z 撤销连线', async () => {
  const e0 = await page.$$eval('.react-flow__edge', (els) => els.length)
  await page.keyboard.down('Control')
  await page.keyboard.press('z')
  await page.keyboard.up('Control')
  await sleep(450)
  const e1 = await page.$$eval('.react-flow__edge', (els) => els.length)
  check('Ctrl+Z 撤销连线', e1 === e0 - 1, `${e0} -> ${e1}`)
})

await step('滚轮改变缩放', async () => {
  const read = () =>
    page.evaluate(() => document.querySelector('.react-flow__viewport')?.style.transform || '')
  const z0 = await read()
  await page.mouse.move(700, 480)
  await page.mouse.wheel({ deltaY: -400 })
  await sleep(400)
  const z1 = await read()
  check('滚轮改变缩放', z0 !== z1, z0.slice(0, 30) + ' -> ' + z1.slice(0, 30))
})

check('没有 JS 报错', errors.length === 0, errors.slice(0, 2).join(' | '))

await page.screenshot({ path: process.env.FB_SHOT || 'e2e.png' })
await browser.close()
const bad = results.filter((x) => !x.ok).length
console.log(bad ? `\n${bad} 项失败` : '\n全部通过')
process.exit(bad ? 1 : 0)

