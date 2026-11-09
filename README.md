# 流程盒子 flowbox

把公司流程画成一张图：每张卡片是一步，卡片里放这一步要交什么、去哪个系统、用谁的账号、截图长什么样。同事不用问，照着图走一遍就会。

Windows 桌面小工具，Python + tkinter，单文件程序，数据和程序放同一个文件夹，拷给同事就能用。

## 跑起来

需要 Python 3.10+：

```
pip install pillow tkinterdnd2
python canvas_demo.py
```

打成 exe 给同事：

```
pyinstaller --noconfirm --clean --onefile --windowed --icon flowbox.ico --name 流程盒子 --collect-all tkinterdnd2 canvas_demo.py
```

## 怎么用

| 想干什么 | 怎么做 |
| --- | --- |
| 加一步 | 双击空白处，就地起名 |
| 改这一步 | 双击卡片 |
| 连起来 | 从卡片右边的半圆拖到另一张卡片左边 |
| 改连线 | 双击线改标签，右键改颜色 / 虚线 |
| 多选 | 空白处拖框，或按住 Shift 点 |
| 成组 | 选中后右键「成组」，框自动贴合 |
| 缩放 | Ctrl+滚轮，或顶栏 － / ＋ / 1:1 |
| 平移 | 中键拖、右键拖 |
| 加材料 | 把文件直接拖到卡片上（图片进「截图」，其它进「附件」） |
| 撤销重做 | Ctrl+Z / Ctrl+Y |
| 保存 | Ctrl+S（多数改动会自动存，拿不准就按一下） |
| 发给同事 | 菜单「文件 → 导出只读网页」，得到一个 HTML，微信传过去，双击就能看 |

## 卡片里能放什么

字段类型：文本、多行文本、单选、多选、清单、人员、日期、附件、图片、数字、复选框、超链接。

- **清单**：一行一条，随时加减
- **附件**：点「＋ 选文件」挂真实文件，文件复制进 `files/<卡片id>/`，点「看」用系统默认程序打开
- **图片**：点「＋ 选图片」，或者直接把文件拖进卡片，最多显示 3 张
- **超链接**：填网址和按钮上的字，点了用浏览器打开（`oa.example.com` 这种没写协议的会自动补 `https://`）

每张卡片右上角有个圆点，是这张卡片的进度。进度值是项目级的，菜单「编辑 → 卡片状态…」里可以改名、加状态、删状态；也可以点圆点或右键卡片直接切。

连线只从右边半圆出、到左边半圆进；回到前面某一步的线（驳回、重新提交）会自动绕一圈再进去。

## 数据存在哪

`projects/<项目名>/`：

```
flow.json             整张图（卡片、连线、字段、状态）
files/<卡片id>/        这张卡片挂的附件和截图
snapshots/            最近 5 次保存的版本
```

`flow.json` 是普通 JSON，原子写入（先写临时文件再替换），手改也认。整个 `projects/` 拷给同事就是分享。

菜单里还能：新建项目、另存为副本、导出 / 导入 zip、导出只读网页。

## 发给同事的那个网页

「文件 → 导出只读网页」出来的是**一张图**，不是一篇文章：连线、分支、驳回回路都在，跟你画布上看到的一样。

- 滚轮缩放、拖动平移、双击空白处回到全图
- 点任意一张卡片：只留它的上游下游，右边滑出这一步的所有材料（附件能直接下载，太大的不内嵌）
- 顶上搜索：名字、字段值、材料名都能搜到，回车跳到那一张
- 「列表」按钮切换成竖排阅读版，适合打印和 Ctrl+P 存 PDF
- 单个 HTML，图片压到 1200 宽内嵌，7 步的项目大约 900 KB，不依赖任何网络

## Qt 版编辑器（试验中）

`editor_qt.py` 是把画布层换成 Qt 的版本，读的是**同一份 `projects/`**，两个版本可以轮流打开同一个项目，互不干扰。

先说清楚状态：**它是拿来试手感的，功能还没 Tk 版全。**

已经有的：

- 画布：滚轮上下滚、Shift+滚轮横滚、Ctrl+滚轮以光标为中心缩放、框选、多选一起拖、10 像素吸附、点阵网格、抗锯齿和阴影
- 卡片：圆角 + 柔和投影、标题两行超长省略、状态圆点、悬停边框变化、右侧连线圆点悬停才出现
- 连线：跟 Tk 版同一套几何（直角 + 圆角）加箭头；从卡片右侧圆点拖到另一张卡片就成线，双击线改标签
- 右侧抽屉：改名、一句话说明、切状态；字段支持 12 种类型，附件和图片能直接选文件，复制进 `files/<卡片id>/`
- 撤销重做（Ctrl+Z / Ctrl+Y）、改完自动保存、快照、导出只读网页（跟 Tk 版同一个模板）

还没搬过来（要这些就用 Tk 版）：

- 新建项目、模板（报销 / 采购 / 入职）、zip 导入导出
- 成组、对齐分布、复制粘贴、把文件拖到卡片上
- 自定义状态编辑、跨项目搜索

跑起来：

```
pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple
python editor_qt.py
```

或者双击 `启动流程盒子Qt.bat`。打包成 exe 用：

```
pyinstaller --noconfirm --clean --onefile --windowed --icon flowbox.ico --name 流程盒子Qt editor_qt.py
```

快捷键：`Ctrl+N` 新建卡片 · `Ctrl+0` 适应窗口 · `Ctrl+1` 100% · `Delete` 删除选中 · `Esc` 取消连线 · 中键拖动平移

## Web 版编辑器（React + React Flow + Tauri，试验中）

`web/` 是把画布和界面整个换成 Web 技术栈的版本：**React 18 + React Flow 12 + Vite**，桌面外壳用 **Tauri 2（Rust + 系统 WebView2）**。数据还是同一份 `projects/`。

为什么换：Tk 和 Qt 两版都是"自绘一切"——就地编辑、拖放、动画、输入法、高 DPI 都要自己啃。浏览器这些是白送的，观感和手感的上限高得多。

已经有的：

- 画布：滚轮缩放、中键拖动平移、框选多选、点阵网格、小地图、缩放控件
- 卡片：双击空白新建（自动进入改名）、双击标题/说明就地编辑、悬停浮起、状态圆点（点一下循环切换）
- 连线：自定义边，走线几何跟 Python 版同一套（直角 + 13 圆角 + 箭头），从卡片右侧圆点拖到另一张卡片
- 右侧抽屉：改名、说明、状态切换、字段查看与编辑
- 撤销重做（Ctrl+Z / Ctrl+Y）、改完 700ms 自动存、项目切换、状态统计
- 桌面版读写走 Rust 命令（`list_projects` / `load_flow` / `save_flow` / `file_data_url`），截图以 data URL 注入

还没做的（这一版是原型，别拿它替换 Tk 版）：

- 新建项目、模板、zip 导入导出、成组对齐、拖放文件、搜索、导出只读网页
- 状态的自定义编辑（增删改名）

跑浏览器版（改代码时最快）：

```
cd web
pip install -r requirements.txt      # 只为了用 python 起 bridge
python bridge.py                     # 127.0.0.1:8765，把 projects/ 暴露给页面
npm install
npm run dev                          # http://localhost:5173
```

跑桌面版：

```
cd web
npm run desktop          # tauri dev，热更新
npm run dist             # 打 release（要 Rust + MSVC BuildTools）
```

自动化测试（用本机 Edge 真点）：

```
cd web
node e2e.mjs             # 需要 bridge + dev server 都起着
```

依赖：Node 18+、Rust stable（含 MSVC 链接器）、WebView2 运行时（Win10 1809 以上一般自带）。

## 局限

- 只有 Windows（用到了 `os.startfile`、单实例互斥锁、tkinterdnd2）
- 单机工具，没有多人同时编辑、没有权限控制
- 界面是 tkinter 画的，不是网页
- `flowbox.py` 是更早的原型（带 PDF 材料检查、命名那套），留着做参考

## 目录

```
canvas_demo.py                        主程序（"流程盒子"本体，文件名是历史遗留）
editor_qt.py                          Qt 画布版编辑器（试验中，读同一份数据）
web/                                  React + React Flow + Tauri 版（试验中）
html_export.py                        只读网页的模板和排版（两个 Python 版本都用它导出）
flowbox.py                            更早的原型
flowbox.ico                           图标
启动流程盒.bat                         双击启动 Tk 版：有 exe 就开 exe，没有就用 pythonw
启动流程盒子Qt.bat                     双击启动 Qt 版
examples/patent-annual-fee.flow.json  原型用的示例流程
```

## License

MIT
