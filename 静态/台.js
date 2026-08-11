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
    存历史({ 语言, 源码, 需求: document.getElementById('需求').value.trim(), 输出: r.stdout });
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
    _out.append({
        '名称': r.name, '领域': r.domain, '分数': r.score,
        '导出名': 导出, '输入': b.get('输入', []),
    })
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

// 按入参名/类型猜一个合理的示例值。块名多是中文财务/数据领域，
// 命中名字用领域常识，否则按类型兜底。
const _示例值表 = {
  月收: 20000, 含税: 17202, 不含税: 15000, 税率: 0.13,
  本金: 100000, 年利率: 0.05, 月利率: 0.004, 期数: 12, 月数: 12, 年数: 5,
  金额: 10000, 数值: 100, 分数: 85, 折现率: 0.08, 现值: 10000, 终值: 12000,
};
function 示例参数(输入项) {
  const 名 = 输入项.名 || '';
  if (名 in _示例值表) return String(_示例值表[名]);
  const 类型 = 输入项.类型 || '数';
  if (类型 === '数') return '100';
  if (类型 === '文' || 类型 === '串' || 类型 === '文本') return '"示例"';
  if (类型 === '真假' || 类型 === '布尔') return '真';
  return '100';
}

// 把 synthesize 产出的 `名(?)` 占位替换成按入参 schema 生成的示例调用 `名(v1, v2)`
function 填示例参数(骨架, 输入s) {
  if (!输入s || !输入s.length) return 骨架;
  const 参数串 = 输入s.map(示例参数).join(', ');
  return 骨架.replace(/\(\s*\?\s*\)/, `(${参数串})`);
}

function 渲染候选(候选) {
  const div = document.getElementById('候选');
  div.innerHTML = 候选.map((c, i) => `
    <div class="候选卡" data-idx="${i}">
      <div class="候选名">${转义(c.名称)}</div>
      <div class="候选meta">${转义(c.领域)} · ${Number(c.分数).toFixed(2)}</div>
      <button type="button" class="候选加管道" data-idx="${i}">加入管道</button>
    </div>
  `).join('');
  div.querySelectorAll('.候选卡').forEach((el) => {
    el.addEventListener('click', async (ev) => {
      if (ev.target.classList.contains('候选加管道')) return; // 加管道不触发组码
      const c = 候选[Number(el.dataset.idx)];
      const 组码代码 = `
from glue import synthesize
方案 = {"步骤": [{"块": ${JSON.stringify(c.名称)}, "领域": ${JSON.stringify(c.领域)}, "导出名": ${JSON.stringify(c.导出名 || c.名称)}}]}
synthesize(方案)
`;
      try {
        const r = await 跑Python('极快', 组码代码);
        const 骨架 = (r.stdout || '').trim();
        // synthesize 只写一个 `(?)`，不体现真实入参个数——增值税这类多参块
        // 照原样只填一个值会让其余参数留 None，块内部算术直接崩。
        // 这里按 索引.json 的 输入 schema 一次填齐示例值，代码开箱可跑。
        const 输入s = c.输入 || [];
        document.getElementById('代码').value = 填示例参数(骨架, 输入s);
        const 参数说明 = 输入s.length
          ? `入参 ${输入s.map((x) => x.名).join('、')}（已填示例值，可改）`
          : '无入参';
        设状态(`已组出 ${c.名称} 的代码 · ${参数说明}`);
      } catch (e) {
        设状态(`[组码失败] ${e.message}`);
      }
    });
  });
  div.querySelectorAll('.候选加管道').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      加入管道(候选[Number(btn.dataset.idx)]);
    });
  });
}

// ---------- M6：多步管道组装 ----------
// 每一步是一个独立的极快代码片段（默认由 synthesize 组出、可手改），
// 「逐步跑」把每步单独送进 Worker，依次展示中间 stdout——
// 这是极快管道范式在 Web 上的可视化，不是真正的值传递管道。
let _管道 = [];

function 加入管道(c) {
  _管道.push({ 名称: c.名称, 领域: c.领域, 导出名: c.导出名 || c.名称, 输入: c.输入 || [], 源码: '' });
  渲染管道();
  设状态(`已加入管道第 ${_管道.length} 步：${c.名称}`);
}

function 渲染管道() {
  const 段 = document.getElementById('管道段');
  const 列 = document.getElementById('管道列表');
  if (!段 || !列) return;
  段.hidden = _管道.length === 0;
  列.textContent = '';
  _管道.forEach((步, i) => {
    const li = document.createElement('li');
    li.className = '管道步';

    const 头 = document.createElement('div');
    头.className = '管道步头';
    const 名 = document.createElement('strong');
    名.textContent = `${步.名称}`;
    const 域 = document.createElement('small');
    域.textContent = ` ${步.领域}`;
    const 删 = document.createElement('button');
    删.type = 'button';
    删.className = '小钮';
    删.textContent = '移除';
    删.addEventListener('click', () => { _管道.splice(i, 1); 渲染管道(); });
    头.append(名, 域, 删);

    const 框 = document.createElement('textarea');
    框.className = '管道步码';
    框.rows = 3;
    框.placeholder = '这一步的极快代码（留空则点「逐步跑」时自动组码）';
    框.value = 步.源码;
    框.addEventListener('input', () => { 步.源码 = 框.value; });

    li.append(头, 框);
    列.appendChild(li);
  });
}

async function 组一步(步) {
  const 组码代码 = `
from glue import synthesize
方案 = {"步骤": [{"块": ${JSON.stringify(步.名称)}, "领域": ${JSON.stringify(步.领域)}, "导出名": ${JSON.stringify(步.导出名)}}]}
synthesize(方案)
`;
  const r = await 跑Python('极快', 组码代码);
  return 填示例参数((r.stdout || '').trim(), 步.输入);
}

const 跑管道钮 = document.getElementById('跑管道');
if (跑管道钮) {
  跑管道钮.addEventListener('click', async () => {
    const 出 = document.getElementById('管道结果');
    if (!_管道.length) { 出.textContent = '管道为空，先从候选块「加入管道」'; return; }
    出.textContent = '';
    for (let i = 0; i < _管道.length; i++) {
      const 步 = _管道[i];
      设状态(`跑管道第 ${i + 1}/${_管道.length} 步：${步.名称}`);
      try {
        if (!步.源码.trim()) {
          步.源码 = await 组一步(步);
          渲染管道();
        }
        const r = await 跑代码('极快', 步.源码);
        出.textContent += `— 第 ${i + 1} 步 ${步.名称} —\n${r.stdout || '(无输出)'}\n\n`;
      } catch (e) {
        出.textContent += `— 第 ${i + 1} 步 ${步.名称} —\n[错误] ${e.message}\n\n`;
        设状态(`管道在第 ${i + 1} 步中断`);
        return;
      }
    }
    设状态(`管道 ${_管道.length} 步全部跑完`);
  });
}

const 清管道钮 = document.getElementById('清管道');
if (清管道钮) {
  清管道钮.addEventListener('click', () => {
    _管道 = [];
    渲染管道();
    document.getElementById('管道结果').textContent = '';
  });
}

// ---------- M6：工作台历史（localStorage 最近 20 条） ----------
const 历史KEY = 'quye_工作台历史';
const 历史上限 = 20;

function 读历史() {
  try {
    const v = JSON.parse(localStorage.getItem(历史KEY) || '[]');
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}

function 存历史(条) {
  if (!条.源码 || !条.源码.trim()) return;
  const 表 = 读历史();
  // 同语言同源码去重：把旧的那条提到最前，避免反复跑同一段刷满列表
  const 位 = 表.findIndex((x) => x.语言 === 条.语言 && x.源码 === 条.源码);
  if (位 >= 0) 表.splice(位, 1);
  表.unshift({ ...条, 时间: new Date().toISOString() });
  localStorage.setItem(历史KEY, JSON.stringify(表.slice(0, 历史上限)));
  渲染历史();
}

function 渲染历史() {
  const 列 = document.getElementById('历史列表');
  if (!列) return;
  const 表 = 读历史();
  列.textContent = '';
  if (!表.length) {
    const li = document.createElement('li');
    li.className = '历史空';
    li.textContent = '还没有记录，跑一段代码就会出现在这里';
    列.appendChild(li);
    return;
  }
  表.forEach((条, i) => {
    const li = document.createElement('li');
    li.className = '历史条';

    const 钮 = document.createElement('button');
    钮.type = 'button';
    钮.className = '历史回填';
    const 摘 = 条.源码.replace(/\s+/g, ' ').slice(0, 48);
    钮.textContent = `${条.语言} · ${条.需求 ? 条.需求 + ' · ' : ''}${摘}`;
    钮.title = 条.源码;
    钮.addEventListener('click', () => {
      document.getElementById('语言选择').value = 条.语言;
      切换语言(条.语言);
      document.getElementById('代码').value = 条.源码;
      if (条.需求) document.getElementById('需求').value = 条.需求;
      设状态(`已回填第 ${i + 1} 条记录`);
    });

    const 时 = document.createElement('small');
    时.className = '历史时间';
    时.textContent = 条.时间 ? 条.时间.slice(5, 16).replace('T', ' ') : '';

    li.append(钮, 时);
    列.appendChild(li);
  });
}

const 清历史钮 = document.getElementById('清历史');
if (清历史钮) {
  清历史钮.addEventListener('click', () => {
    localStorage.removeItem(历史KEY);
    渲染历史();
  });
}

渲染历史();
