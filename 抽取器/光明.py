"""从光明仓库抽取核心解释链路。

采用黑名单模式：copy src/ 下所有 .py，跳过：
- llvm/ 目录（LLVM 后端）
- 顶层 import subprocess 的：package_installer.py、package_manager.py、lightpub.py、ffi_rust.py、ffi_go.py
- threading：file_watcher.py

stdlib 裁减：网络.py、进程.py、线程.py
"""
import shutil
from pathlib import Path

跳过文件 = {
    "package_installer.py",
    "package_manager.py",
    "lightpub.py",
    "ffi_rust.py",
    "ffi_go.py",
    "file_watcher.py",
}
跳过目录 = {"llvm", "__pycache__"}
stdlib跳过 = {"网络.py", "进程.py", "线程.py"}


def 抽取(仓库根: Path, 目标: Path) -> None:
    目标.mkdir(parents=True, exist_ok=True)
    src = 仓库根 / "src"
    if not src.exists():
        raise FileNotFoundError(f"光明源码目录不存在：{src}")
    抽出 = 0
    for p in src.rglob("*.py"):
        if any(部分 in 跳过目录 for 部分 in p.relative_to(src).parts):
            continue
        if p.name in 跳过文件:
            continue
        rel = p.relative_to(src)
        目标文件 = 目标 / rel
        目标文件.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, 目标文件)
        抽出 += 1
    if 抽出 < 5:
        raise RuntimeError(f"光明抽取失败：只抽到 {抽出} 个 .py")

    # 光明 stdlib（裁减）
    stdlib源 = 仓库根 / "stdlib"
    if stdlib源.exists():
        stdlib目标 = 目标 / "stdlib"
        stdlib目标.mkdir(exist_ok=True)
        for p in stdlib源.iterdir():
            if p.is_file() and p.name not in stdlib跳过:
                shutil.copy2(p, stdlib目标 / p.name)
