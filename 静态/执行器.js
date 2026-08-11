// Web Worker：Pyodide 执行沙箱
// 消息协议：
//   主线程 → Worker: {类型:"跑", 语言, 源码, 会话id}
//                    {类型:"跑Python", 依赖语言, 源码, 会话id}  // 直跑 Python，绕开语言桥
//   Worker → 主线程: {类型:"进度", 消息}                      // 加载阶段的状态文本
//                    {类型:"开始执行", 会话id}                 // 准备完毕，主线程此时才起 5 秒表
//                    {类型:"结果"|"错误", 会话id, ...}

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

  // 从 /静态/py/<语言>.zip 一次拉取 → Pyodide unpack_archive 解包到 /<语言>
  // （M2 遗留：逐文件 fetch 极快 394 个太慢）；zip 拉取失败时回退逐文件清单
  const zip地址 = `/静态/py/${encodeURIComponent(语言)}.zip`;
  const 目标根 = `/${语言}`;
  py.FS.mkdirTree(目标根);
  let 用zip = false;
  try {
    const resp = await fetch(zip地址);
    if (resp.ok) {
      const buf = new Uint8Array(await resp.arrayBuffer());
      py.unpackArchive(buf, "zip", { extractDir: 目标根 });
      用zip = true;
    }
  } catch (e) {
    postMessage({ 类型: "进度", 消息: `zip 解包失败，回退逐文件：${e.message}` });
  }
  if (!用zip) {
    const 根 = `/静态/py/${encodeURIComponent(语言)}/`;
    const 清单 = await (await fetch(`${根}清单.json`)).json();
    for (const 相对路径 of 清单.文件) {
      const resp = await fetch(`${根}${相对路径}`);
      if (!resp.ok) throw new Error(`加载失败：${根}${相对路径}`);
      const py路径 = `${目标根}/${相对路径}`;
      py.FS.mkdirTree(py路径.split('/').slice(0, -1).join('/'));
      py.FS.writeFile(py路径, await resp.text(), { encoding: "utf8" });
    }
  }
  py.runPython(`
import sys
if '/${语言}' not in sys.path:
    sys.path.insert(0, '/${语言}')
`);
  // 极快专属两处补丁：
  // 1) JIKUAI_PATH —— module_loader._search_paths 用 `__file__ + '../../stdlib'`
  //    定位标准库，在 /极快/jikuai/ 布局下算出 /极快/stdlib（正确）；但保险起见
  //    显式声明，这样 `从 blocks.财务.个税 导入 缴税。` 一定能解析到
  //    /极快/stdlib/blocks/财务/个税/个税.jk。
  // 2) retrieval 索引 —— ai/retrieval.py 用 `__file__` 往上 3 级（假设自己在
  //    <repo>/src/jikuai/ai/），本布局只有 2 层，上 3 级会走出包根。手动喂索引。
  if (语言 === "极快") {
    py.runPython(`
import os, json
os.environ['JIKUAI_PATH'] = '/极快/stdlib'
from jikuai.ai import retrieval as _R
_idx = '/极快/stdlib/blocks/索引.json'
if os.path.isfile(_idx) and _R._cached_retriever is None:
    with open(_idx, 'r', encoding='utf-8') as _f:
        _blocks = json.load(_f).get('块', [])
    _R._cached_retriever = _R.Retriever(_blocks, vector_index=None)
`);
  }
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
  const { 类型, 语言, 源码, 会话id, 依赖语言 } = e.data;
  if (类型 === "跑Python") {
    // 直接跑 Python 代码（选块/组码等辅助调用），需先准备好依赖语言的包
    // 返回值：Python 代码末行表达式（通常是 json.dumps(...) 出来的字符串），
    // 打包成 {stdout: 原始} —— 与语言桥消息格式保持一致，调用方自己 JSON.parse。
    try {
      await 准备语言(依赖语言 || "极快");
      postMessage({ 类型: "开始执行", 会话id });  // 加载已完成，主线程此刻才开始 5 秒计时
      const py = _py;
      const 原始 = py.runPython(源码);
      postMessage({ 类型: "结果", 会话id, stdout: 原始 == null ? "" : String(原始), 返回值: null });
    } catch (err) {
      postMessage({ 类型: "错误", 会话id, 消息: String(err.message || err) });
    }
    return;
  }
  if (类型 !== "跑") return;
  try {
    await 准备语言(语言);
    postMessage({ 类型: "开始执行", 会话id });  // 加载已完成，主线程此刻才开始 5 秒计时
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
