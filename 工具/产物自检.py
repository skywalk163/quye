"""构建产物自检：关键路由存在 + 站内链接无死链（spec §4.4 门禁 #2）。

用法：先 python 建站.py，再 python 工具/产物自检.py
退出码：全部通过 0，有问题 1。
"""
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "出"

# 必须存在的关键产物
关键产物 = [
    "index.html",
    "台/index.html",
    "对照/index.html",
    "学/index.html",
    "本地/index.html",
    "文档/index.html",
    "块/index.html",
    "路线图/index.html",
    "学/段言/hello/index.html",
    "学/光明/09_异常/index.html",
    "数据/学习基线.json",
    "数据/学习清单.json",
    "数据/示例集.json",
    "数据/示例结果.json",
    "数据/文档搜索索引.json",
    "数据/块索引.json",
    "静态/学.js",
    "静态/台.js",
    "静态/对照.js",
    "静态/执行器.js",
    "静态/讨论区.js",
    "静态/文档搜索.js",
    "静态/每日一题.js",
    "静态/块浏览.js",
    "静态/样式.css",
    "静态/py/极快.zip",
    "静态/py/段言.zip",
    "静态/py/光明.zip",
    "静态/py/知行.zip",
    "版本.json",
    "sitemap.xml",
    "robots.txt",
    "CNAME",
]

# 站内链接 → 产物文件的映射规则（目录型路由补 index.html）
def 解析站内链接(href: str):
    if not href.startswith("/") or href.startswith("//"):
        return None
    路径 = href.split("#")[0].split("?")[0].lstrip("/")
    if not 路径:
        路径 = "index.html"
    候选 = OUT / 路径
    if 路径.endswith("/") or not Path(路径).suffix:
        候选 = OUT / 路径.rstrip("/") / "index.html"
    return 候选


def 主() -> bool:
    问题 = []

    缺失 = [p for p in 关键产物 if not (OUT / p).exists()]
    if 缺失:
        问题.append(f"关键产物缺失 {len(缺失)} 个：{缺失}")

    # 遍历所有 html，检查站内链接
    死链 = []
    html文件 = sorted(OUT.rglob("*.html"))
    链接总数 = 0
    for f in html文件:
        文本 = f.read_text(encoding="utf-8")
        for href in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', 文本):
            目标 = 解析站内链接(href)
            if 目标 is None:
                continue
            链接总数 += 1
            if not 目标.exists():
                死链.append(f"{f.relative_to(OUT).as_posix()} -> {href}")
    if 死链:
        问题.append(f"站内死链 {len(死链)} 条：\n    " + "\n    ".join(死链[:20]))

    # 学习区页数应等于「关卡总数 + 1 个索引」（关卡数由 出/数据/学习清单.json 决定）
    学页数 = len(list((OUT / "学").rglob("index.html"))) if (OUT / "学").exists() else 0
    清单路径 = OUT / "数据" / "学习清单.json"
    if 清单路径.exists():
        清单 = json.loads(清单路径.read_text(encoding="utf-8"))
        期望学页数 = sum(len(v) for v in 清单.values()) + 1
    else:
        期望学页数 = 0
        问题.append("缺 数据/学习清单.json，无法校验学习区页数")
    if 期望学页数 and 学页数 != 期望学页数:
        问题.append(f"学习区页面数 {学页数}，期望 {期望学页数}（关卡 {期望学页数 - 1} + 1 索引）")

    # SEO 门禁（M5）：每页必须有非空 description + canonical，且被 sitemap 收录
    无描述, 无canonical = [], []
    for f in html文件:
        文本 = f.read_text(encoding="utf-8")
        m = re.search(r'<meta name="description" content="([^"]*)"', 文本)
        if not m or not m.group(1).strip():
            无描述.append(f.relative_to(OUT).as_posix())
        if not re.search(r'<link rel="canonical" href="https://[^"]+"', 文本):
            无canonical.append(f.relative_to(OUT).as_posix())
    if 无描述:
        问题.append(f"缺 meta description {len(无描述)} 页：{无描述[:10]}")
    if 无canonical:
        问题.append(f"缺 canonical {len(无canonical)} 页：{无canonical[:10]}")

    sitemap = OUT / "sitemap.xml"
    if sitemap.exists():
        收录 = set(re.findall(r'<loc>https://quye\.com([^<]*)</loc>', sitemap.read_text(encoding="utf-8")))
        if len(收录) != len(html文件):
            问题.append(f"sitemap 收录 {len(收录)} 条，html 页面 {len(html文件)} 个，数量不符")

    print(f"检查 {len(html文件)} 个 html、{链接总数} 条站内链接、学习区 {学页数} 页")
    if 问题:
        for x in 问题:
            print(f"  ! {x}")
        return False
    print("产物自检通过")
    return True


if __name__ == "__main__":
    sys.exit(0 if 主() else 1)
