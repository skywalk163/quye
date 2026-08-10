# quye.com

中文 AI 编程中心。构建期从四门中文编程语言仓库（极快 / 段言 / 光明 / 知行）抽取核心源码，
打包进浏览器端 Pyodide 沙箱，用户在网页里「中文需求 → 组码 → 当场运行」，无需后端。

纯 Python 标准库构建 + 原生前端（无框架、无打包工具）。

## 目录结构

```
建站.py            构建脚本：生成页面 + 抽取语言包 + 下载 Pyodide + 预跑门禁
预跑器.py          构建期跑官方示例，任一挂掉则构建失败
抽取器/            四门语言各自的源码抽取逻辑
模板/              页面 HTML 模板（基础.html / 台.html / 对照.html）
源/                页面内容（首页、语言页、路线图、台.md、对照.md、示例集来源）
静态/              CSS + JS（执行器.js = Web Worker 沙箱，台.js，对照.js，pyodide-加载器.js）
数据/示例集.json   官方示例 + 对照示例清单（预跑门禁的输入）
出/                构建产物（部署到 GitHub Pages / GitCode Pages）
.build_cache/      Pyodide 资产 + 语言仓库浅克隆缓存（已 gitignore）
```

## 构建

需要 Python 3.10+ 和 git。

```powershell
python 建站.py
```

构建流程：取版本 → 生成各页面 → 复制静态资源 → 抽取四门语言包 → 复制示例集 → **预跑门禁** → 自托管 Pyodide。
预跑门禁会在子进程里实跑每个官方示例和对照示例，任一失败则整个构建以非零码退出。

产物写入 `出/`，包含：`index.html`、`台/`、`对照/`、`路线图/`、`静态/{py,pyodide,*.js,*.css}`、`数据/{示例集,示例结果}.json`。

## 本地预览与人工验证

```powershell
python -m http.server 8080 --directory 出
```

然后浏览器打开：

### 工作台 http://localhost:8080/台/
- [ ] 页面加载正常，顶部有语言选择器
- [ ] 选「段言 / 光明 / 知行」时，「需求 + 选块」区和候选卡区隐藏；选「极快」时出现
- [ ] 段言里贴 `打印 "你好，世界！"。` → 点「跑」→ 首次会加载 Pyodide（约 5–20 秒）→ 结果框显示 `你好，世界！`
- [ ] 极快里输入需求（如「打印你好」）→ 点「选块」→ 出现候选卡 → 点某张候选卡 → 代码框自动填入组码 → 点「跑」→ 有输出
- [ ] 死循环超时：段言里贴 `遍历 _ 从 1 到 999999999：` 换行 `  1。` → 点跑 → 约 5 秒后提示「执行超时」，页面不崩；**再点一次跑仍能正常执行**（Worker 已自动重建）

### 对照 http://localhost:8080/对照/
- [ ] 4 列网格（极快 / 段言 / 光明 / 知行），每格独立「跑」按钮
- [ ] 顶部切换示例（「打印你好世界」/「算 1+2+3」）时，四格代码同步刷新
- [ ] 各格点「跑」都能出结果；「算 1+2+3」四门语言都输出 `6`

## 部署

`出/` 目录由 GitHub Actions 部署到 GitHub Pages，绑定 `ai.quye.com`（见 `源/CNAME`）。
双远端：`origin`（GitHub）+ `gitcode`（GitCode）。

```powershell
git push origin main
git push gitcode main
```

## 说明

- Pyodide 采用「自托管主 + CDN 兜底」并发加载：优先 `/静态/pyodide/`，失败回退 jsdelivr CDN。
- 执行走 Web Worker（`静态/执行器.js`），主线程 5 秒超时 `terminate()` 并重建 Worker。
- 极快独有「选块 → 组码」链路，调其 `jikuai.ai.retrieval.retrieve` + `glue.synthesize`；其余三门语言直接跑源码。
- 消息协议区分两类调用：`{类型:"跑"}` 走语言桥（源码是中文语言语法），`{类型:"跑Python"}` 直跑 Python（选块/组码等辅助调用）。

## 已知限制

- **极快选块走启发式（TF-IDF）而非向量检索**。极快 `retrieval.py` 用 `__file__` 往上 3 级定位 `stdlib/blocks/`，这假设自己在 `<repo>/src/jikuai/ai/`；但抽取后落在 `/极快/jikuai/ai/`（只有 2 层），上 3 级会走出包根。`执行器.js` 的 `准备语言()` 里做了热补丁，手动喂上 `索引.json`（105 个块）并以 `vector_index=None` 构造 Retriever。向量索引路径同样错，暂时跳过。彻底修法是让抽取器还原 `src/` 层级，留给 M3。
- **首次加载语言包是逐文件 fetch**，极快有 394 个文件 → 几百次串行请求。功能可用但偏慢，M3 可改为构建期打 zip + `shutil.unpack_archive`。
- `取版本()` 偶尔报「双端不同步」，只是提示（gitcode 与 github 的 HEAD 不一致），不阻断构建。
