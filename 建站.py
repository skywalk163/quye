"""quye.com 构建脚本 — 纯标准库，零第三方依赖"""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "出"
模板目录 = ROOT / "模板"
源目录 = ROOT / "源"
静态目录 = ROOT / "静态"

REPOS = {
    "极快": {"gitcode": "https://gitcode.com/skywalk163/jikuai", "github": "https://github.com/skywalk163/jikuai"},
    "段言": {"gitcode": "https://gitcode.com/skywalk163/duan", "github": "https://github.com/skywalk163/duan"},
    "光明": {"gitcode": "https://gitcode.com/skywalk163/light", "github": "https://github.com/skywalk163/light"},
    "知行": {"gitcode": "https://gitcode.com/skywalk163/zhixing", "github": "https://github.com/skywalk163/zhixing"},
}


def 清理():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)


def 取版本() -> dict:
    """用 git ls-remote 取各仓库 HEAD hash（不需要 clone），并做双端一致性检查。"""
    import subprocess

    def 取远端hash(url: str) -> str:
        try:
            r = subprocess.run(
                ["git", "ls-remote", url, "HEAD"],
                capture_output=True, text=True, timeout=20,
                encoding="utf-8", errors="replace"
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().split()[0][:12]
        except Exception:
            pass
        return "获取失败"

    版本 = {"语言": {}, "告警": []}
    for 名, urls in REPOS.items():
        gc = 取远端hash(urls["gitcode"])
        gh = 取远端hash(urls["github"])
        版本["语言"][名] = {"gitcode": gc, "github": gh}
        if gc != gh and "获取失败" not in (gc, gh):
            版本["告警"].append(f"{名}：双端不同步 gitcode={gc} github={gh}")
        if gc == "获取失败" and gh == "获取失败":
            版本["告警"].append(f"{名}：双端均获取失败（网络或仓库地址问题）")

    版本["构建时间"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for 条 in 版本["告警"]:
        print(f"  ! {条}")
    return 版本


BUILD_CACHE = ROOT / ".build_cache"

# M4 版本锁：浅克隆() 实际消费的 commit hash，构建结束写入 出/版本.json
快照记录: dict = {}


# 本地开发时可用的已有仓库路径（避免网络 clone）。
# 从 .env 或环境变量读取——不提交私人路径到 git。
# CI 里这些变量不存在 → 值为 None → 自动回退到 git clone。
# .env 格式：QUYE_LOCAL_极快=G:\traework\jikuai（见 .env.example）
def _载入env(env路径: Path) -> None:
    """极简 .env 加载器：只覆盖尚未设置的环境变量，不引入第三方依赖。"""
    if not env路径.exists():
        return
    for 原行 in env路径.read_text(encoding="utf-8-sig").splitlines():
        行 = 原行.strip()
        if not 行 or 行.startswith("#") or "=" not in 行:
            continue
        键, _, 值 = 行.partition("=")
        键 = 键.strip()
        值 = 值.strip().strip('"').strip("'")
        if 键 and 键 not in os.environ:
            os.environ[键] = 值


_载入env(ROOT / ".env")


def _本地路径(名: str) -> Path | None:
    """从 QUYE_LOCAL_<名> 环境变量（或 .env）读取本地仓库路径。

    未配置或路径不存在则返回 None → 浅克隆 回退到远端 clone。
    CI 里 .env 不存在 + 环境变量未设 → 全部走 clone，符合预期。
    """
    值 = os.environ.get(f"QUYE_LOCAL_{名}", "").strip()
    if not 值:
        return None
    p = Path(值).expanduser()
    return p if p.exists() else None


LOCAL_REPOS = {名: _本地路径(名) for 名 in ("极快", "段言", "光明", "知行")}


def 浅克隆(名: str, urls: dict) -> Path:
    """获取语言仓库根目录。优先本地路径 → gitcode → github。

    副作用：把实际使用的 commit hash 记入 快照记录（M4 版本锁）——
    取版本() 拿的是远端 HEAD，而这里拿的是构建真正消费的那个提交，
    本地路径 / 缓存未更新时两者会不同，产物必须标明后者。
    """
    根 = _取仓库根(名, urls)
    快照记录[名] = _读本地hash(根)
    return 根


def _取仓库根(名: str, urls: dict) -> Path:
    local = LOCAL_REPOS.get(名)
    if local and local.exists():
        print(f"    用本地路径 {local}")
        return local

    目标 = BUILD_CACHE / 名
    if 目标.exists():
        r = subprocess.run(
            ["git", "-C", str(目标), "fetch", "--depth", "1", "origin", "HEAD"],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace"
        )
        if r.returncode == 0:
            subprocess.run(
                ["git", "-C", str(目标), "reset", "--hard", "FETCH_HEAD"],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace"
            )
        else:
            print(f"    ! 更新 {名} 失败：{r.stderr.strip()[:100]}")
        return 目标

    目标.parent.mkdir(parents=True, exist_ok=True)
    # 依次尝试 gitcode → github（国内网络优先内网）
    错误汇总 = []
    for 端 in ("gitcode", "github"):
        url = urls[端]
        print(f"    尝试 {端}: {url}")
        r = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(目标)],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace"
        )
        if r.returncode == 0:
            return 目标
        错误汇总.append(f"{端}: {r.stderr.strip()[:150]}")
        # 清理失败的目标
        if 目标.exists():
            import shutil as _s
            _s.rmtree(目标, ignore_errors=True)
    raise RuntimeError(f"克隆 {名} 双端均失败：{'; '.join(错误汇总)}")


def _读本地hash(根: Path) -> dict:
    """读仓库工作副本的 HEAD hash + 提交时间。非 git 目录返回未知。"""
    def 跑(*参数) -> str:
        r = subprocess.run(
            ["git", "-C", str(根), *参数],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace"
        )
        return r.stdout.strip() if r.returncode == 0 else ""

    h = 跑("rev-parse", "HEAD")
    if not h:
        return {"hash": "未知", "提交时间": "", "路径": str(根)}
    return {
        "hash": h[:12],
        "提交时间": 跑("log", "-1", "--format=%cI"),
        "路径": str(根),
    }



def 抽取语言包(版本: dict) -> None:
    """按顺序调各语言抽取器。"""
    from 抽取器 import 极快 as 极快抽取
    from 抽取器 import 段言 as 段言抽取
    from 抽取器 import 光明 as 光明抽取
    from 抽取器 import 知行 as 知行抽取

    映射 = {
        "极快": (极快抽取.抽取, REPOS["极快"]),
        "段言": (段言抽取.抽取, REPOS["段言"]),
        "光明": (光明抽取.抽取, REPOS["光明"]),
        "知行": (知行抽取.抽取, REPOS["知行"]),
    }
    py目标 = OUT / "静态" / "py"
    py目标.mkdir(parents=True, exist_ok=True)
    数据目标 = OUT / "数据"
    数据目标.mkdir(parents=True, exist_ok=True)

    for 名, (抽取fn, urls) in 映射.items():
        print(f"    {名}...")
        仓库根 = 浅克隆(名, urls)
        抽取fn(仓库根, py目标 / 名)

    # 为每门语言生成清单.json
    for 名 in ["极快", "段言", "光明", "知行"]:
        目录 = py目标 / 名
        if not 目录.exists():
            continue
        文件s = []
        for p in sorted(目录.rglob("*")):
            if p.is_file() and p.suffix in {".py", ".jk", ".json"}:
                文件s.append(p.relative_to(目录).as_posix())
        (目录 / "清单.json").write_text(
            json.dumps({"文件": 文件s}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # 每门语言额外打一个 zip，供 Worker 一次拉取解包（M2 遗留：394 文件串行 fetch 过慢）
    #
    # 光明积木库的万余个 .light 源码只在构建期给块浏览器抽契约用，运行期浏览器拿的是
    # 块索引.json 里已内联的示例，不需要——排掉 blocks/，别让访客白下几 MB。
    # 但 选块.py + 索引.json 要留：工作台选块要在 Pyodide 里 import 选块 并 load_index，
    # 这俩是它的运行期依赖（索引 gzip 后进 zip 约 0.5 MB，且仅在用户真用光明时才下载）。
    import zipfile
    for 名 in ["极快", "段言", "光明", "知行"]:
        目录 = py目标 / 名
        if not 目录.exists():
            continue
        zip路径 = py目标 / f"{名}.zip"
        with zipfile.ZipFile(zip路径, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(目录.rglob("*")):
                if not p.is_file() or p.name == "清单.json":
                    continue
                相对 = p.relative_to(目录)
                # 积木库里只保留选块运行期要的两样，其余（blocks/ 源码树）不进包
                if "积木库" in 相对.parts and p.name not in ("选块.py", "索引.json"):
                    continue
                zf.write(p, 相对.as_posix())
        print(f"    {名}.zip 打包 {zip路径.stat().st_size // 1024} KB")



def 抽取并构建文档(版本: dict):
    """从四门语言仓库精选 md → 出/文档/，并生成前端搜索索引。"""
    from 抽取器 import 文档 as 文档抽取
    仓库根映射 = {名: 浅克隆(名, REPOS[名]) for 名 in ("极快", "段言", "光明", "知行")}
    清单 = json.loads((ROOT / "数据" / "文档清单.json").read_text(encoding="utf-8"))
    文档数据 = OUT / "数据" / "文档"
    成功 = 文档抽取.抽取(仓库根映射, 文档数据, 清单)

    文档根 = OUT / "文档"
    文档根.mkdir(parents=True, exist_ok=True)
    # 索引：按分组列出 + 搜索框
    分组 = {}
    for 条 in 成功:
        分组.setdefault(条.get("分组", "其他"), []).append(条)
    项 = []
    for 组名, 组 in 分组.items():
        项.append(f"<h2>{转义(组名)}</h2><ul>")
        for 条 in 组:
            项.append(f"<li><a href='/文档/{条['slug']}/'>{转义(条['标题'])}</a></li>")
        项.append("</ul>")
    搜索框 = (
        "<div class='文档搜索'>"
        "<input type='search' id='文档搜索框' placeholder='搜索文档标题/正文…' "
        "autocomplete='off' aria-label='搜索文档'>"
        "<ul id='文档搜索结果' hidden></ul>"
        "</div>"
    )
    索引html = (
        "<section class='文档索引'><h1>文档</h1>\n"
        + 搜索框 + "\n<div id='文档分组'>\n" + "\n".join(项) + "\n</div></section>"
        + '\n<script src="/静态/文档搜索.js" defer></script>'
    )
    (文档根 / "index.html").write_text(
        渲染页面(
            "文档 — quye", 索引html, 版本,
            描述="极快、段言、光明、知行四门语言的安装、入门、语言特色与工具链文档合集，支持全文搜索。",
            路径="/文档/",
        ),
        encoding="utf-8",
    )
    # 各文档页 + 搜索索引
    搜索索引 = []
    for 条 in 成功:
        md = (文档数据 / f"{条['slug']}.md").read_text(encoding="utf-8")
        页 = 渲染页面(
            f"{条['标题']} — quye", 简易md转html(md), 版本, 讨论语言=条["语言"],
            描述=摘要(md) or 条["标题"], 路径=f"/文档/{条['slug']}/",
        )
        目录 = 文档根 / 条["slug"]
        目录.mkdir(parents=True, exist_ok=True)
        (目录 / "index.html").write_text(页, encoding="utf-8")
        # 搜索索引：标题 + 分组 + 正文纯文本（去 md 标记，截断以控体积）
        正文 = re.sub(r'[#*`>\[\]\-]', ' ', md)
        正文 = re.sub(r'\s+', ' ', 正文).strip()
        搜索索引.append({
            "slug": 条["slug"],
            "标题": 条["标题"],
            "分组": 条.get("分组", "其他"),
            "语言": 条["语言"],
            "正文": 正文[:2000],
        })
    (OUT / "数据" / "文档搜索索引.json").write_text(
        json.dumps(搜索索引, ensure_ascii=False), encoding="utf-8"
    )
    print(f"    文档搜索索引：{len(搜索索引)} 篇")


def 抽取学习素材() -> None:
    """抽段言 10 套练习 + 光明 9 课 + 极快/知行 若干示例到 出/数据/学习素材/。

    浅克隆() 幂等（本地路径直接返回；缓存已存在则 fetch 更新），
    这里二次调用不会重复 clone。
    """
    from 抽取器 import 学习 as 学习抽取
    段言根 = 浅克隆("段言", REPOS["段言"])
    光明根 = 浅克隆("光明", REPOS["光明"])
    极快根 = 浅克隆("极快", REPOS["极快"])
    知行根 = 浅克隆("知行", REPOS["知行"])
    清单 = json.loads((ROOT / "数据" / "学习清单.json").read_text(encoding="utf-8"))
    学习抽取.抽取(
        段言根, 光明根, OUT / "数据" / "学习素材", 清单,
        极快根=极快根, 知行根=知行根,
    )


PYODIDE_VERSION = "0.26.4"
PYODIDE_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full"
# Pyodide 核心资产（用户点"跑"前不加载，但预先自托管以备）
PYODIDE_ASSETS = [
    "pyodide.js",
    "pyodide.mjs",
    "pyodide.asm.js",
    "pyodide.asm.wasm",
    "pyodide-lock.json",
    "python_stdlib.zip",
]


def 下载pyodide() -> None:
    """自托管 Pyodide 关键资产。已存在则跳过；拉取失败不阻塞构建（用户端降级 CDN）。"""
    import urllib.request
    目标 = OUT / "静态" / "pyodide"
    目标.mkdir(parents=True, exist_ok=True)
    # 缓存目录：避免每次构建重下（.build_cache 已 gitignore）
    缓存 = BUILD_CACHE / "pyodide"
    缓存.mkdir(parents=True, exist_ok=True)
    for name in PYODIDE_ASSETS:
        缓存文件 = 缓存 / name
        if not (缓存文件.exists() and 缓存文件.stat().st_size > 1000):
            url = f"{PYODIDE_BASE}/{name}"
            print(f"    拉 {name}...")
            try:
                urllib.request.urlretrieve(url, 缓存文件)
            except Exception as e:
                print(f"    ! 拉 {name} 失败：{str(e)[:80]}；用户端将降级到 CDN")
                continue
        # 从缓存复制到产物
        shutil.copy2(缓存文件, 目标 / name)


def 转义(s) -> str:
    """HTML 转义（模板注入用）。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def 简易md转html(md: str) -> str:
    """极简 markdown→HTML：标题、段落、列表、代码块、粗体。不引第三方库。"""
    lines = md.split("\n")
    html_parts = []
    in_code = False
    in_list = False
    for line in lines:
        if line.startswith("```"):
            if in_code:
                html_parts.append("</code></pre>")
                in_code = False
            else:
                lang = line[3:].strip()
                html_parts.append(f'<pre><code class="lang-{lang}">')
                in_code = True
            continue
        if in_code:
            html_parts.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue
        if line.startswith("# "):
            html_parts.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[2:])
            html_parts.append(f"<li>{content}</li>")
        elif line.strip() == "":
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("")
        else:
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
            html_parts.append(f"<p>{content}</p>")
    if in_list:
        html_parts.append("</ul>")
    return "\n".join(html_parts)


SITE = "https://quye.com"
默认描述 = "quye — 中文 AI 编程中心：四门中文编程语言（极快/段言/光明/知行）统一门户，浏览器里零安装写中文代码，纯标准库检索无需 GPU。"

# 已渲染页面的站内路径，构建期收集用于 sitemap.xml
_已渲染路径: set = set()


def 渲染页面(标题: str, 内容html: str, 版本: dict, 讨论语言: str = "极快",
         描述: str = "", 路径: str = "/") -> str:
    """把内容嵌入基础模板。讨论语言决定页脚讨论区指向哪个语言仓库。

    描述：<meta description>/OG 用，空则回退默认站点描述。
    路径：canonical/og:url 用的站内绝对路径（以 / 开头），同时收集进 sitemap。
    """
    模板 = (模板目录 / "基础.html").read_text(encoding="utf-8")
    讨论区 = (源目录 / "片段" / "讨论区.html").read_text(encoding="utf-8").replace(
        "{{讨论语言}}", 讨论语言
    )
    版本json = json.dumps(版本, ensure_ascii=False, indent=2)
    页脚版本 = " · ".join(
        f'{名} {v.get("gitcode", "?")}'
        for 名, v in 版本.get("语言", {}).items()
    )
    描述文本 = (描述 or 默认描述).strip()
    if 路径:
        _已渲染路径.add(路径)
    return (
        模板
        .replace("{{标题}}", 标题)
        .replace("{{描述}}", 转义(描述文本))
        .replace("{{路径}}", 转义(路径))
        .replace("{{内容}}", 内容html)
        .replace("{{讨论区}}", 讨论区)
        .replace("{{页脚版本}}", 页脚版本)
        .replace("{{构建时间}}", 版本.get("构建时间", ""))
        .replace("{{版本json}}", 版本json)
    )


def 摘要(md: str, 上限: int = 150) -> str:
    """从 md 抽第一段正文当描述（去标题/列表符/代码块）。"""
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-") or s.startswith("```"):
            continue
        s = re.sub(r'[*`>#\[\]]', '', s)
        return s[:上限]
    return ""


def 写sitemap():
    """按 _已渲染路径 生成 sitemap.xml + robots.txt。"""
    日期 = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    条目 = []
    for 路径 in sorted(_已渲染路径):
        条目.append(
            f"  <url><loc>{SITE}{转义(路径)}</loc>"
            f"<lastmod>{日期}</lastmod></url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(条目) + "\n</urlset>\n"
    )
    (OUT / "sitemap.xml").write_text(xml, encoding="utf-8")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8"
    )
    print(f"    sitemap.xml：{len(条目)} 个页面")


def 构建首页(版本: dict):
    内容 = (源目录 / "首页.html").read_text(encoding="utf-8")
    html = 渲染页面("quye — 中文 AI 编程中心", 内容, 版本, 路径="/")
    (OUT / "index.html").write_text(html, encoding="utf-8")


def 构建语言页(版本: dict):
    语言目录 = OUT / "语言"
    语言目录.mkdir(parents=True, exist_ok=True)
    名单 = []
    for md_file in sorted((源目录 / "语言").glob("*.md")):
        名 = md_file.stem
        md = md_file.read_text(encoding="utf-8")
        内容html = 简易md转html(md)
        html = 渲染页面(
            f"{名} — quye", 内容html, 版本, 讨论语言=名,
            描述=f"{名}：{摘要(md)}", 路径=f"/语言/{名}.html",
        )
        (语言目录 / f"{名}.html").write_text(html, encoding="utf-8")
        # 索引卡片的一句话简介：取 md 里第一段非标题正文
        简介 = ""
        for line in md.splitlines():
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith("-"):
                简介 = s
                break
        名单.append((名, 简介))

    # 索引页：导航栏的 /语言/ 指向这里
    卡片 = "\n".join(
        f"<li><a href='/语言/{名}.html'><strong>{转义(名)}</strong>"
        f"<div>{转义(简介[:60])}</div></a></li>"
        for 名, 简介 in 名单
    )
    索引html = (
        "<section class='语言索引'><h1>四门中文编程语言</h1>"
        "<p>同一个需求四种写法，每门语言的哲学一目了然。</p>"
        f"<ul class='语言组'>{卡片}</ul>"
        "<p><a href='/对照/'>去对照页并排跑同一需求 →</a></p></section>"
    )
    (语言目录 / "index.html").write_text(
        渲染页面(
            "语言 — quye", 索引html, 版本,
            描述="极快、段言、光明、知行四门中文编程语言介绍与对比入口。",
            路径="/语言/",
        ),
        encoding="utf-8",
    )


def 构建路线图(版本: dict):
    md = (源目录 / "路线图.md").read_text(encoding="utf-8")
    内容html = 简易md转html(md)
    html = 渲染页面("路线图 — quye", 内容html, 版本, 描述=摘要(md), 路径="/路线图/")
    路线图目录 = OUT / "路线图"
    路线图目录.mkdir(parents=True, exist_ok=True)
    (路线图目录 / "index.html").write_text(html, encoding="utf-8")


def 构建本地(版本: dict):
    md = (源目录 / "本地.md").read_text(encoding="utf-8")
    html = 渲染页面(
        "本地开发 — quye", 简易md转html(md), 版本,
        描述="四门中文编程语言的本地安装、CLI 用法与 IDE 配置指南。",
        路径="/本地/",
    )
    目录 = OUT / "本地"
    目录.mkdir(parents=True, exist_ok=True)
    (目录 / "index.html").write_text(html, encoding="utf-8")


def 构建工作台(版本: dict):
    md = (源目录 / "台.md").read_text(encoding="utf-8")
    内容顶部 = 简易md转html(md)
    body = (模板目录 / "台.html").read_text(encoding="utf-8")
    html = 渲染页面(
        "工作台 — quye", 内容顶部 + body + '\n<script src="/静态/台.js"></script>', 版本,
        描述="在浏览器里用中文描述需求，AI 选块组码后立即运行，无需安装任何环境。",
        路径="/台/",
    )
    工作台目录 = OUT / "台"
    工作台目录.mkdir(parents=True, exist_ok=True)
    (工作台目录 / "index.html").write_text(html, encoding="utf-8")


def 构建对照(版本: dict):
    md = (源目录 / "对照.md").read_text(encoding="utf-8")
    内容顶部 = 简易md转html(md)
    body = (模板目录 / "对照.html").read_text(encoding="utf-8")
    html = 渲染页面(
        "对照 — quye", 内容顶部 + body + '\n<script src="/静态/对照.js"></script>', 版本,
        描述="同一个需求，极快/段言/光明/知行四门语言并排运行，直观对比语法差异。",
        路径="/对照/",
    )
    目录 = OUT / "对照"
    目录.mkdir(parents=True, exist_ok=True)
    (目录 / "index.html").write_text(html, encoding="utf-8")


def 构建学习(版本: dict):
    """学习区：索引页 + 各语言关卡页。依赖 出/数据/学习基线.json（预跑产出）。"""
    清单 = json.loads((ROOT / "数据" / "学习清单.json").read_text(encoding="utf-8"))
    基线 = json.loads((OUT / "数据" / "学习基线.json").read_text(encoding="utf-8"))
    基线map = {(语言, x["关卡"]): x for 语言 in 基线 for x in 基线[语言]}
    素材根 = OUT / "数据" / "学习素材"
    学根 = OUT / "学"
    学根.mkdir(parents=True, exist_ok=True)
    语言表 = list(清单.keys())

    # 索引页
    项 = []
    for 语言 in 语言表:
        项.append(f"<h2>{语言}</h2><ul class='关卡组'>")
        for 条 in 清单[语言]:
            关卡 = 条["关卡"]
            项.append(
                f"<li><a href='/学/{语言}/{关卡}/'>"
                f"{条['序号']} · {转义(条['标题'])}</a></li>"
            )
        项.append("</ul>")
    索引内容 = (模板目录 / "学索引.html").read_text(encoding="utf-8").replace(
        "{{关卡列表}}", "\n".join(项)
    )
    总关数 = sum(len(清单[语言]) for 语言 in 语言表)
    md = (源目录 / "学.md").read_text(encoding="utf-8")
    页 = 渲染页面(
        "学习区 — quye",
        简易md转html(md) + 索引内容 + '\n<script src="/静态/学.js"></script>',
        版本,
        描述=f"从零开始学四门中文编程语言——{总关数} 个浏览器内判对关卡，在线写代码、即时验证。",
        路径="/学/",
    )
    (学根 / "index.html").write_text(页, encoding="utf-8")

    # 关卡清单交给前端（首页「每日一题」+ 进度导入导出校验都要用）
    (OUT / "数据" / "学习清单.json").write_text(
        json.dumps(清单, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 关卡页
    关卡模板 = (模板目录 / "学关卡.html").read_text(encoding="utf-8")
    for 语言 in 语言表:
        for 条 in 清单[语言]:
            关卡 = 条["关卡"]
            素材 = 素材根 / 语言 / 关卡
            题干 = 简易md转html((素材 / "题干.md").read_text(encoding="utf-8"))
            骨架源 = 素材 / "骨架.txt"
            骨架文本 = 骨架源.read_text(encoding="utf-8") if 骨架源.exists() else ""
            骨架 = 骨架文本 if 骨架文本.strip() else ""
            b = 基线map.get((语言, 关卡), {})
            body = (关卡模板
                    .replace("{{语言}}", 语言)
                    .replace("{{关卡}}", 关卡)
                    .replace("{{标题}}", 转义(f"{条['序号']} · {条['标题']}"))
                    .replace("{{题干}}", 题干)
                    .replace("{{骨架}}", 转义(骨架))
                    .replace("{{在线可判}}", "1" if b.get("在线可判") else "0"))
            页 = 渲染页面(
                f"{条['标题']} — {语言}学习 — quye",
                body + '\n<script src="/静态/学.js"></script>',
                版本,
                讨论语言=语言,
                描述=f"{语言}学习第 {条['序号']} 关：{条['标题']}。在浏览器内编写代码并自动判对。",
                路径=f"/学/{语言}/{关卡}/",
            )
            目录 = 学根 / 语言 / 关卡
            目录.mkdir(parents=True, exist_ok=True)
            (目录 / "index.html").write_text(页, encoding="utf-8")


# ---- 块浏览器：多语言块/积木的统一 schema ----
#
# 极快与光明两边的索引字段长得不一样（极快 领域 是列表、有 导出/示例；光明 领域 是
# 字符串、描述与输入普遍为空，契约只写在 .light 源码头注释里）。这里各自 normalize
# 成同一份 schema 再合并，前端只认这一份：
#   {名称, 语言, 领域(str), 描述, 输入:[{名,类型}], 输出:{类型},
#    导出:[str], 稳定性, 层级, 示例, 可运行}


def _出类型(输出) -> str:
    """输出.类型 有时是字符串、有时嵌一层 dict，抹平成字符串。"""
    t = (输出 or {}).get("类型", "?")
    return t.get("类型", "?") if isinstance(t, dict) else (t or "?")


def _极快块表() -> list[dict]:
    """极快标准库块：索引.json 不含「示例」（上游刻意窄化），逐块读 块.json 补上。"""
    blocks根 = OUT / "静态" / "py" / "极快" / "stdlib" / "blocks"
    索引路径 = blocks根 / "索引.json"
    if not 索引路径.exists():
        raise FileNotFoundError(f"极快块索引缺失：{索引路径}")
    表 = []
    for b in json.loads(索引路径.read_text(encoding="utf-8")).get("块", []):
        领域 = (b.get("领域") or ["未分类"])[0]
        块json = blocks根 / 领域 / b["名称"] / "块.json"
        示例 = (
            json.loads(块json.read_text(encoding="utf-8")).get("示例", "")
            if 块json.exists() else ""
        )
        表.append({
            "名称": b["名称"],
            "语言": "极快",
            "领域": 领域,
            "描述": b.get("描述", ""),
            "输入": [{"名": i.get("名", "?"), "类型": i.get("类型", "?")}
                     for i in (b.get("输入") or [])],
            "输出": {"类型": _出类型(b.get("输出"))},
            "导出": b.get("导出") or [b["名称"]],
            "稳定性": b.get("稳定性", ""),
            "层级": b.get("层级", 0),
            "示例": 示例,
            # 极快示例是上游手写的官方示例，视为可跑（跑挂了前端会显示报错）
            "可运行": bool(示例),
        })
    return 表


# 光明 .light 积木的头注释契约，形如：
#   # 积木：各元素ELU（数据领域，自动生成）
#   # 契约：输入 [列表] → 输出 [列表]（各元素ELU）
#   导出 ELU
#   段落 ELU 接收 列表：
_光明积木行 = re.compile(r"^#\s*积木：(.+?)（")
_光明契约行 = re.compile(r"^#\s*契约：输入\s*\[(.*?)\]\s*→\s*输出\s*\[?([^\]（]*)\]?(?:（(.+?)）)?")
_光明段落行 = re.compile(r"^段落\s+(\S+)\s+接收\s+(.+?)：")

# 按契约类型造示例入参。类型名取自光明契约注释里出现过的写法。
_光明样例值 = {
    "列表": "[1, 2, 3]",
    "数": "3",
    "小数": "2.5",
    "文本": "'光明'",
    "逻辑": "真",
    "字典": "{}",
    "数列": "[1, 2, 3]",
}


def _解析光明积木(源码: str, 名称: str) -> dict:
    """从 .light 源码头注释 + 段落签名里抠出契约。

    光明 索引.json 的 描述/输入 字段普遍是空的（上游生成器没填），真正的契约信息
    只在源码头两行注释里，所以这里以源码为准。
    """
    描述, 入类型串, 出类型 = "", "", "任意"
    段落名, 形参 = 名称, []
    for 行 in 源码.splitlines():
        行 = 行.strip()
        if not 描述:
            m = _光明积木行.match(行)
            if m:
                描述 = m.group(1).strip()
        m = _光明契约行.match(行)
        if m:
            入类型串 = m.group(1).strip()
            出类型 = (m.group(2) or "任意").strip() or "任意"
            if not 描述 and m.group(3):
                描述 = m.group(3).strip()
        m = _光明段落行.match(行)
        if m:
            段落名 = m.group(1)
            形参 = [p.strip() for p in m.group(2).split(",") if p.strip()]
            break  # 段落签名是头部最后一行有用信息，到此为止
    类型表 = [t.strip() for t in 入类型串.split(",") if t.strip()]
    if len(类型表) != len(形参):
        # 契约与签名对不上（生成器留下的噪声），类型退化成「任意」但保住形参名
        类型表 = (类型表 + ["任意"] * len(形参))[:len(形参)]
    return {
        "描述": 描述,
        "输入": [{"名": p, "类型": t} for p, t in zip(形参, 类型表)],
        "输出": {"类型": 出类型},
        "段落名": 段落名,
    }


def _光明块表() -> list[dict]:
    """光明积木库：索引给块清单，契约与示例从 .light 源码现场解析 + 合成。

    积木本身只是「定义一个段落」，跑起来不会有任何输出，所以这里按契约合成一行
    `打印(段落名(样例入参))` 追加在源码后面当示例——这份合成示例同时也是
    预跑器.预跑光明积木() 的输入，跑通了才在页面上给「在浏览器里跑」按钮。
    """
    积木根 = OUT / "静态" / "py" / "光明" / "积木库"
    索引路径 = 积木根 / "索引.json"
    if not 索引路径.exists():
        print(f"    ! 光明积木索引缺失，跳过光明积木：{索引路径}")
        return []
    表 = []
    for b in json.loads(索引路径.read_text(encoding="utf-8")).get("块", []):
        名称 = b.get("名称") or ""
        领域 = b.get("领域") or "未分类"
        # 索引里的 路径 形如 blocks_v5/中文/Unicode码点.light；抽取期 blocks_v5 已落成
        # 积木库/blocks，所以剥掉这层前缀即可
        路径 = b.get("路径") or f"{领域}/{名称}.light"
        if 路径.startswith("blocks_v5/"):
            路径 = 路径[len("blocks_v5/"):]
        源文件 = 积木根 / "blocks" / 路径
        if not 源文件.exists():
            continue
        源码 = 源文件.read_text(encoding="utf-8")
        契约 = _解析光明积木(源码, 名称)
        入参 = ", ".join(_光明样例值.get(i["类型"], "1") for i in 契约["输入"])
        示例 = f"{源码.rstrip()}\n\n打印({契约['段落名']}({入参}))\n"
        表.append({
            "名称": 名称,
            "语言": "光明",
            "领域": 领域,
            "描述": 契约["描述"] or b.get("描述", "") or 名称,
            "输入": 契约["输入"],
            "输出": 契约["输出"],
            "导出": [b.get("导出名") or 契约["段落名"]],
            "稳定性": b.get("稳定性", ""),
            "层级": b.get("层级", 0),
            "示例": 示例,
            # 由 预跑光明积木() 回填：只有构建期真跑出输出的积木才置 True
            "可运行": False,
        })
    return 表


def 构建块浏览器(版本: dict):
    """M7 块浏览器 /块：极快标准库块 + 光明积木库，合并成一份多语言列表。

    两边索引各自 normalize 成统一 schema（见 _极快块表 / _光明块表），产出两份数据：
    - 出/数据/块清单.json：卡片要的那几个字段，首屏拉它（示例源码占全量索引九成体积）
    - 出/数据/块索引.json：全量含示例源码，点开某块才拉

    页面自身只出筛选按钮与一个空网格——上万张卡片改由前端按当前语言/领域/搜索现渲染
    （见 块浏览.js），HTML 不再随块数膨胀（原先上万卡片会把 index.html 撑到 3 MB+）。
    """
    块列表 = _极快块表() + _光明块表()

    # 光明积木的「可运行」标：构建期用光明解释器实跑合成示例，跑出输出才算可运行
    import 预跑器
    预跑器.预跑光明积木(块列表, OUT / "静态" / "py" / "光明")

    (OUT / "数据" / "块索引.json").write_text(
        json.dumps({"块": 块列表}, ensure_ascii=False), encoding="utf-8"
    )

    # 轻清单：签名在构建期拼成字符串，前端拿来就画，不用再遍历 输入 数组
    清单 = [{
        "名称": b["名称"],
        "语言": b["语言"],
        "领域": b["领域"],
        "描述": b["描述"],
        "签名": (f'{b["导出"][0]}'
                 f'({"、".join(i["名"] for i in b["输入"]) or "无入参"})'
                 f' → {b["输出"]["类型"]}'),
        "稳定性": b["稳定性"],
    } for b in 块列表]
    (OUT / "数据" / "块清单.json").write_text(
        json.dumps({"块": 清单}, ensure_ascii=False), encoding="utf-8"
    )

    语言分组: dict[str, int] = {}
    领域分组: dict[str, int] = {}
    for b in 块列表:
        语言分组[b["语言"]] = 语言分组.get(b["语言"], 0) + 1
        领域分组[b["领域"]] = 领域分组.get(b["领域"], 0) + 1

    语言标签 = "\n".join(
        f"<button type='button' class='语言标签' data-语言='{转义(语)}'>{转义(语)} {数}</button>"
        for 语, 数 in sorted(语言分组.items(), key=lambda kv: -kv[1])
    )
    领域标签 = "\n".join(
        f"<button type='button' class='领域标签' data-领域='{转义(域)}'>{转义(域)} {数}</button>"
        for 域, 数 in sorted(领域分组.items())
    )
    可跑数 = sum(1 for b in 块列表 if b["可运行"])
    语言概览 = "、".join(f"{语} {数}" for 语, 数 in sorted(语言分组.items(), key=lambda kv: -kv[1]))
    内容 = (
        "<section class='块浏览器'>"
        "<h1>块 / 积木浏览器</h1>"
        f"<p>共 {len(块列表)} 个可复用单元（{语言概览}），横跨 {len(领域分组)} 个领域。"
        "点任一块看签名与描述，其中 "
        f"{可跑数} 个能直接在浏览器里跑示例。</p>"
        "<p class='页面引导'>「块」是把常用能力封装成可组合单元的做法，"
        "极快与光明都走这条路线——极快叫块、光明叫积木。"
        "段言、知行目前走「直接写代码」路径，"
        "想上手请到 <a href='/学/'>学习区</a> 逐关练习。</p>"
        "<div class='块搜索'><input type='search' id='块搜索框' "
        "placeholder='搜索块名或描述…' autocomplete='off' aria-label='搜索块'></div>"
        f"<div class='语言筛选'>"
        f"<button type='button' class='语言标签 激活' data-语言='全部'>全部语言 {len(块列表)}</button>"
        f"{语言标签}</div>"
        f"<div class='领域筛选'>"
        f"<button type='button' class='领域标签 激活' data-领域='全部'>全部领域 {len(块列表)}</button>"
        f"{领域标签}</div>"
        "<div id='块详情' class='块详情' hidden></div>"
        "<p class='块提示' id='块提示' aria-live='polite'>加载积木索引…</p>"
        "<div class='块网格' id='块网格'></div>"
        "</section>"
        '\n<script src="/静态/块浏览.js"></script>'
    )
    页 = 渲染页面(
        "块 / 积木浏览器 — quye", 内容, 版本,
        描述=f"浏览 {len(块列表)} 个中文编程可复用单元（{语言概览}）：按语言与领域筛选、查看签名与描述、在线运行示例。",
        路径="/块/",
    )
    块根 = OUT / "块"
    块根.mkdir(parents=True, exist_ok=True)
    (块根 / "index.html").write_text(页, encoding="utf-8")
    print(f"    块浏览器：{len(块列表)} 块（{语言概览}）/ {len(领域分组)} 个领域，可跑 {可跑数}")


def 复制静态():
    目标 = OUT / "静态"
    if 目标.exists():
        shutil.rmtree(目标)
    shutil.copytree(静态目录, 目标)
    # 复制 CNAME 到构建产物根目录（GitHub Pages 需要）
    cname = 源目录 / "CNAME"
    if cname.exists():
        shutil.copy2(cname, OUT / "CNAME")


def 写版本文件(版本: dict):
    # M4 版本锁：合并「远端 HEAD hash」与「构建期实际消费的 commit hash」
    版本 = dict(版本)
    版本["构建快照"] = 快照记录
    (OUT / "版本.json").write_text(
        json.dumps(版本, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    print("[quye] 构建开始")
    清理()
    print("  取版本...")
    版本 = 取版本()
    print("  构建首页...")
    构建首页(版本)
    print("  构建语言页...")
    构建语言页(版本)
    print("  构建路线图...")
    构建路线图(版本)
    print("  构建本地开发...")
    构建本地(版本)
    print("  构建工作台...")
    构建工作台(版本)
    print("  构建对照...")
    构建对照(版本)
    print("  复制静态资源...")
    复制静态()
    # 抽取语言包必须在 复制静态 之后：复制静态会 rmtree 出/静态 再重建
    print("  抽取语言包...")
    抽取语言包(版本)
    # 抽取学习素材
    print("  抽取学习素材...")
    抽取学习素材()
    # 预跑必须在 抽取语言包 之后：它要用 出/静态/py/<语言> 里的解释器
    print("  复制示例集...")
    数据目录 = OUT / "数据"
    数据目录.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "数据" / "示例集.json", 数据目录 / "示例集.json")
    print("  预跑示例...")
    import 预跑器
    预跑器.预跑(数据目录, OUT / "静态" / "py")
    print("  预跑学习基线...")
    预跑器.预跑学习基线(数据目录, OUT / "静态" / "py")
    print("  构建学习区...")
    构建学习(版本)
    print("  构建块浏览器...")
    构建块浏览器(版本)
    print("  抽取并构建文档...")
    抽取并构建文档(版本)
    print("  自托管 Pyodide...")
    下载pyodide()
    print("  生成 sitemap + robots.txt...")
    写sitemap()
    写版本文件(版本)
    print(f"[quye] 构建完成 -> {OUT}")


if __name__ == "__main__":
    main()
