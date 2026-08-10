// 讨论区偏好判定 — 纯客户端，零外部请求
(function() {
  var KEY = 'quye_讨论区偏好';
  var stored = localStorage.getItem(KEY);

  function 偏国内() {
    var langs = navigator.languages || [navigator.language || ''];
    var zhCN = langs.some(function(l) { return /^zh(-CN|-Hans)?$/i.test(l); });
    var tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch(e) {}
    var cnTz = /^Asia\/(Shanghai|Chongqing|Urumqi|Harbin)$/.test(tz);
    return zhCN || cnTz;
  }

  var 推荐 = stored || (偏国内() ? 'gitcode' : 'github');

  var gc = document.getElementById('讨论-gitcode');
  var gh = document.getElementById('讨论-github');
  if (!gc || !gh) return;

  if (推荐 === 'gitcode') {
    gc.classList.add('推荐');
  } else {
    gh.classList.add('推荐');
  }

  gc.addEventListener('click', function() { localStorage.setItem(KEY, 'gitcode'); });
  gh.addEventListener('click', function() { localStorage.setItem(KEY, 'github'); });
})();
