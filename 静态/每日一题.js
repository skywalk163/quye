// 首页「每日一题」：基于日期确定性地从学习清单中选一道。
(function () {
  const 节 = document.getElementById('每日一题');
  const 卡 = document.getElementById('每日一题卡');
  const 语言节 = document.getElementById('每日一题语言');
  const 标题节 = document.getElementById('每日一题标题');
  if (!节 || !卡) return;

  fetch('/数据/学习清单.json')
    .then((r) => r.json())
    .then((清单) => {
      // 将所有关卡展平
      const 全部 = [];
      for (const [语言, 组] of Object.entries(清单)) {
        for (const 条 of 组) 全部.push({ 语言, ...条 });
      }
      if (!全部.length) return;

      // 基于日期的确定性选取（每天同一道）
      const 天 = Math.floor(Date.now() / 86400000);
      const 条 = 全部[天 % 全部.length];

      语言节.textContent = 条.语言;
      标题节.textContent = `${条.序号} · ${条.标题}`;
      卡.href = `/学/${encodeURIComponent(条.语言)}/${encodeURIComponent(条.关卡)}/`;
      节.hidden = false;
    })
    .catch(() => {}); // 无清单时不显示
})();
