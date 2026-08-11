// 讨论区：按当前页语言指向对应仓库；偏好判定纯客户端，零外部请求
(function () {
  var KEY = 'quye_讨论区偏好';
  var 仓库 = { 极快: 'jikuai', 段言: 'duan', 光明: 'light', 知行: 'zhixing' };

  var box = document.querySelector('.讨论区');
  var gc = document.getElementById('讨论-gitcode');
  var gh = document.getElementById('讨论-github');
  if (!box || !gc || !gh) return;

  var 语言 = box.getAttribute('data-讨论语言') || '极快';
  var repo = 仓库[语言] || 'jikuai';
  gc.href = 'https://gitcode.com/skywalk163/' + repo + '/issues';
  gh.href = 'https://github.com/skywalk163/' + repo + '/discussions';

  function 偏国内() {
    var langs = navigator.languages || [navigator.language || ''];
    var zhCN = langs.some(function (l) { return /^zh(-CN|-Hans)?$/i.test(l); });
    var tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) {}
    return zhCN || /^Asia\/(Shanghai|Chongqing|Urumqi|Harbin)$/.test(tz);
  }

  // 用户手动选择永远覆盖自动判定
  var 推荐 = localStorage.getItem(KEY) || (偏国内() ? 'gitcode' : 'github');
  (推荐 === 'gitcode' ? gc : gh).classList.add('推荐');

  gc.addEventListener('click', function () { localStorage.setItem(KEY, 'gitcode'); });
  gh.addEventListener('click', function () { localStorage.setItem(KEY, 'github'); });
})();
