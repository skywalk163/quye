"""从段言仓库抽取核心解释链路。

采用黑名单模式：copy src/ 下所有 .py，跳过：
- 顶层 import threading 的：compiler.py、file_watcher.py、incremental_build.py
- 顶层 import subprocess/socket 的：llvm_dependency.py、package_installer.py、package_manager.py
- LLVM 后端：llvm/ 目录、codegen_x64.py
- 服务器：registry_server.py

保留 core/、optimizer/、repl/ 子包（如果不带会导致核心链路 import 失败）——但 repl 可能引 prompt-toolkit，故也剔除。
"""
import shutil
from pathlib import Path

跳过文件 = {
    "compiler.py",
    "file_watcher.py",
    "incremental_build.py",
    "llvm_dependency.py",
    "package_installer.py",
    "package_manager.py",
    "package_security.py",
    "registry_server.py",
    "codegen_x64.py",
}
跳过目录 = {"llvm", "repl", "__pycache__"}


def 抽取(仓库根: Path, 目标: Path) -> None:
    目标.mkdir(parents=True, exist_ok=True)
    src = 仓库根 / "src"
    if not src.exists():
        raise FileNotFoundError(f"段言源码目录不存在：{src}")
    抽出 = 0
    for p in src.rglob("*.py"):
        # 跳过任何位于跳过目录下的文件
        if any(部分 in 跳过目录 for 部分 in p.relative_to(src).parts):
            continue
        if p.name in 跳过文件:
            continue
        rel = p.relative_to(src)
        目标文件 = 目标 / rel
        目标文件.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, 目标文件)
        抽出 += 1
    if 抽出 < 10:
        raise RuntimeError(f"段言抽取失败：只抽到 {抽出} 个 .py，可能路径结构变更")

    # 积木库（工作台选块运行期依赖）：
    # - 选块.py：Pyodide 内 import，本地关键词打分
    # - 索引.json：200 个块的契约
    # - 粘合.py：synthesize(方案) 合成 .duan 源码
    # - 分领域 .duan 源码：粘合器要内联段落定义
    积木库源 = 仓库根 / "积木库"
    if 积木库源.exists():
        积木库目标 = 目标 / "积木库"
        积木库目标.mkdir(exist_ok=True)
        for 名 in ("索引.json", "选块.py", "粘合.py"):
            src = 积木库源 / 名
            if src.exists():
                shutil.copy2(src, 积木库目标 / 名)
        # 分领域子目录里的 .duan 文件（粘合器 _提取段落 要用）
        块数 = 0
        for p in 积木库源.rglob("*.duan"):
            相对 = p.relative_to(积木库源)
            目标文件 = 积木库目标 / 相对
            目标文件.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, 目标文件)
            块数 += 1
        print(f"    · 段言积木库：索引/选块/粘合 + {块数} 个 .duan")
    else:
        print("    ! 段言积木库目录不存在，跳过")
