"""从极快仓库抽取核心链路。

来源：src/jikuai/ + stdlib/ + tools/ai-bridge/glue.py + --check/索引.json
去除：pkg/sources.py（git subprocess）
"""
import shutil
from pathlib import Path


def 抽取(仓库根: Path, 目标: Path) -> None:
    目标.mkdir(parents=True, exist_ok=True)

    # 核心 Python 包
    src = 仓库根 / "src" / "jikuai"
    if not src.exists():
        raise FileNotFoundError(f"极快源码目录不存在：{src}")
    shutil.copytree(src, 目标 / "jikuai", dirs_exist_ok=True)

    # 移除浏览器碰不到的模块
    坑 = 目标 / "jikuai" / "pkg" / "sources.py"
    if 坑.exists():
        # 用空实现替换，避免 evaluator 里的可选 import 报错
        坑.write_text(
            '"""在浏览器环境中被替换为空 stub。原文件走 git subprocess。"""\n'
            'def _unavailable(*a, **kw):\n'
            '    raise RuntimeError("包管理器在浏览器中不可用")\n',
            encoding="utf-8"
        )

    # stdlib
    stdlib源 = 仓库根 / "stdlib"
    if stdlib源.exists():
        shutil.copytree(stdlib源, 目标 / "stdlib", dirs_exist_ok=True)

    # AI 桥的 glue 模块
    glue = 仓库根 / "tools" / "ai-bridge" / "glue.py"
    if glue.exists():
        shutil.copy2(glue, 目标 / "glue.py")

    # 索引文件
    索引 = 仓库根 / "--check" / "索引.json"
    if 索引.exists():
        shutil.copy2(索引, 目标.parent.parent.parent / "数据" / "极快索引.json")
