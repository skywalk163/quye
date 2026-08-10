// Pyodide 加载器：自托管主 + CDN 兜底并发
// 谁先到用谁。返回 Promise<Pyodide>。
export const PYODIDE_VERSION = "0.26.4";
const 自托管 = "/静态/pyodide/";
const CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let _缓存Promise = null;

export function 加载Pyodide(进度回调) {
  if (_缓存Promise) return _缓存Promise;
  _缓存Promise = _并发拉取(进度回调);
  return _缓存Promise;
}

async function _并发拉取(进度回调) {
  const 尝试 = async (base) => {
    if (进度回调) 进度回调(`尝试 ${base}`);
    const mod = await import(`${base}pyodide.mjs`);
    const py = await mod.loadPyodide({ indexURL: base });
    return { py, base };
  };

  try {
    const 结果 = await Promise.any([尝试(自托管), 尝试(CDN)]);
    if (进度回调) 进度回调(`Pyodide 就绪（源：${结果.base}）`);
    return 结果.py;
  } catch (e) {
    const 细节 = e.errors ? e.errors.map((x) => x.message).join("; ") : e.message;
    throw new Error(`Pyodide 双通道拉取均失败：${细节}`);
  }
}
