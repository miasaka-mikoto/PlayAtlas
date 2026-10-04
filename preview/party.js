(() => {
  'use strict';
  const games = [
    ['tank_battle','🛡️','坦克大战','Tank Battle','2–4 人 · 同屏 / 局域网','原创网格竞技，击中得分，先到 5 分。'],
    ['uno','🟥','UNO','UNO','2–4 人 · 同屏 / 局域网','108 张牌、变色、+4 合法性和玩家视角手牌。'],
    ['upgrade_poker','🃏','升级扑克','Sheng Ji / Upgrade','4 人 · 同屏 / 局域网','两副牌的明确数字改编，固定主牌与跟牌。'],
    ['blackjack','♠️','21点','Blackjack','1–4 人 · 聚会房间','要牌、停牌、加倍；只计本地积分，不下注。'],
    ['prize_reels','🎞️','奖品转盘机','Prize Reels','1 人 · 聚会展示','免费转三格，只得到分数，不含货币。'],
    ['prize_wheel','🎡','幸运积分轮','Prize Wheel','1 人 · 聚会展示','一次点击的免费积分轮，结果可复现。']
  ];
  const grid = document.querySelector('#party-grid');
  let selected = null;
  games.forEach((g, i) => {
    const card = document.createElement('article'); card.className = 'card'; card.dataset.id = g[0]; card.tabIndex = 0;
    card.innerHTML = `<div class="icon">${g[1]}</div><h3>${g[2]}</h3><p>${g[3]} · ${g[5]}</p><div class="tags"><span class="tag">${g[4]}</span><span class="tag dim">协议 v1</span></div>`;
    const pick = () => { document.querySelectorAll('.card').forEach(c => c.classList.remove('selected')); card.classList.add('selected'); selected = g[0]; document.querySelector('#room-game').value = g[0] === 'prize_reels' || g[0] === 'prize_wheel' ? 'uno' : g[0]; };
    card.addEventListener('click', pick); card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
    grid.appendChild(card); if (i === 0) pick();
  });
  const status = document.querySelector('#room-status');
  const chosen = () => document.querySelector('#room-game').value;
  document.querySelector('#select-first').addEventListener('click', () => { document.querySelector('#room-game').focus(); status.innerHTML = '状态：<strong>已选择</strong> · ' + chosen(); });
  document.querySelector('#host-btn').addEventListener('click', () => { status.innerHTML = '状态：<strong>待启动房主</strong> · 请运行 <code>tools/lan_host.py --game ' + chosen() + '</code>'; });
  document.querySelector('#join-btn').addEventListener('click', () => { status.innerHTML = '状态：<strong>待加入</strong> · 本预览不伪造远程房间，请使用已知主机地址。'; });
  document.querySelector('#protocol').addEventListener('click', () => { window.location.href = '../docs/LAN_PROTOCOL.md'; });
})();
