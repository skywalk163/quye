"""构建产物自检：关键路由存在 + 站内链接无死链（spec §4.4 门禁 #2）。

用法：先 python 建站.py，再 python 工具/产物自检.py
退出码：全部通过 0，有问题 1。
"""
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
    "路线图/index.html",
    "学/段言/hello/index.html",
    "学/光明/09_异常/index.html",
    "数据/学习基线.json",
    "数据/示例集.json",
    "数据/示例结果.json",
    "静态/学.js",
    "静态/台.js",
    "静态/对照.js",
    "静态/执行器.js",
    "静态/讨论区.js",
    "静态/样式.css",
    "静态/py/极快.zip",
    "静态/py/段言.zip",
    "静态/py/光明.zip",
    "静态/py/知行.zip",
    "版本.json",
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

    # 学习区应有 19 关 + 1 索引
    学页数 = len(list((OUT / "学").rglob("index.html"))) if (OUT / "学").exists() else 0
    if 学页数 != 20:
        问题.append(f"学习区页面数 {学页数}，期望 20（19 关 + 1 索引）")

    print(f"检查 {len(html文件)} 个 html、{链接总数} 条站内链接、学习区 {学页数} 页")
    if 问题:
        for x in 问题:
            print(f"  ! {x}")
        return False
    print("产物自检通过")
    return True


if __name__ == "__main__":
    sys.exit(0 if 主() else 1)
