// 工作台主逻辑：语言切换、直跑、极快选块-组码-跑
const 超时毫秒 = 5000;

let _worker = null;
let _会话id = 0;
const _会话回调 = new Map();

function 收消息(e) {
  const { 会话id, 类型 } = e.data;
  if (类型 === '进度') {
    document.getElementById('状态').textContent = e.data.消息;
    return;
  }
  const cb = _会话回调.get(会话id);
  if (cb) {
    _会话回调.delete(会话id);
    cb(e.data);
  }
}

function 取worker() {
  if (_worker) return _worker;
  _worker = new Worker('/静态/执行器.js');
  _worker.addEventListener('message', 收消息);
  _worker.addEventListener('error', (e) => {
    document.getElementById('状态').textContent = `Worker 异常：${e.message}`;
  });
  return _worker;
}

// terminate 后 Worker 不可复用，必须丢掉引用让下次调用重建（Pyodide 会重新加载）
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
        document.getElementById('状态').textContent = '已中止，下次运行会重新加载 Pyodide';
        reject(new Error(`执行超时 ${超时毫秒}ms，Worker 已中止`));
      }
    }, 超时毫秒);
  });
}

function 转义(s) {
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function 切换语言(名) {
  document.querySelectorAll('.极快专属').forEach((el) => {
    el.style.display = 名 === '极快' ? '' : 'none';
  });
}

document.getElementById('语言选择').addEventListener('change', (e) => 切换语言(e.target.value));
切换语言(document.getElementById('语言选择').value);

document.getElementById('跑').addEventListener('click', async () => {
  const 语言 = document.getElementById('语言选择').value;
  const 源码 = document.getElementById('代码').value;
  const 结果 = document.getElementById('结果');
  结果.textContent = '执行中...';
  try {
    const r = await 跑代码(语言, 源码);
    结果.textContent = r.stdout + (r.返回值 ? `\n\n返回值：${r.返回值}` : '');
  } catch (e) {
    结果.textContent = `[错误] ${e.message}`;
  }
});

document.getElementById('清空').addEventListener('click', () => {
  document.getElementById('代码').value = '';
  document.getElementById('结果').textContent = '';
});

document.getElementById('代码').addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    document.getElementById('跑').click();
  }
});

// 极快选块：调 Pyodide 里的 retrieval，展示候选卡片，点候选后组码
document.getElementById('选块').addEventListener('click', async () => {
  const 需求 = document.getElementById('需求').value.trim();
  if (!需求) return;
  const 状态 = document.getElementById('状态');
  状态.textContent = '选块中...';
  const 选块代码 = `
import json
from jikuai.ai.retrieval import retrieve
_res = retrieve(${JSON.stringify(需求)}, top=5)
print(json.dumps([{'名称': r.name, '领域': r.domain, '分数': r.score, '路径': r.path} for r in _res], ensure_ascii=False))
`;
  try {
    const r = await 跑代码('极快', 选块代码);
    const 候选 = JSON.parse(r.stdout.trim().split('\n').pop() || '[]');
    渲染候选(候选);
    状态.textContent = `选出 ${候选.length} 个候选块`;
  } catch (e) {
    document.getElementById('候选').textContent = `[选块失败] ${e.message}`;
    状态.textContent = '选块失败';
  }
});

function 渲染候选(候选) {
  const div = document.getElementById('候选');
  div.innerHTML = 候选.map((c, i) => `
    <div class="候选卡" data-idx="${i}">
      <div class="候选名">${转义(c.名称)}</div>
      <div class="候选meta">${转义(c.领域)} · ${Number(c.分数).toFixed(2)}</div>
    </div>
  `).join('');
  div.querySelectorAll('.候选卡').forEach((el) => {
    el.addEventListener('click', async () => {
      const c = 候选[Number(el.dataset.idx)];
      const 组码代码 = `
from glue import synthesize
方案 = {"步骤": [{"块": ${JSON.stringify(c.名称)}, "领域": ${JSON.stringify(c.领域)}}]}
print(synthesize(方案))
`;
      try {
        const r = await 跑代码('极快', 组码代码);
        document.getElementById('代码').value = r.stdout.trim();
        document.getElementById('状态').textContent = `已组出 ${c.名称} 的代码`;
      } catch (e) {
        document.getElementById('状态').textContent = `[组码失败] ${e.message}`;
      }
    });
  });
}
