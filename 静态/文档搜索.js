// 文档区前端搜索：加载构建期生成的 /数据/文档搜索索引.json，纯子串+分词打分，无第三方库。
(function () {
  const 框 = document.getElementById('文档搜索框');
  const 结果列 = document.getElementById('文档搜索结果');
  const 分组区 = document.getElementById('文档分组');
  if (!框 || !结果列 || !分组区) return;

  let 索引 = null;
  let 加载中 = null;

  function 取索引() {
    if (索引) return Promise.resolve(索引);
    if (!加载中) {
      加载中 = fetch('/数据/文档搜索索引.json')
        .then((r) => r.json())
        .then((d) => { 索引 = d; return d; })
        .catch(() => { 索引 = []; return 索引; });
    }
    return 加载中;
  }

  // 中文无空格分词：按 2 字滑窗切；英文按空白切。
  function 切词(q) {
    const 词 = [];
    q.split(/\s+/).filter(Boolean).forEach((段) => {
      if (/^[\x00-\x7F]+$/.test(段)) { 词.push(段.toLowerCase()); return; }
      if (段.length <= 2) { 词.push(段); return; }
      for (let i = 0; i < 段.length - 1; i++) 词.push(段.slice(i, i + 2));
    });
    return 词;
  }

  function 打分(条, 词组, 原查询) {
    const 标题 = 条.标题.toLowerCase();
    const 正文 = 条.正文.toLowerCase();
    let 分 = 0;
    if (标题.includes(原查询)) 分 += 100;
    if (正文.includes(原查询)) 分 += 20;
    词组.forEach((w) => {
      if (标题.includes(w)) 分 += 10;
      if (正文.includes(w)) 分 += 1;
    });
    return 分;
  }

  // 取正文中命中处前后文，用于结果摘要
  function 摘要(条, 原查询) {
    const i = 条.正文.toLowerCase().indexOf(原查询);
    if (i < 0) return 条.正文.slice(0, 80);
    return (i > 20 ? '…' : '') + 条.正文.slice(Math.max(0, i - 20), i + 60);
  }

  function 渲染(命中, 原查询) {
    结果列.textContent = '';
    if (!命中.length) {
      const li = document.createElement('li');
      li.className = '无结果';
      li.textContent = '没有匹配的文档';
      结果列.appendChild(li);
      return;
    }
    命中.slice(0, 10).forEach((条) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = `/文档/${encodeURIComponent(条.slug)}/`;
      a.textContent = 条.标题;
      const 小 = document.createElement('small');
      小.textContent = ` ${条.分组} · ${摘要(条, 原查询)}`;
      li.appendChild(a);
      li.appendChild(小);
      结果列.appendChild(li);
    });
  }

  let 定时器 = null;
  框.addEventListener('input', () => {
    clearTimeout(定时器);
    定时器 = setTimeout(async () => {
      const q = 框.value.trim().toLowerCase();
      if (!q) {
        结果列.hidden = true;
        分组区.hidden = false;
        return;
      }
      const 全部 = await 取索引();
      const 词组 = 切词(q);
      const 命中 = 全部
        .map((条) => ({ 条, 分: 打分(条, 词组, q) }))
        .filter((x) => x.分 > 0)
        .sort((a, b) => b.分 - a.分)
        .map((x) => x.条);
      渲染(命中, q);
      结果列.hidden = false;
      分组区.hidden = true;
    }, 150);
  });
})();
