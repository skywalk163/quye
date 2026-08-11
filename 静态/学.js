// 学习区：单关卡判对 + 进度。关卡页有 .学关卡[data-语言][data-关卡]；索引页只读进度打勾。
const 进度KEY = 'quye_学习进度';
const 加载超时毫秒 = 180000;
const 执行超时毫秒 = 5000;

function 读进度() {
  try { return JSON.parse(localStorage.getItem(进度KEY) || '{}'); } catch { return {}; }
}
function 存完成(语言, 关卡) {
  const p = 读进度();
  p[`${语言}/${关卡}`] = true;
  localStorage.setItem(进度KEY, JSON.stringify(p));
}

// ---- 索引页：给已完成关卡打勾 ----
(function 标记完成() {
  const p = 读进度();
  document.querySelectorAll('.关卡组 a').forEach((a) => {
    const m = a.getAttribute('href').match(/\/学\/([^/]+)\/([^/]+)\//);
    if (m && p[`${decodeURIComponent(m[1])}/${decodeURIComponent(m[2])}`]) a.classList.add('已完成');
  });
})();

// ---- 索引页：进度导出/导入（换设备用） ----
(function 进度导入导出() {
  const 导出钮 = document.getElementById('导出进度');
  const 导入钮 = document.getElementById('导入进度');
  const 文件框 = document.getElementById('导入文件');
  const 提示 = document.getElementById('进度提示');
  const 统计 = document.getElementById('进度统计');
  if (!导出钮 || !导入钮 || !文件框) return;

  function 刷新统计() {
    const 完成 = Object.values(读进度()).filter(Boolean).length;
    const 总 = document.querySelectorAll('.关卡组 a').length;
    if (统计) 统计.textContent = `已完成 ${完成} / ${总} 关`;
  }
  刷新统计();

  function 说(t) { if (提示) 提示.textContent = t; }

  导出钮.addEventListener('click', () => {
    const 包 = { 版本: 1, 类型: 'quye学习进度', 进度: 读进度() };
    const blob = new Blob([JSON.stringify(包, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'quye学习进度.json';
    a.click();
    URL.revokeObjectURL(a.href);
    说('已导出');
  });

  导入钮.addEventListener('click', () => 文件框.click());

  文件框.addEventListener('change', async () => {
    const f = 文件框.files && 文件框.files[0];
    if (!f) return;
    try {
      const 包 = JSON.parse(await f.text());
      const 来 = 包 && 包.进度;
      if (!来 || typeof 来 !== 'object' || Array.isArray(来)) throw new Error('格式不认');
      // 只接受 "语言/关卡": true 形式，且键必须对得上页面上的关卡，避免灌入垃圾
      const 合法键 = new Set();
      document.querySelectorAll('.关卡组 a').forEach((a) => {
        const m = a.getAttribute('href').match(/\/学\/([^/]+)\/([^/]+)\//);
        if (m) 合法键.add(`${decodeURIComponent(m[1])}/${decodeURIComponent(m[2])}`);
      });
      const 合并 = 读进度();
      let 新增 = 0;
      for (const [k, v] of Object.entries(来)) {
        if (v === true && 合法键.has(k) && !合并[k]) { 合并[k] = true; 新增++; }
      }
      localStorage.setItem(进度KEY, JSON.stringify(合并));
      说(`已导入，新增 ${新增} 关`);
      document.querySelectorAll('.关卡组 a').forEach((a) => {
        const m = a.getAttribute('href').match(/\/学\/([^/]+)\/([^/]+)\//);
        if (m && 合并[`${decodeURIComponent(m[1])}/${decodeURIComponent(m[2])}`]) a.classList.add('已完成');
      });
      刷新统计();
    } catch (e) {
      说(`导入失败：${e.message}`);
    } finally {
      文件框.value = '';
    }
  });
})();

// ---- 关卡页：判对 ----
const 关卡节点 = document.querySelector('.学关卡');
if (关卡节点) {
  const 语言 = 关卡节点.dataset.语言;
  const 关卡 = 关卡节点.dataset.关卡;
  const 在线可判 = 关卡节点.dataset.在线可判 === '1';

  let _worker = null, _会话id = 0;
  const _会话 = new Map();
  function 设状态(t) { document.getElementById('状态').textContent = t; }
  function 收消息(e) {
    const { 会话id, 类型 } = e.data;
    if (类型 === '进度') { 设状态(e.data.消息); return; }
    const 会话 = _会话.get(会话id);
    if (!会话) return;
    if (类型 === '开始执行') { 会话.开始执行(); return; }
    会话.收尾(e.data);
  }
  function 取worker() {
    if (_worker) return _worker;
    _worker = new Worker('/静态/执行器.js');
    _worker.addEventListener('message', 收消息);
    _worker.addEventListener('error', (e) => 设状态(`Worker 异常：${e.message}`));
    return _worker;
  }
  function 弃worker() { if (_worker) { _worker.terminate(); _worker = null; } _会话.clear(); }
  function 发消息(消息) {
    return new Promise((resolve, reject) => {
      const id = ++_会话id;
      let 定时器 = null;
      const 起表 = (毫秒, 说明) => {
        if (定时器) clearTimeout(定时器);
        定时器 = setTimeout(() => {
          _会话.delete(id); 弃worker();
          设状态(`已中止：${说明}`);
          reject(new Error(`${说明}（超过 ${毫秒 / 1000} 秒）`));
        }, 毫秒);
      };
      _会话.set(id, {
        开始执行: () => 起表(执行超时毫秒, '执行超时'),
        收尾: (data) => {
          if (定时器) clearTimeout(定时器);
          _会话.delete(id);
          if (data.类型 === '结果') resolve(data); else reject(new Error(data.消息));
        },
      });
      起表(加载超时毫秒, '加载中');
      取worker().postMessage({ ...消息, 会话id: id });
    });
  }

  // 预期输出：从 /数据/学习基线.json 拉当前关卡
  let _预期 = null;
  async function 取预期() {
    if (_预期 !== null) return _预期;
    const 基线 = await (await fetch('/数据/学习基线.json')).json();
    const x = (基线[语言] || []).find((e) => e.关卡 === 关卡);
    _预期 = x ? x.预期stdout : '';
    document.getElementById('预期').textContent = _预期;
    return _预期;
  }
  取预期();

  function 归一(s) { return String(s).replace(/\r\n/g, '\n').replace(/\s+$/g, ''); }

  document.getElementById('跑').addEventListener('click', async () => {
    const 源码 = document.getElementById('代码').value;
    const 结果 = document.getElementById('结果');
    结果.textContent = '执行中...';
    try {
      const r = await 发消息({ 类型: '跑', 语言, 源码 });
      结果.textContent = r.stdout;
      if (!在线可判) { 设状态('本关不支持在线判对，请对照预期自查'); return; }
      const 预期 = await 取预期();
      if (归一(r.stdout) === 归一(预期)) {
        设状态('✓ 判对！进度已保存');
        存完成(语言, 关卡);
      } else {
        设状态('✗ 输出与预期不一致，再看看');
      }
    } catch (e) {
      结果.textContent = `[错误] ${e.message}`;
      设状态('执行出错');
    }
  });

  document.getElementById('看答案').addEventListener('click', async () => {
    const box = document.getElementById('参考答案');
    if (!box.textContent) {
      const url = `/数据/学习素材/${encodeURIComponent(语言)}/${encodeURIComponent(关卡)}/参考答案.txt`;
      box.textContent = await (await fetch(url)).text();
    }
    box.hidden = !box.hidden;
  });

  document.getElementById('代码').addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); document.getElementById('跑').click(); }
  });
}
