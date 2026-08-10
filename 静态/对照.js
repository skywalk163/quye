// 对照页：四门语言并排跑同一需求，每格独立
// 两段超时：加载阶段（Pyodide 冷启 + 语言包挂载）宽松，执行阶段严格 5 秒。
const 加载超时毫秒 = 180000;
const 执行超时毫秒 = 5000;

let _worker = null;
let _会话id = 0;
const _会话 = new Map();

function 收消息(e) {
  const { 会话id, 类型 } = e.data;
  if (类型 === '进度') {
    document.getElementById('对照状态').textContent = e.data.消息;
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
  return _worker;
}

// terminate 后 Worker 不可复用，丢引用让下次调用重建（Pyodide 会重新加载）
function 弃worker() {
  if (_worker) {
    _worker.terminate();
    _worker = null;
  }
  _会话.clear();
}

function 跑代码(语言, 源码) {
  return new Promise((resolve, reject) => {
    const id = ++_会话id;
    let 定时器 = null;

    const 起表 = (毫秒, 说明) => {
      if (定时器) clearTimeout(定时器);
      定时器 = setTimeout(() => {
        _会话.delete(id);
        弃worker();
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
    取worker().postMessage({ 类型: '跑', 语言, 源码, 会话id: id });
  });
}

// 加载示例集，填充下拉与格子
fetch('/数据/示例集.json')
  .then((r) => r.json())
  .then((集) => {
    const 选择 = document.getElementById('示例选择');
    集.对照示例.forEach((条, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = 条.标题;
      选择.appendChild(opt);
    });
    const 加载 = (i) => {
      const 条 = 集.对照示例[i];
      document.querySelectorAll('.对照-格').forEach((格) => {
        格.querySelector('textarea').value = 条[格.dataset.语言] || '// 该语言暂无示例';
        格.querySelector('.结果').textContent = '';
      });
    };
    选择.addEventListener('change', (e) => 加载(Number(e.target.value)));
    if (集.对照示例.length) 加载(0);
  })
  .catch((e) => {
    document.getElementById('对照状态').textContent = `示例集加载失败：${e.message}`;
  });

document.querySelectorAll('.对照-格').forEach((格) => {
  格.querySelector('.跑').addEventListener('click', async () => {
    const 语言 = 格.dataset.语言;
    const 结果 = 格.querySelector('.结果');
    结果.textContent = '执行中...';
    try {
      const r = await 跑代码(语言, 格.querySelector('textarea').value);
      结果.textContent = r.stdout + (r.返回值 ? `\n返回值：${r.返回值}` : '');
    } catch (e) {
      结果.textContent = `[错误] ${e.message}`;
    }
  });
});
