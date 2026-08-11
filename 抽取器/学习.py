"""抽取学习素材：段言 tutorial exercises + 光明 L1_baihua。

产物落到 出/数据/学习素材/<语言>/<关卡>/：
- 题干.md      （段言有原始 md；光明用源码首部注释）
- 参考答案.txt  （段言取 <关卡>_solution.duan；光明取 <关卡>.light 源码本身）
- 骨架.txt      （段言有 <关卡>.duan 起始骨架；光明无，留空）

关卡元数据来自 数据/学习清单.json（由 建站.py 读入后传入）。
"""
import shutil
from pathlib import Path


def 抽取(段言根: Path, 光明根: Path, 素材目标: Path, 清单: dict) -> None:
    素材目标.mkdir(parents=True, exist_ok=True)

    # 段言：exercises 三件套
    段言练习 = 段言根 / "tools" / "tutorial" / "exercises"
    for 条 in 清单["段言"]:
        关卡 = 条["关卡"]
        目标 = 素材目标 / "段言" / 关卡
        目标.mkdir(parents=True, exist_ok=True)
        题干 = 段言练习 / f"{关卡}.md"
        答案 = 段言练习 / f"{关卡}_solution.duan"
        骨架 = 段言练习 / f"{关卡}.duan"
        if not 答案.exists():
            raise FileNotFoundError(f"段言参考答案缺失：{答案}")
        _写(目标 / "题干.md", 题干)
        _写(目标 / "参考答案.txt", 答案)
        _写(目标 / "骨架.txt", 骨架)

    # 光明：L1_baihua/<关卡>.light（源码即参考答案；题干取源码首部注释）
    光明课 = 光明根 / "examples" / "L1_baihua"
    for 条 in 清单["光明"]:
        关卡 = 条["关卡"]
        目标 = 素材目标 / "光明" / 关卡
        目标.mkdir(parents=True, exist_ok=True)
        源 = 光明课 / f"{关卡}.light"
        if not 源.exists():
            raise FileNotFoundError(f"光明课程缺失：{源}")
        _写(目标 / "参考答案.txt", 源)
        # 题干：取源码开头连续的 # 注释行（跳过空行也保留在中间），遇到第一行非注释非空即停
        题干行 = []
        for line in 源.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                题干行.append(line.lstrip("# ").rstrip())
            elif line.strip() == "":
                continue
            else:
                break
        (目标 / "题干.md").write_text("\n\n".join(题干行), encoding="utf-8")


def _写(目标: Path, 源: Path) -> None:
    if 源.exists():
        shutil.copy2(源, 目标)
    else:
        目标.write_text("", encoding="utf-8")
