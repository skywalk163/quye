// 对照页：四门语言并排跑同一需求，每格独立
const 超时毫秒 = 5000;

let _worker = null;
let _会话id = 0;
const _会话回调 = new Map();

function 收消息(e) {
  const cb = _会话回调.get(e.data.会话id);
  if (cb) {
    _会话回调.delete(e.data.会话id);
    cb(e.data);
  }
}

function 取worker() {
  if (_worker) return _worker;
  _worker = new Worker('/静态/执行器.js');
  _worker.addEventListener('message', 收消息);
  return _worker;
}

// terminate 后 Worker 不可复用，丢引用让下次调用重建（Pyodide 会重新加载）
function 弃worker() {
  if (_worker) {
    _worker.terminate();
    _worker = null;
  }
  _会话回调.clear();
}

function 跑代码(语言, 源码) {
  return new Promise((resolve, reject) => {
    const id = ++_会话id;
    _会话回调.set(id, (data) => {
      if (data.类型 === '结果') resolve(data);
      else reject(new Error(data.消息));
    });
    取worker().postMessage({ 类型: '跑', 语言, 源码, 会话id: id });
    setTimeout(() => {
      if (_会话回调.has(id)) {
        弃worker();
        reject(new Error(`超时 ${超时毫秒 / 1000}s，Worker 已中止`));
      }
    }, 超时毫秒);
  });
}

// 加载示例集，填充下拉与格子
fetch('/数据/示例集.json')
  .then((r) => r.json())
  .then((集) => {
    const 选择 = document.getElementById('示例选择');
    集.对照示例.forEach((条, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = 条.标题;
      选择.appendChild(opt);
    });
    const 加载 = (i) => {
      const 条 = 集.对照示例[i];
      document.querySelectorAll('.对照-格').forEach((格) => {
        格.querySelector('textarea').value = 条[格.dataset.语言] || '// 该语言暂无示例';
        格.querySelector('.结果').textContent = '';
      });
    };
    选择.addEventListener('change', (e) => 加载(Number(e.target.value)));
    if (集.对照示例.length) 加载(0);
  })
  .catch((e) => {
    document.getElementById('对照状态').textContent = `示例集加载失败：${e.message}`;
  });

document.querySelectorAll('.对照-格').forEach((格) => {
  格.querySelector('.跑').addEventListener('click', async () => {
    const 语言 = 格.dataset.语言;
    const 结果 = 格.querySelector('.结果');
    结果.textContent = '执行中...';
    try {
      const r = await 跑代码(语言, 格.querySelector('textarea').value);
      结果.textContent = r.stdout + (r.返回值 ? `\n返回值：${r.返回值}` : '');
    } catch (e) {
      结果.textContent = `[错误] ${e.message}`;
    }
  });
});
