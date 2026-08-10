// Web Worker：Pyodide 执行沙箱
// 消息协议：
//   主线程 → Worker: {类型:"跑", 语言, 源码, 会话id}
//   Worker → 主线程: {类型:"结果"|"错误"|"进度", 会话id, ...}

self.PYODIDE_VERSION = "0.26.4";
const 自托管 = "/静态/pyodide/";
const CDN = `https://cdn.jsdelivr.net/pyodide/v${self.PYODIDE_VERSION}/full/`;

let _py = null;
let _语言就绪 = new Set();

async function 初始化Pyodide() {
  if (_py) return _py;
  postMessage({ 类型: "进度", 消息: "加载 Pyodide runtime..." });
  const 试 = async (base) => {
    self.importScripts(base + "pyodide.js");
    return await self.loadPyodide({ indexURL: base });
  };
  try {
    _py = await 试(new URL(自托管, self.location.href).href);
  } catch (e1) {
    postMessage({ 类型: "进度", 消息: `自托管失败，回退 CDN: ${e1.message}` });
    _py = await 试(CDN);
  }
  return _py;
}

async function 准备语言(语言) {
  if (_语言就绪.has(语言)) return;
  const py = await 初始化Pyodide();
  postMessage({ 类型: "进度", 消息: `加载 ${语言} 包...` });

  // 从 /静态/py/<语言>/ 抓取 py 文件并挂到 Pyodide FS
  const 根 = `/静态/py/${encodeURIComponent(语言)}/`;
  const 清单 = await (await fetch(`${根}清单.json`)).json();
  for (const 相对路径 of 清单.文件) {
    const url = `${根}${相对路径}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`加载失败：${url}`);
    const 内容 = await resp.text();
    const py路径 = `/${语言}/${相对路径}`;
    const 目录 = py路径.split('/').slice(0, -1).join('/');
    py.FS.mkdirTree(目录);
    py.FS.writeFile(py路径, 内容, { encoding: "utf8" });
  }
  py.runPython(`
import sys
if '/${语言}' not in sys.path:
    sys.path.insert(0, '/${语言}')
`);
  _语言就绪.add(语言);
}

// 每门语言的调用桥：翻译成 Python 代码，最后一行为 json.dumps 表达式（runPython 直接返回）
const 桥 = {
  极快: (src) => `
import io, sys, json
from jikuai.main import run_source
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _ret = run_source(${JSON.stringify(src)})
finally:
    sys.stdout = _old
json.dumps({"stdout": _buf.getvalue(), "返回值": repr(_ret) if _ret is not None else None}, ensure_ascii=False)
`,
  段言: (src) => `
import io, sys, json
from duan_parser_v3 import DuanParser
from code_generator import PythonCodeGenerator
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _mod = DuanParser().parse(${JSON.stringify(src)})
    _py = PythonCodeGenerator().generate(_mod)
    _ns = {'__name__': '__main__'}
    exec(_py, _ns)
finally:
    sys.stdout = _old
json.dumps({"stdout": _buf.getvalue(), "返回值": None}, ensure_ascii=False)
`,
  光明: (src) => `
import io, sys, json
from light_parser_v3 import LightParser
from code_generator import PythonCodeGenerator
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _ast = LightParser().parse(${JSON.stringify(src)})
    _py = PythonCodeGenerator().generate(_ast)
    exec(_py, {'__name__': '__main__'})
finally:
    sys.stdout = _old
json.dumps({"stdout": _buf.getvalue(), "返回值": None}, ensure_ascii=False)
`,
  知行: (src) => `
import io, sys, json
from zhixing.compiler.parser import parse
from zhixing.runtime.evaluator import evaluate
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    _ret = evaluate(parse(${JSON.stringify(src)}))
finally:
    sys.stdout = _old
json.dumps({"stdout": _buf.getvalue(), "返回值": repr(_ret) if _ret is not None else None}, ensure_ascii=False)
`,
};

self.addEventListener("message", async (e) => {
  const { 类型, 语言, 源码, 会话id } = e.data;
  if (类型 !== "跑") return;
  try {
    await 准备语言(语言);
    const py = _py;
    const 代码 = 桥[语言];
    if (!代码) throw new Error(`未知语言：${语言}`);
    const 原始 = py.runPython(代码(源码));
    let 结果;
    try { 结果 = JSON.parse(原始); } catch { 结果 = { stdout: String(原始), 返回值: null }; }
    postMessage({ 类型: "结果", 会话id, ...结果 });
  } catch (err) {
    postMessage({ 类型: "错误", 会话id, 消息: String(err.message || err) });
  }
});
