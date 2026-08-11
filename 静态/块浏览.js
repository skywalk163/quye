// /块 页：分类筛选、搜索、点击查看详情、在浏览器里跑官方示例。
(function () {
  const 网格 = document.getElementById('块网格');
  const 详情 = document.getElementById('块详情');
  const 搜索框 = document.getElementById('块搜索框');
  if (!网格 || !详情) return;

  // ---- 领域筛选 + 搜索 ----
  let 当前领域 = '全部';
  document.querySelectorAll('.领域标签').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.领域标签').forEach((b) => b.classList.remove('激活'));
      btn.classList.add('激活');
      当前领域 = btn.dataset.领域;
      过滤();
    });
  });

  function 过滤() {
    const q = (搜索框 ? 搜索框.value : '').trim().toLowerCase();
    let 显示数 = 0;
    网格.querySelectorAll('.块卡').forEach((卡) => {
      const 名 = 卡.dataset.名称.toLowerCase();
      const 描 = 卡.querySelector('.块描述').textContent.toLowerCase();
      const 领配 = 当前领域 === '全部' || 卡.dataset.领域 === 当前领域;
      const 文配 = !q || 名.includes(q) || 描.includes(q);
      卡.hidden = !(领配 && 文配);
      if (!卡.hidden) 显示数++;
    });
  }
  if (搜索框) {
    let 定时器 = null;
    搜索框.addEventListener('input', () => {
      clearTimeout(定时器);
      定时器 = setTimeout(过滤, 120);
    });
  }

  // ---- Worker（懒建，与工作台同规则；执行 5 秒超时） ----
  const 加载超时 = 180000;
  const 执行超时 = 5000;
  let _worker = null;
  let _会话id = 0;
  const _会话 = new Map();

  function 取worker() {
    if (_worker) return _worker;
    _worker = new Worker('/静态/执行器.js');
    _worker.addEventListener('message', (e) => {
      const { 会话id, 类型 } = e.data;
      if (类型 === '进度') { 设状态(e.data.消息); return; }
      const s = _会话.get(会话id);
      if (!s) return;
      if (类型 === '开始执行') { s.开始执行(); return; }
      s.收尾(e.data);
    });
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
          reject(new Error(`${说明}（超过 ${毫秒 / 1000} 秒）`));
        }, 毫秒);
      };
      _会话.set(id, {
        开始执行: () => 起表(执行超时, '执行超时'),
        收尾: (data) => {
          if (定时器) clearTimeout(定时器);
          _会话.delete(id);
          if (data.类型 === '结果') resolve(data); else reject(new Error(data.消息));
        },
      });
      起表(加载超时, '加载超时');
      取worker().postMessage({ ...消息, 会话id: id });
    });
  }

  // ---- 详情面板 ----
  let _索引Promise = null;
  function 取索引() {
    if (!_索引Promise) _索引Promise = fetch('/数据/块索引.json').then((r) => r.json());
    return _索引Promise;
  }
  function 设状态(t) {
    const s = 详情.querySelector('.详状态');
    if (s) s.textContent = t;
  }

  网格.addEventListener('click', async (e) => {
    const 卡 = e.target.closest('.块卡');
    if (!卡) return;
    const 名 = 卡.dataset.名称;
    const 索引 = await 取索引();
    const b = (索引.块 || []).find((x) => x.名称 === 名);
    if (!b) return;
    渲染详情(b);
    详情.hidden = false;
    详情.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  function 渲染详情(b) {
    const 导出名 = (b.导出 || [b.名称])[0];
    const 入参 = (b.输入 || []).map((i) => {
      const t = i.类型 && typeof i.类型 === 'object' ? `${i.类型.类型}/${i.类型.元素类型 || ''}` : i.类型;
      return `${i.名 || '?'}:${t || '?'}`;
    }).join('、') || '无';
    const 出t = b.输出 && typeof b.输出.类型 === 'object' ? b.输出.类型.类型 : (b.输出 && b.输出.类型);
    const 领域 = (b.领域 || ['未分类'])[0];

    详情.innerHTML = `
      <div class="详头">
        <button type="button" class="详关闭" aria-label="关闭详情">×</button>
        <h2>${escapeHtml(b.名称)}</h2>
        <p class="详签名"><code>${escapeHtml(导出名)}(${escapeHtml(入参)}) → ${escapeHtml(出t || '?')}</code></p>
        <p class="详标签">${escapeHtml(领域)} · ${escapeHtml(b.稳定性 || '')} · 层级 ${b.层级 ?? '?'}</p>
        <p class="详描述">${escapeHtml(b.描述 || '')}</p>
      </div>
      <div class="详示例">
        <h3>官方示例</h3>
        <pre class="详代码">${escapeHtml(b.示例 || '（无示例）')}</pre>
        <div class="详按钮">
          <button type="button" class="详跑" ${b.示例 ? '' : 'disabled'}>在浏览器里跑</button>
          <a class="详按钮次" href="/台/">在工作台修改这段代码 →</a>
        </div>
        <p class="详状态"></p>
        <pre class="详输出" hidden></pre>
      </div>
    `;
    详情.querySelector('.详关闭').addEventListener('click', () => { 详情.hidden = true; });
    const 跑钮 = 详情.querySelector('.详跑');
    if (跑钮) 跑钮.addEventListener('click', async () => {
      const 输出 = 详情.querySelector('.详输出');
      输出.hidden = false;
      输出.textContent = '执行中…';
      设状态('准备极快解释器（首次约 30 秒）');
      try {
        const r = await 发消息({ 类型: '跑', 语言: '极快', 源码: b.示例 });
        输出.textContent = r.stdout || '(无输出)';
        设状态('✓ 已完成');
      } catch (err) {
        输出.textContent = `[错误] ${err.message}`;
        设状态('执行出错');
      }
    });
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }
})();
