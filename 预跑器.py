"""构建期跑官方示例集，产出示例结果.json。

任一示例挂掉，整个构建失败——这是 spec § 4.4 门禁 #1（示例回归）。
"""
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

标记 = "__STDOUT__"

# 每门语言的桥：@@LANG_DIR@@ / @@SRC@@ 两个占位符用 repr 后的字面量替换，
# 避免 str.format 在含大括号的 Python 代码里反复转义。
桥 = {
    "极快": """
import sys, io
sys.path.insert(0, @@LANG_DIR@@)
from jikuai.main import run_source
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    run_source(@@SRC@@)
finally:
    sys.stdout = _old
sys.stdout.write("@@MARK@@" + _buf.getvalue())
""",
    "段言": """
import sys, io
sys.path.insert(0, @@LANG_DIR@@)
from duan_parser_v3 import DuanParser
from code_generator import PythonCodeGenerator
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _mod = DuanParser().parse(@@SRC@@)
    _py = PythonCodeGenerator().generate(_mod)
    exec(_py, {'__name__': '__main__'})
finally:
    sys.stdout = _old
sys.stdout.write("@@MARK@@" + _buf.getvalue())
""",
    "光明": """
import sys, io
sys.path.insert(0, @@LANG_DIR@@)
from light_parser_v3 import LightParser
from code_generator import PythonCodeGenerator
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _ast = LightParser().parse(@@SRC@@)
    _py = PythonCodeGenerator().generate(_ast)
    exec(_py, {'__name__': '__main__'})
finally:
    sys.stdout = _old
sys.stdout.write("@@MARK@@" + _buf.getvalue())
""",
    "知行": """
import sys, io
sys.path.insert(0, @@LANG_DIR@@)
from zhixing.compiler.parser import parse
from zhixing.runtime.evaluator import evaluate
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    evaluate(parse(@@SRC@@))
finally:
    sys.stdout = _old
sys.stdout.write("@@MARK@@" + _buf.getvalue())
""",
}


def 跑一个(语言: str, 源码: str, 语言目录: Path) -> dict:
    """在子进程里跑语言的解释器，避免污染当前进程。"""
    if 语言 not in 桥:
        return {"error": f"未知语言 {语言}"}
    code = (
        桥[语言]
        .replace("@@LANG_DIR@@", repr(str(语言目录)))
        .replace("@@SRC@@", repr(源码))
        .replace("@@MARK@@", 标记)
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    if r.returncode != 0:
        return {"error": (r.stderr or "")[:500]}
    idx = (r.stdout or "").find(标记)
    if idx < 0:
        return {"error": "子进程未产出标记，stdout 被意外截断"}
    return {"stdout": r.stdout[idx + len(标记):]}


def 预跑(数据目录: Path, py根: Path) -> None:
    集 = json.loads((数据目录 / "示例集.json").read_text(encoding="utf-8"))
    结果 = {"工作台官方示例": []}
    失败 = []
    for 条 in 集["工作台官方示例"]:
        r = 跑一个(条["语言"], 条["源码"], py根 / 条["语言"])
        if "error" in r:
            失败.append(f"{条['语言']} · {条['标题']}: {r['error'][:200]}")
            continue
        结果["工作台官方示例"].append({**条, "stdout": r["stdout"]})
    # 对照示例同样纳入门禁：四门语言的同一需求必须都跑得通
    for 条 in 集["对照示例"]:
        for 语言 in ("极快", "段言", "光明", "知行"):
            源码 = 条.get(语言)
            if not 源码:
                continue
            r = 跑一个(语言, 源码, py根 / 语言)
            if "error" in r:
                失败.append(f"对照 {语言} · {条['标题']}: {r['error'][:200]}")
    if 失败:
        for 条 in 失败:
            print(f"  ! 预跑失败: {条}")
        raise RuntimeError(f"预跑器失败 {len(失败)} 个示例")
    (数据目录 / "示例结果.json").write_text(
        json.dumps(结果, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  预跑通过 {len(结果['工作台官方示例'])} 个工作台示例 + {len(集['对照示例'])} 组对照示例")


if __name__ == "__main__":
    预跑(ROOT / "出" / "数据", ROOT / "出" / "静态" / "py")
