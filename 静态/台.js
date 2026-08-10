// 工作台主逻辑：语言切换、直跑、极快选块-组码-跑
// 两段超时：加载阶段（Pyodide 冷启 + 语言包挂载）宽松，执行阶段严格 5 秒。
// Worker 在 准备语言 完成后回一条 {类型:"开始执行"}，主线程收到后才切到 5 秒表。
const 加载超时毫秒 = 180000;
const 执行超时毫秒 = 5000;

let _worker = null;
let _会话id = 0;
const _会话 = new Map();

function 设状态(文本) {
  document.getElementById('状态').textContent = 文本;
}

function 收消息(e) {
  const { 会话id, 类型 } = e.data;
  if (类型 === '进度') {
    设状态(e.data.消息);
    return;
  }
  const 会话 = _会话.get(会话id);
  if (!会话) return;
  if (类型 === '开始执行') {
    会话.开始执行();
    return;
  }
  会话.收尾(e.data);
}

function 取worker() {
  if (_worker) return _worker;
  _worker = new Worker('/静态/执行器.js');
  _worker.addEventListener('message', 收消息);
  _worker.addEventListener('error', (e) => 设状态(`Worker 异常：${e.message}`));
  return _worker;
}

// terminate 后 Worker 不可复用，必须丢掉引用让下次调用重建（Pyodide 会重新加载）
function 弃worker() {
  if (_worker) {
    _worker.terminate();
    _worker = null;
  }
  _会话.clear();
}

function 发消息(消息) {
  return new Promise((resolve, reject) => {
    const id = ++_会话id;
    let 定时器 = null;

    const 起表 = (毫秒, 说明) => {
      if (定时器) clearTimeout(定时器);
      定时器 = setTimeout(() => {
        _会话.delete(id);
        弃worker();
        设状态(`已中止：${说明}。下次运行会重新加载 Pyodide`);
        reject(new Error(`${说明}（超过 ${毫秒 / 1000} 秒），Worker 已中止`));
      }, 毫秒);
    };

    _会话.set(id, {
      开始执行: () => 起表(执行超时毫秒, '执行超时'),
      收尾: (data) => {
        if (定时器) clearTimeout(定时器);
        _会话.delete(id);
        if (data.类型 === '结果') resolve(data);
        else reject(new Error(data.消息));
      },
    });

    起表(加载超时毫秒, '加载超时');
    取worker().postMessage({ ...消息, 会话id: id });
  });
}

// 跑某门语言的源码（走语言桥，源码是该语言的语法）
function 跑代码(语言, 源码) {
  return 发消息({ 类型: '跑', 语言, 源码 });
}

// 直跑 Python（选块/组码等辅助调用，源码是 Python 而非中文语言语法）
function 跑Python(依赖语言, 源码) {
  return 发消息({ 类型: '跑Python', 依赖语言, 源码 });
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
_blocks_data = json.loads(open('/极快/stdlib/blocks/索引.json', encoding='utf-8').read()).get('块', [])
_block_map = {b['名称']: b for b in _blocks_data}
_out = []
for r in _res:
    b = _block_map.get(r.name, {})
    导出 = (b.get('导出') or [r.name])[0]
    _out.append({'名称': r.name, '领域': r.domain, '分数': r.score, '导出名': 导出})
json.dumps(_out, ensure_ascii=False)
`;
  try {
    const r = await 跑Python('极快', 选块代码);
    const 候选 = JSON.parse(r.stdout || '[]');
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
方案 = {"步骤": [{"块": ${JSON.stringify(c.名称)}, "领域": ${JSON.stringify(c.领域)}, "导出名": ${JSON.stringify(c.导出名 || c.名称)}}]}
synthesize(方案)
`;
      try {
        const r = await 跑Python('极快', 组码代码);
        document.getElementById('代码').value = (r.stdout || '').trim();
        document.getElementById('状态').textContent = `已组出 ${c.名称} 的代码`;
      } catch (e) {
        document.getElementById('状态').textContent = `[组码失败] ${e.message}`;
      }
    });
  });
}
