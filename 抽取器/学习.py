"""抽取学习素材：段言 tutorial exercises + 光明 L1_baihua + 极快 examples + 知行 examples。

产物落到 出/数据/学习素材/<语言>/<关卡>/：
- 题干.md      （段言有原始 md；其他语言用源码首部注释）
- 参考答案.txt  （段言取 <关卡>_solution.duan；其他取源码本身）
- 骨架.txt      （段言有 <关卡>.duan 起始骨架；其他无，留空）

关卡元数据来自 数据/学习清单.json（由 建站.py 读入后传入）。
"""
import shutil
from pathlib import Path


def 抽取(段言根: Path, 光明根: Path, 素材目标: Path, 清单: dict,
       极快根: Path = None, 知行根: Path = None) -> None:
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
        (目标 / "题干.md").write_text(_取首部注释(源, ("#",)), encoding="utf-8")

    # 极快：examples/*.jk（清单里带「源」相对路径；题干取源码首部注释 -- 或 //）
    if 极快根 is not None and "极快" in 清单:
        for 条 in 清单["极快"]:
            关卡 = 条["关卡"]
            目标 = 素材目标 / "极快" / 关卡
            目标.mkdir(parents=True, exist_ok=True)
            源 = 极快根 / 条["源"]
            if not 源.exists():
                raise FileNotFoundError(f"极快示例缺失：{源}")
            _写(目标 / "参考答案.txt", 源)
            (目标 / "题干.md").write_text(_取首部注释(源, ("--", "//", "#")), encoding="utf-8")

    # 知行：examples/NN_*.yan（同光明形态；题干取源码首部 # 注释）
    if 知行根 is not None and "知行" in 清单:
        for 条 in 清单["知行"]:
            关卡 = 条["关卡"]
            目标 = 素材目标 / "知行" / 关卡
            目标.mkdir(parents=True, exist_ok=True)
            源 = 知行根 / 条["源"]
            if not 源.exists():
                raise FileNotFoundError(f"知行示例缺失：{源}")
            _写(目标 / "参考答案.txt", 源)
            (目标 / "题干.md").write_text(_取首部注释(源, ("#",)), encoding="utf-8")


def _取首部注释(源: Path, 前缀: tuple) -> str:
    """收源码开头连续的注释行，中间空行保留；遇首个非注释非空即停。若无注释则回退用文件名。"""
    题干行 = []
    for line in 源.read_text(encoding="utf-8").splitlines():
        s = line.rstrip()
        if any(s.startswith(p) for p in 前缀):
            for p in 前缀:
                if s.startswith(p):
                    题干行.append(s[len(p):].strip())
                    break
        elif s.strip() == "":
            continue
        else:
            break
    return "\n\n".join(题干行) if 题干行 else f"# {源.stem}\n\n跟着参考答案写一遍。"


def _写(目标: Path, 源: Path) -> None:
    if 源.exists():
        shutil.copy2(源, 目标)
    else:
        目标.write_text("", encoding="utf-8")
