"""块示例自检：把 112 个块的官方示例逐个跑一遍。

/块 页面对每个块都提供「在浏览器里跑」按钮，但此前没有任何门禁验证这些示例
真的跑得通——历法/属相/节气类块因 stdlib 路径错了一级，在浏览器里全是
FileNotFoundError，而构建、产物自检、命中率实测三关都没发现。这个工具补上那块盲区。

跑的是 出/静态/py/极快 布局（与浏览器 Pyodide 里的目录结构一致），
所以这里的通过率就是用户在 /块 页上点「跑」的通过率。

用法：先 python 建站.py，再 python 工具/块示例自检.py
退出码：通过率 >= 阈值 返回 0，否则 1。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import 预跑器  # noqa: E402

OUT = ROOT / "出"
极快根 = OUT / "静态" / "py" / "极快"
BLOCKS = 极快根 / "stdlib" / "blocks"

# 通过率阈值。示例本身是上游写的，个别块可能依赖浏览器缺的能力（文件/网络），
# 所以不要求 100%；低于这个线说明布局或上游出了系统性问题。
阈值 = 0.9


def 主() -> float:
    if not BLOCKS.exists():
        print(f"[块示例自检] 块目录不存在：{BLOCKS}（先跑 建站.py）")
        return 0.0

    条目 = []
    for 块json in sorted(BLOCKS.rglob("块.json")):
        d = json.loads(块json.read_text(encoding="utf-8"))
        示例 = (d.get("示例") or "").strip()
        if 示例:
            条目.append((d.get("名称", 块json.parent.name),
                        (d.get("领域") or ["?"])[0], 示例))

    if not 条目:
        print("[块示例自检] 没有带示例的块，跳过")
        return 1.0

    失败 = []
    for 名, 领域, 示例 in 条目:
        r = 预跑器.跑一个("极快", 示例, 极快根)
        if "error" in r:
            末行 = r["error"].strip().splitlines()[-1][:120]
            失败.append((名, 领域, 末行))

    通过 = len(条目) - len(失败)
    率 = 通过 / len(条目)
    print(f"块示例自检：{通过}/{len(条目)} 通过 = {率:.0%}（阈值 {阈值:.0%}）")
    if 失败:
        print("失败明细（块 / 领域 / 末行错误）：")
        for 名, 领域, 错 in 失败:
            print(f"  - {名} / {领域} / {错}")
    return 率


if __name__ == "__main__":
    sys.exit(0 if 主() >= 阈值 else 1)
