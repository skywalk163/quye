"""按 数据/文档清单.json 抽各仓库精选 markdown 到 出/数据/文档/<slug>.md。

源文件缺失即报错——宁可构建失败，也不产出指向死链的文档索引（spec §4.4 门禁 #2）。
"""
import shutil
from pathlib import Path


def 抽取(仓库根映射: dict, 目标: Path, 清单: dict) -> list:
    """仓库根映射: {语言: 仓库根 Path}。返回成功抽取的条目列表（供构建索引）。"""
    目标.mkdir(parents=True, exist_ok=True)
    成功 = []
    缺失 = []
    for 条 in 清单["文档"]:
        根 = 仓库根映射[条["语言"]]
        源 = 根 / 条["源路径"]
        if not 源.exists():
            缺失.append(f'{条["语言"]}:{条["源路径"]}')
            continue
        shutil.copy2(源, 目标 / f'{条["slug"]}.md')
        成功.append(条)
    if 缺失:
        raise FileNotFoundError(
            "文档源缺失（清单需更新或上游改名）：" + "; ".join(缺失)
        )
    return 成功
