"""从极快仓库抽取核心链路。

来源：src/jikuai/ + stdlib/ + tools/ai-bridge/glue.py + --check/索引.json
替换：pkg/sources.py（原文件走 git subprocess，浏览器不可用）

关于布局：jikuai 包落在 <目标>/jikuai/，stdlib 落在 <目标>/stdlib/。
`module_loader._search_paths` 用 `__file__ + '../../stdlib'` 定位标准库
（即 <目标>/stdlib），这个假设在本布局下成立，块生态 `blocks.财务.个税`
可以正常解析。但 `ai/retrieval.py` 用的是上 3 级（假设自己在
<repo>/src/jikuai/ai/），在本布局下会走出包根——那一处由
静态/执行器.js 的 准备语言() 热补丁兜住。
"""
import shutil
from pathlib import Path

# pkg/sources.py 的浏览器替身：保留 __all__ 全部公开签名，import 阶段绝不失败，
# 只有真正调用抓取逻辑时才抛错。原文件依赖 git subprocess + 网络。
# 下游 import 者：pkg/__init__.py(SourceError)、pkg/resolver.py(全部 4 个)、
# pkg/installer.py(FetchedSource, compute_checksum)、pkg/registry.py(compute_checksum)。
SOURCES_替身 = '''"""浏览器替身：原 sources.py 走 git subprocess + 网络，在 Pyodide 中不可用。

保留 __all__ 的全部公开签名，让 pkg.resolver / pkg.installer / pkg.registry
的模块级 import 正常通过；真正触发包抓取时才抛 RuntimeError。
"""
import os
from typing import Tuple

__all__ = [
    'SourceError', 'FetchedSource',
    'resolve_source', 'compute_checksum',
]

_不可用 = "包管理器在浏览器（Pyodide）中不可用：原实现依赖 git subprocess 与网络"


class SourceError(Exception):
    """来源抓取失败：路径不存在、git 出错、来源类型不支持等。"""


class FetchedSource:
    """一次抓取的结果：包源码根目录 + 清单 + 若干坐标信息。"""

    __slots__ = ('root', 'manifest', 'kind', 'origin', 'ephemeral')

    def __init__(self, root, manifest, kind, origin, ephemeral):
        self.root = os.path.abspath(root)
        self.manifest = manifest
        self.kind = kind
        self.origin = origin
        self.ephemeral = ephemeral


def resolve_source(dep, base_dir):
    raise SourceError(_不可用)


def compute_checksum(directory: str) -> Tuple[str, int]:
    raise RuntimeError(_不可用)
'''


def 抽取(仓库根: Path, 目标: Path) -> None:
    目标.mkdir(parents=True, exist_ok=True)

    # 核心 Python 包
    src = 仓库根 / "src" / "jikuai"
    if not src.exists():
        raise FileNotFoundError(f"极快源码目录不存在：{src}")
    shutil.copytree(src, 目标 / "jikuai", dirs_exist_ok=True)

    # 加固 retrieval 索引定位（建议书 §4.1）：
    # 上游 vector_index_path/_load_blocks 用 `__file__` 上 3 级找 stdlib（假设自己在
    # <repo>/src/jikuai/ai/），本布局 <目标>/jikuai/ai/ 上 3 级会走出包根、静默返回 []。
    # 抽取期把「上 3 级」改成「上 2 级」——布局正好指向 <目标>/stdlib。两处（向量索引
    # 与块索引）用同一串，replace 全替。
    #
    # 第二处补丁（给静默 return [] 加 warning）：上游 2026-08 起已自行改成
    # `_log.warning(...)`，命中即视为「上游已落地」直接跳过，不再注入。
    # 两处补丁都不硬失败——上游漂移由 工具/命中率实测.py 兜住（命中率骤降 →
    # CI 软门禁告警 + 上游漂移 workflow 开 issue），构建本身不该因一个字符串失配而红。
    retr = 目标 / "jikuai" / "ai" / "retrieval.py"
    if retr.exists():
        s = retr.read_text(encoding="utf-8")
        原文 = s

        旧路径 = "os.path.normpath(os.path.join(here, '..', '..', '..'))"
        新路径 = "os.path.normpath(os.path.join(here, '..', '..'))"
        if 旧路径 in s:
            s = s.replace(旧路径, 新路径)
        elif 新路径 in s:
            print("    · 极快 retrieval 路径已是上 2 级（上游已适配），跳过路径补丁")
        else:
            print(
                "    ! 极快 retrieval 索引路径写法与预期不符（上游可能重构），"
                "跳过路径补丁——请看命中率实测结果确认检索是否仍可用"
            )

        旧静默 = "    if not os.path.isfile(idx_path):\n        return []"
        新静默 = (
            "    if not os.path.isfile(idx_path):\n"
            "        import warnings as _w\n"
            "        _w.warn(f'retrieval: 未定位到索引 {idx_path}，检索将返回空')\n"
            "        return []"
        )
        if 旧静默 in s:
            s = s.replace(旧静默, 新静默)
        elif "_log.warning" in s and "idx_path" in s:
            print("    · 极快 retrieval 索引缺失已由上游自行告警，跳过 warning 注入")
        else:
            print("    ! 极快 retrieval 索引缺失分支与预期不符，跳过 warning 注入")

        if s != 原文:
            retr.write_text(s, encoding="utf-8")

    # 用保留签名的替身换掉走 git subprocess 的 sources.py
    坑 = 目标 / "jikuai" / "pkg" / "sources.py"
    if 坑.exists():
        坑.write_text(SOURCES_替身, encoding="utf-8")

    # stdlib（含 blocks/ 块生态与 索引.json / 向量索引.bin）
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
