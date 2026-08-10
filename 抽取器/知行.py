"""从知行仓库抽取核心求值链路。

来源：src/zhixing/compiler/*、runtime/*、stdlib/*
排除：pkg_manager.py（subprocess）
补丁 stdlib/loader.py：从 DEFAULT_LIBS 精确删除 c_lib/net_lib/db_lib 三行
（浏览器 Pyodide 里 ctypes/urllib/sqlite3 不可用）
"""
import shutil
from pathlib import Path

跳过 = {"c_lib.py", "net_lib.py", "db_lib.py", "pkg_manager.py"}
跳过目录 = {"__pycache__"}


def 抽取(仓库根: Path, 目标: Path) -> None:
    目标.mkdir(parents=True, exist_ok=True)
    src = 仓库根 / "src" / "zhixing"
    if not src.exists():
        raise FileNotFoundError(f"知行源码目录不存在：{src}")

    抽出 = 0
    for p in src.rglob("*.py"):
        if any(部分 in 跳过目录 for 部分 in p.relative_to(src).parts):
            continue
        if p.name in 跳过:
            continue
        rel = p.relative_to(src)
        目标文件 = 目标 / rel
        目标文件.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, 目标文件)
        抽出 += 1
    if 抽出 < 5:
        raise RuntimeError(f"知行抽取失败：只抽到 {抽出} 个 .py")

    # loader.py 补丁：精确删除 DEFAULT_LIBS 里的三个模块行
    loader = 目标 / "stdlib" / "loader.py"
    if loader.exists():
        文本 = loader.read_text(encoding="utf-8")
        if "# quye-patched" in 文本:
            return  # 已打过补丁
        原长 = len(文本)
        for mod in ("c_lib", "net_lib", "db_lib"):
            # 覆盖 4/8/12 缩进 + 单/双引号 + 可选空格 + 逗号 + CR/LF
            候选 = [
                f"    'zhixing.stdlib.{mod}',\n",
                f'    "zhixing.stdlib.{mod}",\n',
                f"    'zhixing.stdlib.{mod}',\r\n",
                f'    "zhixing.stdlib.{mod}",\r\n',
                f"        'zhixing.stdlib.{mod}',\n",
                f'        "zhixing.stdlib.{mod}",\n',
            ]
            for c in 候选:
                文本 = 文本.replace(c, "")
        if len(文本) == 原长:
            raise RuntimeError(
                "知行 loader.py 补丁未生效：DEFAULT_LIBS 结构可能已变更，"
                "请查 stdlib/loader.py 确认 c_lib/net_lib/db_lib 三行的形态"
            )
        文本 = 文本.rstrip() + "\n\n# quye-patched: 已从 DEFAULT_LIBS 移除浏览器不可用的三项\n"
        loader.write_text(文本, encoding="utf-8")
