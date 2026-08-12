// /块 页：前端驱动渲染。
// 两份数据分工：
//   /数据/块清单.json —— 卡片要的那几个字段，首屏拉它，驱动网格
//   /数据/块索引.json —— 全量含示例源码（体积的九成在示例上），点开某块才拉
// 服务端只输出筛选按钮与空网格容器，不再内联上万张卡片（原先把 index.html 撑到 3 MB+）。
(function () {
  const 网格 = document.getElementById('块网格');
  const 详情 = document.getElementById('块详情');
  const 搜索框 = document.getElementById('块搜索框');
  const 提示 = document.getElementById('块提示');
  if (!网格 || !详情) return;

  // ---- 数据 ----
  let _清单 = [];        // 轻清单，首屏加载
  let _索引Promise = null;  // 全量索引，首次点卡片才拉
  function 取索引() {
    if (!_索引Promise) _索引Promise = fetch('/数据/块索引.json').then(r => r.json());
    return _索引Promise;
  }

  // ---- 筛选状态 ----
  let 当前语言 = '全部';
  let 当前领域 = '全部';
  let 当前搜索 = '';

  document.querySelectorAll('.语言标签').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.语言标签').forEach(b => b.classList.remove('激活'));
      btn.classList.add('激活');
      当前语言 = btn.dataset.语言;
      渲染网格();
    });
  });
  document.querySelectorAll('.领域标签').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.领域标签').forEach(b => b.classList.remove('激活'));
      btn.classList.add('激活');
      当前领域 = btn.dataset.领域;
      渲染网格();
    });
  });
  if (搜索框) {
    let 定时器 = null;
    搜索框.addEventListener('input', () => {
      clearTimeout(定时器);
      定时器 = setTimeout(() => { 当前搜索 = 搜索框.value.trim().toLowerCase(); 渲染网格(); }, 150);
    });
  }

  // ---- 渲染卡片网格 ----
  // 上限 500：匹配全部一万条时不硬渲染，提示缩窄筛选——DOM 节点数是这页的主要成本
  const 渲染上限 = 500;

  function 渲染网格() {
    const 匹配 = _清单.filter(b => {
      if (当前语言 !== '全部' && b.语言 !== 当前语言) return false;
      if (当前领域 !== '全部' && b.领域 !== 当前领域) return false;
      if (当前搜索
          && !b.名称.toLowerCase().includes(当前搜索)
          && !(b.描述 || '').toLowerCase().includes(当前搜索)) return false;
      return true;
    });
    const 截断 = 匹配.length > 渲染上限;
    网格.innerHTML = (截断 ? 匹配.slice(0, 渲染上限) : 匹配).map(b =>
      `<button type="button" class="块卡" data-语言="${esc(b.语言)}"`
      + ` data-领域="${esc(b.领域)}" data-名称="${esc(b.名称)}">`
      + `<span class="块名">${esc(b.名称)}</span>`
      + `<span class="块签名">${esc(b.签名)}</span>`
      + `<span class="块描述">${esc(b.描述 || '')}</span>`
      + `<span class="块标记">${esc(b.语言)} · ${esc(b.领域)}`
      + `${b.稳定性 ? ' · ' + esc(b.稳定性) : ''}</span>`
      + `</button>`
    ).join('');
    if (提示) {
      if (匹配.length === 0) 提示.textContent = '没有匹配的块，换个搜索词或领域试试。';
      else if (截断) 提示.textContent = `匹配 ${匹配.length} 个，已显示前 ${渲染上限} 个——请缩窄筛选。`;
      else 提示.textContent = `显示 ${匹配.length} 个`;
    }
  }

  // ---- 初始化 ----
  fetch('/数据/块清单.json')
    .then(r => r.json())
    .then(data => { _清单 = data.块 || []; 渲染网格(); })
    .catch(e => { if (提示) 提示.textContent = `加载块清单失败：${e.message}`; });

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
  function 设状态(t) {
    const s = 详情.querySelector('.详状态');
    if (s) s.textContent = t;
  }

  网格.addEventListener('click', async (e) => {
    const 卡 = e.target.closest('.块卡');
    if (!卡) return;
    const 名 = 卡.dataset.名称;
    const 语言 = 卡.dataset.语言;
    // 首次点击要把全量索引拉下来，先把面板亮出来给个等待态
    详情.hidden = false;
    详情.innerHTML = '<p class="详载入">载入示例…</p>';
    详情.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try {
      const 索引 = await 取索引();
      // 名称在多语言下可能重名（极快/光明 都有「求和」），按 (语言,名称) 唯一定位
      const b = (索引.块 || []).find(x => x.名称 === 名 && x.语言 === 语言);
      if (!b) { 详情.innerHTML = '<p class="详载入">索引里没有这一条，可能构建产物不同步。</p>'; return; }
      渲染详情(b);
    } catch (err) {
      详情.innerHTML = `<p class="详载入">示例索引加载失败：${esc(err.message)}</p>`;
    }
  });

  function 渲染详情(b) {
    const 导出名 = (b.导出 || [b.名称])[0];
    const 入参 = (b.输入 || []).map(i => {
      const t = i.类型 && typeof i.类型 === 'object' ? `${i.类型.类型}/${i.类型.元素类型 || ''}` : i.类型;
      return `${i.名 || '?'}:${t || '?'}`;
    }).join('、') || '无';
    const 出t = b.输出 && typeof b.输出.类型 === 'object' ? b.输出.类型.类型 : (b.输出 && b.输出.类型);
    const 领域 = b.领域 || '未分类';
    const 语言 = b.语言 || '极快';
    const 可跑 = !!(b.示例 && b.可运行);

    详情.innerHTML = `
      <div class="详头">
        <button type="button" class="详关闭" aria-label="关闭详情">×</button>
        <h2>${esc(b.名称)}</h2>
        <p class="详签名"><code>${esc(导出名)}(${esc(入参)}) → ${esc(出t || '?')}</code></p>
        <p class="详标签">${esc(语言)} · ${esc(领域)}${b.稳定性 ? ' · ' + esc(b.稳定性) : ''} · 层级 ${b.层级 ?? '?'}</p>
        <p class="详描述">${esc(b.描述 || '')}</p>
      </div>
      <div class="详示例">
        <h3>${语言 === '光明' ? '合成示例' : '官方示例'}</h3>
        <pre class="详代码">${esc(b.示例 || '（无示例）')}</pre>
        <div class="详按钮">
          <button type="button" class="详跑" ${可跑 ? '' : 'disabled'}>${可跑 ? '在浏览器里跑' : (b.示例 ? '此积木未通过构建期预跑' : '暂无示例')}</button>
          <a class="详按钮次" href="/台/">在工作台修改这段代码 →</a>
        </div>
        <p class="详状态"></p>
        <pre class="详输出" hidden></pre>
      </div>
    `;
    详情.querySelector('.详关闭').addEventListener('click', () => { 详情.hidden = true; });
    const 跑钮 = 详情.querySelector('.详跑');
    if (跑钮 && 可跑) 跑钮.addEventListener('click', async () => {
      const 输出 = 详情.querySelector('.详输出');
      输出.hidden = false;
      输出.textContent = '执行中…';
      设状态(`准备${语言}解释器（首次约 30 秒）`);
      try {
        const r = await 发消息({ 类型: '跑', 语言, 源码: b.示例 });
        输出.textContent = r.stdout || '(无输出)';
        设状态('✓ 已完成');
      } catch (err) {
        输出.textContent = `[错误] ${err.message}`;
        设状态('执行出错');
      }
    });
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }
})();
