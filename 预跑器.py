"""构建期跑官方示例集，产出示例结果.json。

任一示例挂掉，整个构建失败——这是 spec § 4.4 门禁 #1（示例回归）。
"""
import json
import os
import subprocess
import sys
import tempfile
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
    """在子进程里跑语言的解释器，避免污染当前进程。

    cwd 用临时目录：段言 files 练习之类会真写文件，不能让它污染仓库根。
    """
    if 语言 not in 桥:
        return {"error": f"未知语言 {语言}"}
    code = (
        桥[语言]
        .replace("@@LANG_DIR@@", repr(str(语言目录)))
        .replace("@@SRC@@", repr(源码))
        .replace("@@MARK@@", 标记)
    )
    with tempfile.TemporaryDirectory(prefix="quye_预跑_") as 沙箱:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            cwd=沙箱,
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


# 光明积木预跑的子进程脚本：一个进程跑完整批，逐条 flush 结果到 JSONL。
# 为什么不复用 跑一个()：那是「一块一进程」，上万块起进程的开销以小时计。
# 逐条 flush 的作用是「一条卡死不牵连全批」——外层超时杀掉进程后，已写下的结果照样算。
光明积木预跑脚本 = """
import sys, io, json
sys.path.insert(0, @@LANG_DIR@@)
from light_parser_v3 import LightParser
from code_generator import PythonCodeGenerator

任务 = json.load(open(@@任务文件@@, encoding='utf-8'))
出 = open(@@结果文件@@, 'w', encoding='utf-8')
真stdout = sys.stdout
for 条 in 任务:
    缓冲 = io.StringIO()
    可运行, 输出 = False, ''
    try:
        _ast = LightParser().parse(条['示例'])
        _py = PythonCodeGenerator().generate(_ast)
        sys.stdout = 缓冲
        exec(_py, {'__name__': '__main__'})
        sys.stdout = 真stdout
        输出 = 缓冲.getvalue()
        可运行 = bool(输出.strip())
    except KeyboardInterrupt:
        raise
    except BaseException:
        # 生成器产出的积木有相当比例踩到解释器未覆盖的语法（如三元 如果…则…否则）
        # 或引用了未定义名字，跑挂是常态，不是构建错误
        sys.stdout = 真stdout
    出.write(json.dumps(
        {'名称': 条['名称'], '可运行': 可运行, 'stdout': 输出[:500]},
        ensure_ascii=False) + '\\n')
    出.flush()
出.close()
"""


def 预跑光明积木(块列表: list, 语言目录: Path, 超时秒: int = 900) -> None:
    """就地把 块列表 里光明积木的「可运行」标跑出来。

    光明积木本身只定义一个段落，直接跑没有输出，所以 建站._光明块表() 已按契约
    合成了 `打印(段落名(样例入参))` 追加在源码后面。这里用光明解释器实跑那份合成
    示例：跑出非空输出才置 可运行=True，页面据此决定是否给「在浏览器里跑」按钮。

    跑挂/超时都不失败构建——积木库是自动生成的，可运行率本身就是一项观测指标，
    不是门禁。只在一条都没跑通时告警（那通常意味着解释器抽取坏了）。
    """
    待跑 = [b for b in 块列表 if b["语言"] == "光明" and b.get("示例")]
    if not 待跑:
        return
    结果 = {}
    with tempfile.TemporaryDirectory(prefix="quye_积木预跑_") as 沙箱:
        任务文件 = Path(沙箱) / "任务.json"
        结果文件 = Path(沙箱) / "结果.jsonl"
        任务文件.write_text(
            json.dumps([{"名称": b["名称"], "示例": b["示例"]} for b in 待跑],
                       ensure_ascii=False),
            encoding="utf-8",
        )
        code = (
            光明积木预跑脚本
            .replace("@@LANG_DIR@@", repr(str(语言目录)))
            .replace("@@任务文件@@", repr(str(任务文件)))
            .replace("@@结果文件@@", repr(str(结果文件)))
        )
        超时了 = False
        try:
            subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=超时秒,
                encoding="utf-8", errors="replace",
                cwd=沙箱,  # 文件/系统类积木可能真写盘，别污染仓库
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
        except subprocess.TimeoutExpired:
            超时了 = True
        if 结果文件.exists():
            for 行 in 结果文件.read_text(encoding="utf-8").splitlines():
                if not 行.strip():
                    continue
                r = json.loads(行)
                结果[r["名称"]] = r
    for b in 待跑:
        r = 结果.get(b["名称"])
        if r and r["可运行"]:
            b["可运行"] = True
    跑通 = sum(1 for b in 待跑 if b["可运行"])
    尾注 = f"（超时 {超时秒}s 截断，已判定 {len(结果)}/{len(待跑)}）" if 超时了 else ""
    if not 跑通:
        print(f"    ! 光明积木预跑 0 通过{尾注}——检查光明解释器抽取是否正常")
    else:
        print(f"    光明积木预跑：{跑通}/{len(待跑)} 可跑{尾注}")


def 预跑学习基线(数据目录: Path, py根: Path) -> None:
    """跑每关参考答案，抓 stdout 作判对基线。

    部分关卡（如段言 files 的真实文件 IO）在子进程可跑但浏览器 Pyodide 未必支持，
    这类关卡标 在线可判=False，页面只读展示、不提供在线判对。
    可判关卡低于阈值则构建失败（M3 定的 19 关是不可退让的底线，M5 扩关只能加不能减）。
    """
    可判阈值 = 19
    清单 = json.loads((ROOT / "数据" / "学习清单.json").read_text(encoding="utf-8"))
    素材根 = 数据目录 / "学习素材"
    语言表 = list(清单.keys())
    基线 = {语言: [] for 语言 in 语言表}
    失败 = []
    for 语言 in 语言表:
        for 条 in 清单[语言]:
            关卡 = 条["关卡"]
            源码 = (素材根 / 语言 / 关卡 / "参考答案.txt").read_text(encoding="utf-8")
            r = 跑一个(语言, 源码, py根 / 语言)
            if "error" in r:
                失败.append(f"学习 {语言} · {关卡}: {r['error'][:300]}")
                基线[语言].append({**条, "预期stdout": "", "在线可判": False})
                continue
            基线[语言].append({**条, "预期stdout": r["stdout"], "在线可判": True})
    总关数 = sum(len(清单[语言]) for 语言 in 语言表)
    可判数 = sum(1 for 语言 in 基线 for x in 基线[语言] if x["在线可判"])
    if 可判数 < 可判阈值:
        for 条 in 失败:
            print(f"  ! 学习基线失败: {条}")
        raise RuntimeError(f"学习基线可判关卡仅 {可判数}，低于阈值 {可判阈值}")
    for 条 in 失败:
        print(f"  ! 学习关卡不可在线判（只读展示）: {条}")
    (数据目录 / "学习基线.json").write_text(
        json.dumps(基线, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  学习基线：可在线判 {可判数} / {总关数} 关")


if __name__ == "__main__":
    预跑(ROOT / "出" / "数据", ROOT / "出" / "静态" / "py")
