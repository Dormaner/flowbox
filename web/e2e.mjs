// 新模型回归：卡片 = Markdown 文档
import puppeteer from 'puppeteer-core'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const URL = process.env.FB_URL || 'http://localhost:5173/'
const BRIDGE = process.env.FB_BRIDGE || 'http://127.0.0.1:8765'
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

await page.goto(URL, { waitUntil: 'networkidle2' })

// 数据目录守卫：用 App 里真实看到的项目列表判断（不信浏览器缓存）
await page.waitForSelector('.tb select option', { timeout: 20000 })
const opts = await page.$$eval('.tb select option', (els) => els.map((e) => e.value))
if (opts.length !== 1 || opts[0] !== '测试项目') {
  console.error('App 里看到的项目是 ' + JSON.stringify(opts) + '，必须是只有「测试项目」的临时目录')
  await browser.close()
  process.exit(2)
}

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


// 自由缩放 + 自适应
const selectedCardWidth = () =>
  page.evaluate(() => {
    const c = document.querySelector('.react-flow__node.selected .card') || document.querySelector('.card')
    return Math.round(c.getBoundingClientRect().width)
  })

await step('拖边角改大小', async () => {
  const before = await selectedCardWidth()
  const h = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.react-flow__resize-control.handle')].find(
      (x) => x.className.includes('bottom') && x.className.includes('right'),
    )
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
  })
  if (!h) return check('拖边角改大小', false, '看不到缩放把手')
  await page.mouse.move(h.x, h.y)
  await page.mouse.down()
  await page.mouse.move(h.x + 30, h.y + 20, { steps: 6 })
  await page.mouse.move(h.x + 60, h.y + 40, { steps: 6 })
  await page.mouse.up()
  await sleep(500)
  const after = await selectedCardWidth()
  const label = await page.$eval('.drawer .msize', (e) => e.textContent || '').catch(() => '')
  check('拖边角改大小', after > before + 15, `${before} -> ${after}，详情栏显示 ${label.trim()}`)
})

await step('自适应按钮回到自动尺寸', async () => {
  await page.click('.drawer .mini-btn')
  await sleep(500)
  const label = await page.$eval('.drawer .msize', (e) => e.textContent || '')
  check('自适应按钮回到自动尺寸', label.includes('自动'), label.trim())
})

// 模式只管详情：预览下画布照样能改
await step('预览模式下画布仍可编辑', async () => {
  await page.click('#m-view')
  await sleep(300)
  const n0 = await page.$$eval('.card', (els) => els.length)
  const pane = await page.evaluate(() => {
    const p = document.querySelector('.react-flow__pane')
    const r = p.getBoundingClientRect()
    return { x: Math.round(r.x + 200), y: Math.round(r.y + r.height - 170) }
  })
  await page.mouse.click(pane.x, pane.y, { delay: 10 })
  await page.mouse.click(pane.x, pane.y, { delay: 10 })
  await sleep(500)
  const n1 = await page.$$eval('.card', (els) => els.length)
  await page.keyboard.press('Escape')
  check('预览模式下画布仍可编辑', n1 === n0 + 1, `${n0} -> ${n1}`)
  await page.click('#m-edit')
  await sleep(300)
})

await step('Ctrl+/ 来回切换', async () => {
  await page.keyboard.down('Control')
  await page.keyboard.press('/')
  await page.keyboard.up('Control')
  await sleep(350)
  const toView = await page.$eval('#m-view', (e) => e.className.includes('on'))
  await page.keyboard.down('Control')
  await page.keyboard.press('/')
  await page.keyboard.up('Control')
  await sleep(350)
  const toEdit = await page.$eval('#m-edit', (e) => e.className.includes('on'))
  check('Ctrl+/ 来回切换', toView && toEdit, `编辑->预览 ${toView}，预览->编辑 ${toEdit}`)
})

await step('详情栏固定后不选卡片也不消失', async () => {
  const pinned = await page.$eval('#d-pin', (e) => e.className.includes('on'))
  await page.mouse.click(60, 200)
  await sleep(400)
  const stillThere = Boolean(await page.$('.drawer'))
  check('详情栏固定后不选卡片也不消失', pinned === true && stillThere, `固定=${pinned}，还在=${stillThere}`)
})

await step('顶部不再有状态计数', async () => {
  check('顶部不再有状态计数', (await page.$$('.tb .legend')).length === 0)
})
// 容器卡：建容器 → 拖卡进去 → 折叠/展开 → 拖容器带走子卡 → 聚焦
let contKidId = null
await step('新建容器', async () => {
  // 先把详情栏关掉，免得卡片被它盖住点不到
  await page.click('#d-close').catch(() => {})
  await page.waitForFunction(() => !document.querySelector('.drawer'), { timeout: 5000 }).catch(() => {})
  await sleep(300)
  await page.evaluate(() => {
    const b2 = [...document.querySelectorAll('.tb button')].find((x) => x.textContent.includes('容器'))
    b2?.click()
  })
  await sleep(600)
  await page.keyboard.press('Escape')
  await sleep(300)
  const c = await page.evaluate(() => {
    const el = document.querySelector('.card.cont')
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
  })
  check('新建容器', !!c && c.w > 80, c ? `${c.w}×${c.h}（屏幕像素）` : '没建出来')
})

await step('拖卡进容器', async () => {
  const rect = await page.evaluate(() => {
    const r = document.querySelector('.card.cont').getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
  })
  // 在容器左边双击新建一张卡，位置可预期，再把它拖进容器
  const spot = { x: Math.max(80, rect.x - 200), y: rect.y + Math.round(rect.h / 2) }
  await page.mouse.click(spot.x, spot.y, { delay: 10 })
  await page.mouse.click(spot.x, spot.y, { delay: 10 })
  await sleep(600)
  await page.keyboard.press('Escape')
  await sleep(300)
  const start = await page.evaluate(() => {
    const cs = [...document.querySelectorAll('.card')].filter((c) => !c.classList.contains('cont'))
    const node = cs[cs.length - 1].closest('.react-flow__node')
    const r = cs[cs.length - 1].getBoundingClientRect()
    return {
      id: node.getAttribute('data-id'),
      x: Math.round(r.x + r.width / 2),
      y: Math.round(r.y + r.height / 2),
    }
  })
  contKidId = start.id
  const drop = { x: rect.x + Math.round(rect.w / 2), y: rect.y + Math.round(rect.h / 2) }
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(start.x + 30, start.y + 20, { steps: 8 })
  await page.mouse.move(drop.x, drop.y, { steps: 12 })
  await page.mouse.up()
  await sleep(700)
  const cnt = await page.$eval('.card.cont .ccnt', (e) => e.textContent || '')
  check('拖卡进容器', cnt.includes('1'), '徽标显示 ' + cnt.trim())
})

await step('折叠隐藏子卡 / 展开恢复', async () => {
  const visible = () => page.$$eval('.card', (els) => els.filter((e) => e.offsetParent !== null).length)
  await page.evaluate(() => {
    const b2 = [...document.querySelectorAll('.card.cont .cbtn')].find((x) =>
      x.textContent.includes('折叠'),
    )
    b2?.click()
  })
  await sleep(600)
  const folded = await visible()
  await page.evaluate(() => {
    const b2 = [...document.querySelectorAll('.card.cont .cbtn')].find((x) =>
      x.textContent.includes('展开'),
    )
    b2?.click()
  })
  await sleep(600)
  const open = await visible()
  check('折叠隐藏子卡 / 展开恢复', folded === open - 1, `折叠 ${folded} 张，展开 ${open} 张`)
})

await step('拖容器带着子卡一起走', async () => {
  // 用保存下来的数据当判据（比测 DOM 稳）
  const readDoc = () =>
    page.evaluate(async (u) => {
      const res = await fetch(u + '/flow?project=' + encodeURIComponent('测试项目') + '&t=' + Date.now(), {
        cache: 'no-store',
      })
      return res.ok ? await res.json() : null
    }, BRIDGE)
  const contId = await page.evaluate(
    () => document.querySelector('.card.cont').closest('.react-flow__node').dataset.id,
  )
  // 等保存追上：d0 里子卡必须已经落在容器范围内（否则量到的位移是假的）
  let d0 = null
  let c0f = null
  let k0f = null
  for (let i = 0; i < 12; i++) {
    d0 = await readDoc()
    const c = d0?.nodes?.find((n) => n.id === contId)
    const k = d0?.nodes?.find((n) => n.id === contKidId)
    if (c && k && k.x > c.x && k.x < c.x + (c.w || 0) && k.y > c.y && k.y < c.y + (c.h || 0)) {
      c0f = c
      k0f = k
      break
    }
    await sleep(400)
  }
  const before = await page.evaluate(() => {
    const r = document.querySelector('.card.cont').getBoundingClientRect()
    return { cx: Math.round(r.x + 24), cy: Math.round(r.y + r.height - 14) }
  })
  await page.mouse.move(before.cx, before.cy)
  await page.mouse.down()
  await page.mouse.move(before.cx + 20, before.cy + 10, { steps: 6 })
  await page.mouse.move(before.cx + 60, before.cy + 40, { steps: 10 })
  await page.mouse.up()
  await sleep(600)
  // 自动保存是防抖的，多等几轮直到落盘
  let d1 = null
  let dcx = 0
  let dkx = 0
  for (let i = 0; i < 14; i++) {
    await sleep(700)
    d1 = await readDoc()
    const c1f = d1?.nodes?.find((n) => n.id === contId)
    const k1f = d1?.nodes?.find((n) => n.id === contKidId)
    dcx = c1f && c0f ? Math.round(c1f.x - c0f.x) : 0
    dkx = k1f && k0f ? Math.round(k1f.x - k0f.x) : 0
    if (dcx !== 0 && Math.abs(dcx - dkx) <= 2) break
  }
  check(
    '拖容器带着子卡一起走',
    !!c0f && !!k0f && dcx !== 0 && Math.abs(dcx - dkx) <= 2,
    `容器 +${dcx}，子卡 +${dkx}`,
  )
})

await step('聚焦只留这一组', async () => {
  await page.evaluate(() => {
    const b2 = [...document.querySelectorAll('.card.cont .cbtn')].find((x) =>
      x.textContent.includes('聚焦'),
    )
    b2?.click()
  })
  await sleep(700)
  const vis = await page.$$eval('.card', (els) => els.filter((e) => e.offsetParent !== null).length)
  const chip = Boolean(await page.$('.viewchip.focus'))
  check('聚焦只留这一组', vis === 2 && chip, `可见 ${vis} 张`)
  await page.evaluate(() => {
    document.querySelector('.viewchip.focus button')?.click()
  })
  await sleep(500)
  const all = await page.$$eval('.card', (els) => els.filter((e) => e.offsetParent !== null).length)
  check('退出聚焦恢复全部', all > vis, `可见 ${all} 张`)
})



await step('多选出现排版工具条', async () => {
  await page.click('#d-close').catch(() => {})
  await page.waitForFunction(() => !document.querySelector('.drawer'), { timeout: 5000 }).catch(() => {})
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
// 清单升卡 / 按小节拆卡 / 合并
let splitSrc = null
await step('清单升卡：勾选项变成卡片', async () => {
  const spot = await page.evaluate(() => {
    const p = document.querySelector('.react-flow__pane').getBoundingClientRect()
    return { x: Math.round(p.x + 160), y: Math.round(p.y + 150) }
  })
  await page.mouse.click(spot.x, spot.y, { delay: 10 })
  await page.mouse.click(spot.x, spot.y, { delay: 10 })
  await sleep(500)
  await page.keyboard.type('拆卡测试')
  await page.keyboard.press('Enter')
  await sleep(300)
  splitSrc = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.card')].find((c) =>
      (c.textContent || '').includes('拆卡测试'),
    )
    return el.closest('.react-flow__node').getAttribute('data-id')
  })
  const md = await page.$('.drawer textarea.md')
  await md.click()
  await page.keyboard.down('Control')
  await page.keyboard.press('End')
  await page.keyboard.up('Control')
  await page.keyboard.type('\n- [ ] 甲材料\n- [ ] 乙材料')
  await sleep(400)
  const n0 = await page.$$eval('.card', (els) => els.length)
  const e0 = await page.$$eval('.react-flow__edge', (els) => els.length)
  await page.click('#m-promote')
  await sleep(800)
  const n1 = await page.$$eval('.card', (els) => els.length)
  const e1 = await page.$$eval('.react-flow__edge', (els) => els.length)
  const names = await page.$$eval('.card .ttl', (els) => els.map((e) => e.textContent.trim()))
  check(
    '清单升卡：勾选项变成卡片',
    n1 === n0 + 2 && e1 === e0 + 2 && names.includes('甲材料') && names.includes('乙材料'),
    `卡片 ${n0} -> ${n1}，连线 ${e0} -> ${e1}`,
  )
})

await step('按小节拆卡', async () => {
  const md = await page.$('.drawer textarea.md')
  await md.click()
  await page.keyboard.down('Control')
  await page.keyboard.press('End')
  await page.keyboard.up('Control')
  await page.keyboard.type('\n## 第一步\n先干这个\n## 第二步\n再干那个')
  await sleep(500)
  const n0 = await page.$$eval('.card', (els) => els.length)
  await page.click('#m-split')
  await sleep(800)
  const n1 = await page.$$eval('.card', (els) => els.length)
  const names = await page.$$eval('.card .ttl', (els) => els.map((e) => e.textContent.trim()))
  check(
    '按小节拆卡',
    n1 === n0 + 2 && names.includes('第一步') && names.includes('第二步'),
    `卡片 ${n0} -> ${n1}`,
  )
})

await step('多选合并成容器', async () => {
  await page.click('#d-close').catch(() => {})
  await page.waitForFunction(() => !document.querySelector('.drawer'), { timeout: 5000 }).catch(() => {})
  await sleep(300)
  const pts = await page.evaluate(() => {
    const cs = [...document.querySelectorAll('.card:not(.cont)')].filter((c) => {
      const t = c.querySelector('.ttl')?.textContent || ''
      return t.includes('甲材料') || t.includes('乙材料')
    })
    return cs.map((c) => {
      const r = c.getBoundingClientRect()
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }
    })
  })
  if (pts.length < 2) return check('多选合并成容器', false, '没找到刚拆出来的两张卡')
  await page.mouse.click(pts[0].x, pts[0].y)
  await sleep(200)
  await page.keyboard.down('Control')
  await page.mouse.click(pts[1].x, pts[1].y)
  await page.keyboard.up('Control')
  await sleep(300)
  const c0 = await page.$$eval('.card.cont', (els) => els.length)
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.selbar button')].find((x) =>
      (x.getAttribute('title') || '').includes('合并'),
    )
    b?.click()
  })
  await sleep(800)
  const c1 = await page.$$eval('.card.cont', (els) => els.length)
  const badges = await page.$$eval('.card.cont .ccnt', (els) => els.map((e) => e.textContent.trim()))
  check(
    '多选合并成容器',
    c1 === c0 + 1 && badges.some((b) => b.startsWith('2')),
    `容器 ${c0} -> ${c1}，徽标 ${badges.join(' / ')}`,
  )
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
        // 两点太近时拖拽会被当成点击
        if (Math.hypot(to.x - from.x, to.y - from.y) < 150) continue
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

