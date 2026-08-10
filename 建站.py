"""quye.com 构建脚本 — 纯标准库，零第三方依赖"""
import json
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
                capture_output=True, text=True, timeout=20
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

# 本地开发时可用的已有仓库路径（避免网络 clone）
# CI 环境中这些路径不存在，会自动回退到 git clone
LOCAL_REPOS = {
    "极快": Path(r"G:\traework\jikuai"),
    "段言": Path(r"C:\dumatework\duan"),
    "光明": None,  # 本地无，强制 clone
    "知行": Path(r"g:\zhixing"),
}


def 浅克隆(名: str, urls: dict) -> Path:
    """获取语言仓库根目录。优先本地路径 → gitcode → github。"""
    local = LOCAL_REPOS.get(名)
    if local and local.exists():
        print(f"    用本地路径 {local}")
        return local

    目标 = BUILD_CACHE / 名
    if 目标.exists():
        r = subprocess.run(
            ["git", "-C", str(目标), "fetch", "--depth", "1", "origin", "HEAD"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            subprocess.run(
                ["git", "-C", str(目标), "reset", "--hard", "FETCH_HEAD"],
                capture_output=True, text=True, timeout=60
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
            capture_output=True, text=True, timeout=300
        )
        if r.returncode == 0:
            return 目标
        错误汇总.append(f"{端}: {r.stderr.strip()[:150]}")
        # 清理失败的目标
        if 目标.exists():
            import shutil as _s
            _s.rmtree(目标, ignore_errors=True)
    raise RuntimeError(f"克隆 {名} 双端均失败：{'; '.join(错误汇总)}")


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


def 渲染页面(标题: str, 内容html: str, 版本: dict) -> str:
    """把内容嵌入基础模板。"""
    模板 = (模板目录 / "基础.html").read_text(encoding="utf-8")
    讨论区 = (源目录 / "片段" / "讨论区.html").read_text(encoding="utf-8")
    版本json = json.dumps(版本, ensure_ascii=False, indent=2)
    页脚版本 = " · ".join(
        f'{名} {v.get("gitcode", "?")}'
        for 名, v in 版本.get("语言", {}).items()
    )
    return (
        模板
        .replace("{{标题}}", 标题)
        .replace("{{内容}}", 内容html)
        .replace("{{讨论区}}", 讨论区)
        .replace("{{页脚版本}}", 页脚版本)
        .replace("{{构建时间}}", 版本.get("构建时间", ""))
        .replace("{{版本json}}", 版本json)
    )


def 构建首页(版本: dict):
    内容 = (源目录 / "首页.html").read_text(encoding="utf-8")
    html = 渲染页面("quye — 中文 AI 编程中心", 内容, 版本)
    (OUT / "index.html").write_text(html, encoding="utf-8")


def 构建语言页(版本: dict):
    语言目录 = OUT / "语言"
    语言目录.mkdir(parents=True, exist_ok=True)
    for md_file in (源目录 / "语言").glob("*.md"):
        名 = md_file.stem
        md = md_file.read_text(encoding="utf-8")
        内容html = 简易md转html(md)
        html = 渲染页面(f"{名} — quye", 内容html, 版本)
        (语言目录 / f"{名}.html").write_text(html, encoding="utf-8")


def 构建路线图(版本: dict):
    md = (源目录 / "路线图.md").read_text(encoding="utf-8")
    内容html = 简易md转html(md)
    html = 渲染页面("路线图 — quye", 内容html, 版本)
    路线图目录 = OUT / "路线图"
    路线图目录.mkdir(parents=True, exist_ok=True)
    (路线图目录 / "index.html").write_text(html, encoding="utf-8")


def 构建工作台(版本: dict):
    md = (源目录 / "台.md").read_text(encoding="utf-8")
    内容顶部 = 简易md转html(md)
    body = (模板目录 / "台.html").read_text(encoding="utf-8")
    html = 渲染页面("工作台 — quye", 内容顶部 + body + '\n<script src="/静态/台.js"></script>', 版本)
    工作台目录 = OUT / "台"
    工作台目录.mkdir(parents=True, exist_ok=True)
    (工作台目录 / "index.html").write_text(html, encoding="utf-8")


def 构建对照(版本: dict):
    md = (源目录 / "对照.md").read_text(encoding="utf-8")
    内容顶部 = 简易md转html(md)
    body = (模板目录 / "对照.html").read_text(encoding="utf-8")
    html = 渲染页面("对照 — quye", 内容顶部 + body + '\n<script src="/静态/对照.js"></script>', 版本)
    目录 = OUT / "对照"
    目录.mkdir(parents=True, exist_ok=True)
    (目录 / "index.html").write_text(html, encoding="utf-8")


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
    print("  构建工作台...")
    构建工作台(版本)
    print("  构建对照...")
    构建对照(版本)
    print("  复制静态资源...")
    复制静态()
    # 抽取语言包必须在 复制静态 之后：复制静态会 rmtree 出/静态 再重建
    print("  抽取语言包...")
    抽取语言包(版本)
    # 预跑必须在 抽取语言包 之后：它要用 出/静态/py/<语言> 里的解释器
    print("  复制示例集...")
    数据目录 = OUT / "数据"
    数据目录.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "数据" / "示例集.json", 数据目录 / "示例集.json")
    print("  预跑示例...")
    import 预跑器
    预跑器.预跑(数据目录, OUT / "静态" / "py")
    print("  自托管 Pyodide...")
    下载pyodide()
    写版本文件(版本)
    print(f"[quye] 构建完成 -> {OUT}")


if __name__ == "__main__":
    main()
