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
