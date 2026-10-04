/* PlayAtlas visual shell. No network, fonts, images, or paid APIs are required. */
(function () {
  'use strict';

  const SAMPLE_IDS = new Set(['gomoku', 'minesweeper', 'klondike', 'snake', 'oware', 'carrom']);
  const PALETTE = {
    bg: '#111b32', ink: '#eff3ff', muted: '#93a1be', dim: '#5e6b86', accent: '#ffb454', mint: '#77e2c1', blue: '#75a7ff', coral: '#ff7a70'
  };
  const FALLBACK_GAMES = [
    ['gomoku','五子棋','GOMOKU','棋盘对战','经典棋盘落子，先成五子者胜。','2 人','电脑对战 · 本地双人','中国 / 东亚','playable'],
    ['minesweeper','扫雷','MINESWEEPER','经典轻游戏','以数字推理安全揭开每一格。','1 人','单人放松 · 触屏友好','全球经典','playable'],
    ['klondike','克朗代克接龙','KLONDIKE','纸牌休闲','把四种花色从 A 到 K 依次整理。','1 人','单人放松','欧美纸牌传统','playable'],
    ['snake','贪吃蛇','SNAKE','经典轻游戏','在边界与节奏之间找到最长路线。','1 人','单人放松 · 触屏友好','全球街机','playable'],
    ['oware','Oware','OWARE','世界传统','播撒种子、计算收获，来自曼卡拉家族。','2 人','电脑对战 · 本地双人','西非 / 加勒比','playable'],
    ['carrom','卡罗姆','CARROM','桌面运动','轻推、反弹、落袋，掌握桌面几何。','2–4 人','本地双人 · 触屏友好','南亚','playable'],
    ['breakout','打砖块','BREAKOUT','经典轻游戏','控制挡板，让每一次反弹都有去处。','1 人','单人放松','街机传统','planned'],
    ['sudoku','数独','SUDOKU','经典轻游戏','每行、每列、每宫都只留下一个答案。','1 人','单人放松 · 触屏友好','全球益智','planned'],
    ['2048','2048','2048','经典轻游戏','合并相同数字，追寻 2048。','1 人','单人放松 · 触屏友好','数字益智','planned'],
    ['sokoban','推箱子','SOKOBAN','经典轻游戏','先想好退路，再把箱子推到目标。','1 人','单人放松','日本 / 全球','planned'],
    ['sliding-15','15 拼图','15 PUZZLE','经典轻游戏','只移动相邻方块，恢复完整顺序。','1 人','单人放松 · 触屏友好','欧美益智','planned'],
    ['link-link','连连看','LINK LINK','经典轻游戏','用不超过两次转弯的路径配对。','1 人','单人放松 · 触屏友好','东亚益智','planned'],
    ['reversi','黑白棋','REVERSI','棋盘对战','夹住对手的棋子，翻转局势。','2 人','电脑对战 · 本地双人','日本 / 国际','planned'],
    ['xiangqi','中国象棋','XIANGQI','棋盘对战','炮隔山，马别腿，将帅不照面。','2 人','电脑对战 · 本地双人','中国','planned'],
    ['connect-four','四子连线','CONNECT FOUR','棋盘对战','在重力棋盘上率先连接四子。','2 人','电脑对战 · 本地双人','美国 / 全球','planned'],
    ['dots-boxes','点格棋','DOTS & BOXES','棋盘对战','画下最后一条边，收下这一格。','2 人','电脑对战 · 本地双人','欧洲 / 全球','planned'],
    ['english-draughts','英式跳棋','DRAUGHTS','棋盘对战','强制吃子，抵达底线升王。','2 人','电脑对战 · 本地双人','英国 / 国际','planned'],
    ['nine-men-morris','九子棋','NINE MEN’S MORRIS','棋盘对战','成磨、吃子、封锁，完成三阶段对局。','2 人','电脑对战 · 本地双人','欧洲','planned'],
    ['chess','国际象棋','CHESS','棋盘对战','将军、易位、升变与和棋判定。','2 人','电脑对战 · 本地双人','国际','planned'],
    ['spider','蜘蛛接龙','SPIDER','纸牌休闲','按花色收拢八组完整序列。','1 人','单人放松','欧美纸牌传统','planned'],
    ['freecell','空当接龙','FREECELL','纸牌休闲','四个空位，所有牌都在桌面上。','1 人','单人放松','欧美纸牌传统','planned'],
    ['pyramid','金字塔接龙','PYRAMID','纸牌休闲','配对总和为 13，逐层清空牌面。','1 人','单人放松','欧美纸牌传统','planned'],
    ['hearts','红心大战','HEARTS','纸牌休闲','避开红心与黑桃皇后，分数最低者胜。','3–4 人','电脑对战 · 本地多人','欧美纸牌传统','planned'],
    ['gin-rummy','金拉米','GIN RUMMY','纸牌休闲','组成顺子与刻子，合理停牌。','2 人','电脑对战 · 本地双人','美国 / 欧洲','planned'],
    ['go-fish','Go Fish','GO FISH','纸牌休闲','询问牌面，收集完整四张。','2–6 人','电脑对战 · 本地多人','欧美纸牌传统','planned'],
    ['crazy-eights','疯狂八','CRAZY EIGHTS','纸牌休闲','用花色与点数接牌，八可改变花色。','2–7 人','电脑对战 · 本地多人','欧美纸牌传统','planned'],
    ['sungka','Sungka','SUNGKA','世界传统','沿着播棋轨道轮转，收集更多种子。','2 人','电脑对战 · 本地双人','菲律宾','planned'],
    ['yut-nori','Yut Nori · 掷柶','YUT NORI','世界传统','掷柶、走棋、合马，先到终点。','2–4 人','电脑对战 · 本地多人','韩国','planned'],
    ['baghchal','Baghchal · 虎羊棋','BAGHCHAL','世界传统','虎方捕获，羊方围堵，信息完全公开。','2 人','电脑对战 · 本地双人','尼泊尔','planned'],
    ['scopa','Scopa','SCOPA','世界传统','用牌面点数清扫桌面牌。','2–4 人','电脑对战 · 本地多人','意大利','planned'],
    ['briscola','Briscola','BRISCOLA','世界传统','记住王牌花色，赢下关键墩。','2–5 人','电脑对战 · 本地多人','意大利','planned'],
    ['mu-torere','Mū tōrere','MŪ TŌRERE','世界传统','在八瓣棋盘上移动并封锁。','2 人','电脑对战 · 本地双人','新西兰毛利','planned'],
    ['fanorona','Fanorona','FANORONA','世界传统','进退皆可取，连续吃子改变局面。','2 人','电脑对战 · 本地双人','马达加斯加','planned'],
    ['air-hockey','桌上冰球','AIR HOCKEY','桌面运动','快速碰撞，先得目标分数。','2 人','本地双人 · 触屏友好','桌面运动','planned'],
    ['bowling','保龄球','BOWLING','桌面运动','完整十轮计分，控制线路与力度。','1–2 人','单人放松 · 本地双人','全球运动','planned'],
    ['mini-golf','迷你高尔夫','MINI GOLF','桌面运动','九洞、障碍、角度与每一杆。','1–4 人','单人放松 · 本地多人','全球运动','planned']
  ].map((g, i) => ({ id:g[0], title:g[1], title_en:g[2], family:g[3], description:g[4], players:g[5], modes:g[6], region:g[7], status:g[8], order:i }));

  let games = FALLBACK_GAMES.slice();
  let activeFamily = '全部';
  let activeMode = 'all';
  let searchTerm = '';
  let sortMode = '推荐';
  let selectedGame = null;
  let favoriteIds = new Set();
  try { favoriteIds = new Set(JSON.parse(localStorage.getItem('playatlas_favorites') || '[]')); } catch (_) { /* storage can be disabled in private/file previews */ }
  const $ = (q, root=document) => root.querySelector(q);
  const $$ = (q, root=document) => Array.from(root.querySelectorAll(q));
  const grid = $('#game-grid');

  function familyName(f) { return ({ arcade:'经典轻游戏', classic:'经典轻游戏', puzzle:'经典轻游戏', board:'棋盘对战', cards:'纸牌休闲', traditional:'世界传统', table_physics:'桌面运动', '桌面运动':'桌面运动', '世界传统':'世界传统', '棋盘对战':'棋盘对战', '纸牌休闲':'纸牌休闲', '经典轻游戏':'经典轻游戏' })[f] || f || '未分类'; }
  function modeName(m) { return ({ solo:'单人放松', ai:'电脑对战', local:'本地双人', local_multiplayer:'本地多人', challenge:'挑战模式', touch:'触屏友好', keyboard:'键盘', mouse:'鼠标', gamepad:'手柄' })[m] || m; }

  function normalizeCatalog(raw) {
    const list = Array.isArray(raw) ? raw : (raw && (raw.games || raw.catalog || raw.entries));
    if (!Array.isArray(list) || !list.length) return null;
    return list.map((g, i) => ({
      id: String(g.id || g.game_id || `game-${i}`), title: g.title_zh || g.title || g.name || `游戏 ${i + 1}`,
      title_en: g.title_en || g.english_name || String(g.id || '').toUpperCase(), family: familyName(String(g.game_family || g.family || '未分类')),
      description: g.description || g.summary || '规则清晰、可离线游玩的世界游戏。', players: typeof g.players === 'object' ? `${g.players.min || 1}–${g.players.max || g.players.min || 1} 人` : (g.players || g.supported_players || '—'),
      modes: Array.isArray(g.supported_modes) ? g.supported_modes.map(modeName).join(' · ') : (g.modes || '单人放松'), region: g.region || g.countries || '—',
      status: /playable|implemented|ready|已实现|可玩/i.test(String(g.status || '')) ? 'playable' : (SAMPLE_IDS.has(String(g.id || '')) && /in_development|开发中|待验证/i.test(String(g.status || '')) ? 'preview' : (g.status || 'planned')), order: i,
      ruleset: g.ruleset_version || g.rules_version || '待核验', sources: g.content_sources || g.sources || []
    }));
  }

  async function loadCatalog() {
    try {
      const res = await fetch('../data/games/GAME_CATALOG.json', { cache: 'no-store' });
      if (res.ok) { const normalized = normalizeCatalog(await res.json()); if (normalized) games = normalized; }
    } catch (_) { /* local preview deliberately falls back to an embedded catalogue */ }
    $('#catalog-count').textContent = games.length;
    $('#all-count').textContent = games.length;
    render();
  }

  function modeMatches(g) {
    const text = `${g.modes || ''} ${g.players || ''}`;
    if (activeMode === 'solo') return /单人|solo/i.test(text) && !/仅多人|多人真人/i.test(text);
    if (activeMode === 'ai') return /电脑|AI|对战/i.test(text);
    if (activeMode === 'local') return /本地|同屏/i.test(text);
    if (activeMode === 'touch') return /触屏|touch/i.test(text);
    return true;
  }
  function filteredGames() {
    let list = games.filter(g => activeFamily === '全部' || String(g.family).includes(activeFamily));
    if (activeMode !== 'all') list = list.filter(modeMatches);
    if (searchTerm) { const q = searchTerm.toLowerCase(); list = list.filter(g => `${g.title} ${g.title_en} ${g.id} ${g.family} ${g.region} ${g.description}`.toLowerCase().includes(q)); }
    if (sortMode === '名称') list.sort((a,b)=>a.title.localeCompare(b.title,'zh'));
    else if (sortMode === '可玩优先') list.sort((a,b)=>(Number(['playable','preview'].includes(b.status)) - Number(['playable','preview'].includes(a.status))) || a.order-b.order);
    else list.sort((a,b)=>a.order-b.order);
    return list;
  }

  function safeText(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }
  function render() {
    const list = filteredGames();
    grid.innerHTML = '';
    list.forEach((game, idx) => grid.appendChild(createCard(game, idx)));
    $('#result-count').textContent = `${list.length} 款游戏`;
    $('#empty-state').hidden = list.length !== 0;
    $$('.filter-chip').forEach(b => b.classList.toggle('active', b.dataset.filter === activeFamily));
    $$('.sub-filter').forEach(b => b.classList.toggle('active', b.dataset.mode === activeMode));
  }

  function createCard(game, index) {
    const article = document.createElement('article'); article.className = 'game-card'; article.tabIndex = 0;
    const stateLabel = game.status === 'playable' ? '已验收可玩' : (game.status === 'preview' ? '互动样板' : (/implemented|ready|已实现/i.test(game.status) ? '可玩' : '开发路线'));
    article.innerHTML = `<div class="card-art"><canvas width="420" height="250"></canvas><span class="card-badge">${safeText(game.family)}</span><button class="card-fav ${favoriteIds.has(game.id) ? 'active' : ''}" aria-label="收藏">${favoriteIds.has(game.id) ? '★' : '☆'}</button></div><div class="card-copy"><div class="card-title-row"><h3 class="card-title">${safeText(game.title)}</h3><span class="card-en">${safeText(game.title_en)}</span></div><p class="card-desc">${safeText(game.description)}</p><div class="card-footer"><span class="card-tags"><span class="card-tag">${safeText(game.players)}</span><span class="card-tag">${safeText(modeLabel(game))}</span></span><span class="card-state ${game.status === 'playable' ? '' : 'planned'}">${stateLabel}</span></div></div>`;
    drawPreview($('canvas', article).getContext('2d'), game.id, index);
    $('.card-fav', article).addEventListener('click', e => { e.stopPropagation(); toggleFavorite(game, e.currentTarget); });
    article.addEventListener('click', () => openDetails(game));
    article.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetails(game); } });
    return article;
  }
  function modeLabel(g) { if (/电脑/.test(g.modes || '')) return '电脑对战'; if (/本地/.test(g.modes || '')) return '本地多人'; return '单人'; }
  function toggleFavorite(game, btn) { if (favoriteIds.has(game.id)) { favoriteIds.delete(game.id); btn.classList.remove('active'); btn.textContent = '☆'; toast('已从收藏移除'); } else { favoriteIds.add(game.id); btn.classList.add('active'); btn.textContent = '★'; toast('已加入收藏'); } try { localStorage.setItem('playatlas_favorites', JSON.stringify([...favoriteIds])); } catch (_) {} }

  function drawPreview(ctx, id, seed) {
    const w = ctx.canvas.width, h = ctx.canvas.height; ctx.clearRect(0,0,w,h);
    const hue = (seed * 41) % 360; const grad = ctx.createLinearGradient(0,0,w,h); grad.addColorStop(0, `hsl(${hue}, 30%, 24%)`); grad.addColorStop(1, `hsl(${(hue+45)%360}, 35%, 13%)`); ctx.fillStyle = grad; ctx.fillRect(0,0,w,h);
    ctx.globalAlpha = .16; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; for (let x=0;x<w;x+=28){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+h,h);ctx.stroke();} ctx.globalAlpha=1;
    if (id === 'gomoku' || id === 'reversi' || id === 'xiangqi') drawBoard(ctx, id);
    else if (id === 'minesweeper' || id === 'sudoku' || id === 'sliding-15') drawGridPuzzle(ctx, id);
    else if (id === 'snake') drawSnake(ctx, 0, 0, false);
    else if (id === 'oware' || id === 'sungka') drawMancala(ctx, id === 'sungka');
    else if (id === 'carrom' || id === 'air-hockey') drawTable(ctx, id);
    else if (id === 'klondike' || id === 'spider' || id === 'freecell') drawCards(ctx, id);
    else drawAbstract(ctx, id, hue);
  }
  function roundRect(ctx,x,y,w,h,r){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
  function drawBoard(ctx,id){ const x=70,y=22,s=19,n=id==='xiangqi'?9:11; ctx.fillStyle='#9d704b';roundRect(ctx,x-12,y-10,s*(n-1)+24,s*(n-1)+24,9);ctx.fill();ctx.strokeStyle='rgba(47,28,18,.62)';ctx.lineWidth=1; for(let i=0;i<n;i++){ctx.beginPath();ctx.moveTo(x,y+i*s);ctx.lineTo(x+(n-1)*s,y+i*s);ctx.stroke();ctx.beginPath();ctx.moveTo(x+i*s,y);ctx.lineTo(x+i*s,y+(n-1)*s);ctx.stroke();} [['#171922',4,4],['#eee8dc',6,6],['#171922',7,5],['#eee8dc',2,8],['#171922',8,8]].forEach(a=>{ctx.fillStyle=a[0];ctx.beginPath();ctx.arc(x+a[1]*s,y+a[2]*s,7,0,Math.PI*2);ctx.fill();}); }
  function drawGridPuzzle(ctx,id){ const n=7,x=72,y=19,s=26; for(let r=0;r<n;r++)for(let c=0;c<n;c++){ctx.fillStyle=(r+c)%2?'#213653':'#1a2c47';roundRect(ctx,x+c*s,y+r*s,s-2,s-2,4);ctx.fill();if(id==='minesweeper'&&(r*7+c)%11===3){ctx.fillStyle='#ff7a70';ctx.beginPath();ctx.arc(x+c*s+12,y+r*s+12,5,0,Math.PI*2);ctx.fill();}else if(id==='sudoku'&&(r+c)%3===0){ctx.fillStyle='#77e2c1';ctx.font='bold 13px sans-serif';ctx.fillText((r*3+c)%9+1,x+c*s+9,y+r*s+18);} } }
  function drawSnake(ctx, ox=0, oy=0, detail=true){const x=82+ox,y=38+oy,s=18;ctx.strokeStyle='rgba(119,226,193,.22)';ctx.lineWidth=1;for(let i=0;i<10;i++){ctx.beginPath();ctx.moveTo(x+i*s,y);ctx.lineTo(x+i*s,y+150);ctx.stroke();}for(let i=0;i<9;i++){ctx.beginPath();ctx.moveTo(x,y+i*s);ctx.lineTo(x+180,y+i*s);ctx.stroke();}const body=[[1,5],[2,5],[3,5],[3,4],[4,4],[5,4],[5,3],[6,3]];body.forEach((p,i)=>{ctx.fillStyle=i===body.length-1?'#ffb454':'#77e2c1';roundRect(ctx,x+p[0]*s+2,y+p[1]*s+2,s-4,s-4,4);ctx.fill();});ctx.fillStyle='#ff7a70';ctx.beginPath();ctx.arc(x+8*s,y+7*s,5,0,Math.PI*2);ctx.fill(); }
  function drawMancala(ctx,small){const x=38,y=49,w=342,h=90;ctx.fillStyle='#85563c';roundRect(ctx,x,y,w,h,42);ctx.fill();for(let r=0;r<2;r++)for(let i=0;i<6;i++){const px=x+76+i*42,py=y+26+r*39;ctx.fillStyle='#3a241f';ctx.beginPath();ctx.ellipse(px,py,16,12,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#f2c171';for(let k=0;k<((i+r)%4+2);k++){ctx.beginPath();ctx.arc(px-6+k*4,py+(k%2)*3,3,0,Math.PI*2);ctx.fill();}}ctx.fillStyle='#342019';ctx.beginPath();ctx.ellipse(x+27,y+45,16,29,0,0,Math.PI*2);ctx.ellipse(x+w-27,y+45,16,29,0,0,Math.PI*2);ctx.fill();}
  function drawCards(ctx,id){const x=74,y=26;for(let i=0;i<6;i++){ctx.save();ctx.translate(x+i*38,y+(i%2)*10);ctx.rotate((i-2.5)*.045);ctx.fillStyle=i%2?'#e7e2d8':'#c3545f';roundRect(ctx,0,0,57,82,6);ctx.fill();ctx.fillStyle=i%2?'#263c61':'#fff1e8';ctx.font='bold 20px serif';ctx.fillText(['A','4','7','J','Q','K'][i],10,27);ctx.font='18px serif';ctx.fillText(i%2?'♣':'♥',29,59);ctx.restore();}ctx.fillStyle='#77e2c1';ctx.font='10px sans-serif';ctx.fillText(id==='klondike'?'RED / BLACK · BUILD DOWN':'SORT BY SUIT',74,144);}
  function drawTable(ctx,id){ctx.fillStyle='#23615d';roundRect(ctx,52,21,316,137,16);ctx.fill();ctx.strokeStyle='rgba(255,255,255,.22)';ctx.stroke();ctx.fillStyle='#d4b48a';ctx.beginPath();ctx.arc(210,90,18,0,Math.PI*2);ctx.fill();ctx.fillStyle='#f5dcae';ctx.beginPath();ctx.arc(id==='carrom'?115:120,90,9,0,Math.PI*2);ctx.fill();ctx.fillStyle='#121729';ctx.beginPath();ctx.arc(300,75,8,0,Math.PI*2);ctx.fill();ctx.strokeStyle='rgba(255,255,255,.23)';ctx.setLineDash([4,5]);ctx.beginPath();ctx.moveTo(80,90);ctx.lineTo(340,90);ctx.stroke();ctx.setLineDash([]);}
  function drawAbstract(ctx,id,hue){ctx.save();ctx.translate(210,88);ctx.rotate(-.13);for(let i=0;i<9;i++){ctx.fillStyle=`hsla(${(hue+i*17)%360},70%,${55+i*3}%,.8)`;roundRect(ctx,-112+i*26,-38+(i%2)*16,51,56,10);ctx.fill();}ctx.restore();ctx.fillStyle='rgba(239,243,255,.7)';ctx.font='600 11px sans-serif';ctx.fillText(String(id).toUpperCase(),20,150);}

  function openDetails(game) {
    selectedGame = game; $('#modal-title').textContent = game.title; $('#modal-family').textContent = game.family; $('#modal-kicker').textContent = game.status === 'playable' ? 'PLAYABLE SAMPLE · OFFLINE' : (game.status === 'preview' ? 'INTERACTIVE PREVIEW · NOT YET ACCEPTED' : 'ROADMAP ENTRY'); $('#modal-description').textContent = game.description;
    $('#detail-canvas').getContext('2d').clearRect(0,0,700,280); drawPreview($('#detail-canvas').getContext('2d'), game.id, game.order + 2);
    $('#modal-meta').innerHTML = [['人数',game.players],['模式',game.modes],['地区',game.region],['规则版本',game.ruleset || (game.status==='playable'?'默认规则':'待核验')]].map(m=>`<div class="meta-item"><span>${safeText(m[0])}</span><b>${safeText(m[1])}</b></div>`).join('');
    $$('.modal-tab').forEach(b=>b.classList.toggle('active', b.dataset.panel === 'overview')); showModalPanel('overview'); $('#modal-favorite').textContent = favoriteIds.has(game.id) ? '★ 已收藏' : '☆ 收藏'; $('#modal-favorite').classList.toggle('active', favoriteIds.has(game.id)); $('#modal-backdrop').hidden = false; document.body.style.overflow='hidden';
  }
  function showModalPanel(panel) { const g=selectedGame||FALLBACK_GAMES[0]; const content={overview:`<strong>${g.status==='playable'?'现在就可以开始。':(g.status==='preview'?'这里是可操作的交互样板。':'正在路线图中。')}</strong><br>支持 ${safeText(g.modes)}。${g.status==='preview'?'样板不会被统计为正式可玩，待规则、存档和人工验收完成后再转为可玩。':'正式内容包状态清晰区分可玩与待开发。'}`,tutorial:`了解目标 → 看一次关键操作 → 亲手完成。<br><strong>教程入口：</strong>第一局会逐步解释非法操作、轮次与结算。教程进度可随时重置。`,rules:`<strong>默认规则：</strong>${safeText(g.ruleset || '规则资料核验中')}<br><strong>资料状态：</strong>${g.status==='playable'?'已绑定本地规则引擎与样板验收。':(g.status==='preview'?'交互预览，完整规则验收未完成。':'待完成规则核验，不计入可玩数量。')}`}; $('#modal-panel').innerHTML=content[panel]||content.overview; }
  function closeModal(){ $('#modal-backdrop').hidden=true; document.body.style.overflow=''; }
  function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(window.__toastTimer);window.__toastTimer=setTimeout(()=>el.classList.remove('show'),2200);}

  function openPlayable(game) {
    if (!SAMPLE_IDS.has(game.id) || !['playable','preview'].includes(game.status)) { toast('该游戏尚未进入可玩内容包，不会伪装成已完成。'); return; }
    closeModal(); let backdrop=$('#play-backdrop'); if(!backdrop){backdrop=document.createElement('div');backdrop.id='play-backdrop';backdrop.className='modal-backdrop';backdrop.innerHTML='<section class="play-modal" role="dialog" aria-modal="true"><div class="play-header"><div><span class="modal-kicker">INTERACTIVE SAMPLE</span><h2 id="play-title"></h2></div><button class="modal-close" id="play-close">×</button></div><div class="play-stage"><canvas id="play-canvas" width="720" height="440" tabindex="0"></canvas><div id="play-status" class="play-status"></div></div><div class="play-controls" id="play-controls"></div><div class="play-note" id="play-note"></div></section>';document.body.appendChild(backdrop);$('#play-close').addEventListener('click',()=>closePlay());}
    backdrop.hidden=false; $('#play-title').textContent=game.title; startMiniGame(game, $('#play-canvas'), $('#play-controls'), $('#play-status'), $('#play-note'));
  }

  function closePlay() { if (activeMiniCleanup) { activeMiniCleanup(); activeMiniCleanup = null; } const p=$('#play-backdrop'); if (p) p.remove(); }

  let activeMiniCleanup = null;
  function startMiniGame(game, canvas, controls, status, note) { if(activeMiniCleanup) activeMiniCleanup(); controls.innerHTML=''; status.textContent=''; note.textContent=''; const ctx=canvas.getContext('2d'); const cleanup=MINI_GAMES[game.id]?.(ctx,canvas,controls,status,note); activeMiniCleanup=cleanup||null; }

  const MINI_GAMES = {
    gomoku(ctx,c,controls,status,note){let b=Array.from({length:15},()=>Array(15).fill(0)),turn=1,over=false;const reset=()=>{b=Array.from({length:15},()=>Array(15).fill(0));turn=1;over=false;draw();status.textContent='你的回合 · 点击棋盘落子';};function draw(){ctx.fillStyle='#825b3e';ctx.fillRect(0,0,c.width,c.height);const gap=26,ox=170,oy=32;ctx.strokeStyle='rgba(39,23,15,.75)';for(let i=0;i<15;i++){ctx.beginPath();ctx.moveTo(ox,oy+i*gap);ctx.lineTo(ox+14*gap,oy+i*gap);ctx.stroke();ctx.beginPath();ctx.moveTo(ox+i*gap,oy);ctx.lineTo(ox+i*gap,oy+14*gap);ctx.stroke();}for(let r=0;r<15;r++)for(let col=0;col<15;col++)if(b[r][col]){ctx.fillStyle=b[r][col]===1?'#171a22':'#f1eadc';ctx.beginPath();ctx.arc(ox+col*gap,oy+r*gap,10,0,Math.PI*2);ctx.fill();}}function win(r,col,p){let dirs=[[1,0],[0,1],[1,1],[1,-1]];return dirs.some(([dr,dc])=>{let n=1;for(let q=1;q<5;q++){const rr=r+dr*q,cc=col+dc*q;if(rr>=0&&rr<15&&cc>=0&&cc<15&&b[rr][cc]===p)n++;else break;}for(let q=1;q<5;q++){const rr=r-dr*q,cc=col-dc*q;if(rr>=0&&rr<15&&cc>=0&&cc<15&&b[rr][cc]===p)n++;else break;}return n>=5;});}function click(e){if(over)return;const q=c.getBoundingClientRect(),col=Math.round(((e.clientX-q.left)*c.width/q.width-170)/26),row=Math.round(((e.clientY-q.top)*c.height/q.height-32)/26);if(row<0||row>14||col<0||col>14||b[row][col])return;b[row][col]=1;draw();if(win(row,col,1)){over=true;status.textContent='你连成五子，胜利！';return;}turn=2;status.textContent='电脑思考中…';setTimeout(()=>{if(over)return;let opts=[];for(let r=0;r<15;r++)for(let cc=0;cc<15;cc++)if(!b[r][cc]){let near=false;for(let dr=-1;dr<=1;dr++)for(let dc=-1;dc<=1;dc++)if(b[r+dr]?.[cc+dc])near=true;if(near)opts.push([r,cc]);}const pick=opts[Math.floor(Math.random()*opts.length)]||[7,7];b[pick[0]][pick[1]]=2;draw();if(win(pick[0],pick[1],2)){over=true;status.textContent='电脑连成五子，本局结束';}else{turn=1;status.textContent='你的回合 · 点击棋盘落子';}},240);}c.addEventListener('click',click);controls.innerHTML='<button class="primary-btn mini-reset">重新开始</button>';$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：15×15 棋盘、落子与基础胜负判断。完整规则版本以正式模块为准。';reset();return()=>c.removeEventListener('click',click);},
    minesweeper(ctx,c,controls,status,note){const n=9,cell=38,ox=188,oy=30,mines=new Set([4,17,29,51,65,77,8,43]);let open=new Set(),flags=new Set(),over=false;function count(i){let r=Math.floor(i/n),col=i%n,k=0;for(let dr=-1;dr<=1;dr++)for(let dc=-1;dc<=1;dc++)if(mines.has((r+dr)*n+col+dc))k++;return k;}function draw(){ctx.fillStyle='#172541';ctx.fillRect(0,0,c.width,c.height);for(let r=0;r<n;r++)for(let col=0;col<n;col++){const i=r*n+col,shown=open.has(i),flag=flags.has(i);ctx.fillStyle=shown?'#29435f':'#1b2c49';ctx.fillRect(ox+col*cell,oy+r*cell,cell-2,cell-2);if(flag){ctx.fillStyle='#ff7a70';ctx.font='20px sans-serif';ctx.fillText('⚑',ox+col*cell+9,oy+r*cell+27);}else if(shown){if(mines.has(i)){ctx.fillStyle='#ff7a70';ctx.beginPath();ctx.arc(ox+col*cell+18,oy+r*cell+18,8,0,Math.PI*2);ctx.fill();}else{const v=count(i);if(v){ctx.fillStyle=['#77e2c1','#75a7ff','#ffb454','#ff7a70'][Math.min(v-1,3)];ctx.font='bold 17px sans-serif';ctx.fillText(v,ox+col*cell+14,oy+r*cell+25);}}}}}function reveal(i){if(over||flags.has(i)||open.has(i))return;if(mines.has(i)){open.add(i);over=true;status.textContent='踩到地雷，本局结束';draw();return;}open.add(i);if(count(i)===0){const r=Math.floor(i/n),col=i%n;for(let dr=-1;dr<=1;dr++)for(let dc=-1;dc<=1;dc++){const rr=r+dr,cc=col+dc;if(rr>=0&&rr<n&&cc>=0&&cc<n)reveal(rr*n+cc);}}const safe=n*n-mines.size;if(open.size>=safe){over=true;status.textContent='清理完成，胜利！';}draw();}function click(e){const q=c.getBoundingClientRect(),x=(e.clientX-q.left)*c.width/q.width,y=(e.clientY-q.top)*c.height/q.height,col=Math.floor((x-ox)/cell),r=Math.floor((y-oy)/cell);if(r<0||r>=n||col<0||col>=n)return;reveal(r*n+col);}function context(e){e.preventDefault();const q=c.getBoundingClientRect(),x=(e.clientX-q.left)*c.width/q.width,y=(e.clientY-q.top)*c.height/q.height,col=Math.floor((x-ox)/cell),r=Math.floor((y-oy)/cell),i=r*n+col;if(r<0||r>=n||col<0||col>=n||open.has(i)||over)return;flags.has(i)?flags.delete(i):flags.add(i);draw();status.textContent=`已标记 ${flags.size} 格 · 左键揭开`; }function reset(){open=new Set();flags=new Set();over=false;status.textContent='首击安全 · 左键揭开，右键插旗';draw();}c.addEventListener('click',click);c.addEventListener('contextmenu',context);controls.innerHTML='<button class="primary-btn mini-reset">重新开始</button>';$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：首击安全提示、插旗和连锁展开。正式难度与无猜生成状态以规则资料卡为准。';reset();return()=>{c.removeEventListener('click',click);c.removeEventListener('contextmenu',context);};},
    klondike(ctx,c,controls,status,note){let cards=['A','3','5','7','9','J','Q','K'],removed=0;function draw(){ctx.fillStyle='#183c3d';ctx.fillRect(0,0,c.width,c.height);for(let i=0;i<8;i++){const x=86+i*69;ctx.fillStyle=i<removed?'rgba(255,255,255,.08)':'#eee8dc';roundRect(ctx,x,145,57,83,7);ctx.fill();if(i>=removed){ctx.fillStyle=i%2?'#bb5360':'#1f3456';ctx.font='bold 21px serif';ctx.fillText(cards[i],x+13,178);ctx.font='18px serif';ctx.fillText(i%2?'♥':'♣',x+29,207);}}ctx.fillStyle='#d7dce8';ctx.font='12px sans-serif';ctx.fillText('点击任意可见牌，将它送入基础牌堆',205,90);ctx.fillText(`${removed}/8 组牌已整理`,294,260);}function click(e){const q=c.getBoundingClientRect(),x=(e.clientX-q.left)*c.width/q.width,y=(e.clientY-q.top)*c.height/q.height;if(y<135||y>240)return;const i=Math.floor((x-86)/69);if(i>=0&&i<8&&i===removed){removed++;status.textContent=removed===8?'所有示范牌已整理！':'合法移动 · 继续选择下一张';draw();}else status.textContent='这张牌目前不能移动 · 按顺序整理';}function reset(){removed=0;status.textContent='红黑交替 · 点击 A 开始';draw();}c.addEventListener('click',click);controls.innerHTML='<button class="primary-btn mini-reset">重新开始</button>';$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：牌张顺序与合法移动反馈。完整接龙模块将保存牌堆、翻牌和撤销状态。';reset();return()=>c.removeEventListener('click',click);},
    snake(ctx,c,controls,status,note){let snake,dir,food,timer,running=false;const cols=22,rows=12,cell=24,ox=96,oy=66;function spawn(){food=[Math.floor(Math.random()*cols),Math.floor(Math.random()*rows)];}function draw(){ctx.fillStyle='#101c2d';ctx.fillRect(0,0,c.width,c.height);ctx.strokeStyle='rgba(119,226,193,.17)';for(let i=0;i<=cols;i++){ctx.beginPath();ctx.moveTo(ox+i*cell,oy);ctx.lineTo(ox+i*cell,oy+rows*cell);ctx.stroke();}for(let i=0;i<=rows;i++){ctx.beginPath();ctx.moveTo(ox,oy+i*cell);ctx.lineTo(ox+cols*cell,oy+i*cell);ctx.stroke();}snake.forEach((p,i)=>{ctx.fillStyle=i?'#77e2c1':'#ffb454';roundRect(ctx,ox+p[0]*cell+2,oy+p[1]*cell+2,cell-4,cell-4,5);ctx.fill();});ctx.fillStyle='#ff7a70';ctx.beginPath();ctx.arc(ox+food[0]*cell+12,oy+food[1]*cell+12,7,0,Math.PI*2);ctx.fill();}function tick(){const h=[snake[0][0]+dir[0],snake[0][1]+dir[1]],hit=h[0]<0||h[0]>=cols||h[1]<0||h[1]>=rows||snake.some(p=>p[0]===h[0]&&p[1]===h[1]);if(hit){running=false;clearInterval(timer);status.textContent='撞到边界或自己，本局结束';return;}snake.unshift(h);if(h[0]===food[0]&&h[1]===food[1]){spawn();status.textContent=`长度 ${snake.length} · 继续前进`;}else snake.pop();draw();}function reset(){clearInterval(timer);snake=[[5,5],[4,5],[3,5]];dir=[1,0];spawn();running=false;status.textContent='按方向键或下方按钮开始';draw();}function toggle(){if(running){running=false;clearInterval(timer);status.textContent='已暂停';}else{running=true;timer=setInterval(tick,150);status.textContent='前进中 · 方向键转向';}}function key(e){const k=e.key.toLowerCase(),d={arrowup:[0,-1],w:[0,-1],arrowdown:[0,1],s:[0,1],arrowleft:[-1,0],a:[-1,0],arrowright:[1,0],d:[1,0]}[k];if(d&&!(d[0]===-dir[0]&&d[1]===-dir[1])){dir=d;if(!running)toggle();e.preventDefault();}}window.addEventListener('keydown',key);c.addEventListener('click',toggle);controls.innerHTML='<button class="primary-btn mini-toggle">开始 / 暂停</button><button class="ghost-btn mini-reset">重置</button>';$('.mini-toggle',controls).onclick=toggle;$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：键盘方向键 / WASD，点击画布也可暂停。移动端可接入统一触控方向层。';reset();return()=>{clearInterval(timer);window.removeEventListener('keydown',key);};},
    oware(ctx,c,controls,status,note){let pits=Array(12).fill(4),turn=0,score=[0,0],over=false;function draw(){ctx.fillStyle='#6c4936';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#a87951';roundRect(ctx,65,90,590,170,80);ctx.fill();for(let i=0;i<12;i++){const row=i<6?0:1,j=i<6?i:11-i,x=145+j*78,y=row?208:142;ctx.fillStyle='#3c2925';ctx.beginPath();ctx.ellipse(x,y,29,21,0,0,Math.PI*2);ctx.fill();for(let k=0;k<Math.min(pits[i],8);k++){ctx.fillStyle=['#f2c171','#e59458','#77e2c1','#d7dce8'][k%4];ctx.beginPath();ctx.arc(x-12+(k%4)*8,y-5+Math.floor(k/4)*9,4,0,Math.PI*2);ctx.fill();}}ctx.fillStyle='#f2c171';ctx.font='bold 17px sans-serif';ctx.fillText(`你 ${score[0]}`,80,54);ctx.fillStyle='#d7dce8';ctx.fillText(`对手 ${score[1]}`,525,54);}function move(i){if(over||i>5||pits[i]===0)return;let n=pits[i];pits[i]=0;let j=i;while(n--){j=(j+1)%12;pits[j]++;}if(j>=6&&pits[j]>=2&&pits[j]<=3){score[0]+=pits[j];pits[j]=0;}if(score[0]>=25||score[1]>=25){over=true;status.textContent='收获达到 25，回合结束';}else{status.textContent='你播撒了种子 · 继续选择己方坑位';draw();}}function click(e){const q=c.getBoundingClientRect(),x=(e.clientX-q.left)*c.width/q.width;const i=Math.floor((x-112)/78);if(i>=0&&i<6)move(i);}function reset(){pits=Array(12).fill(4);score=[0,0];over=false;status.textContent='点击下排己方坑位播撒';draw();}c.addEventListener('click',click);controls.innerHTML='<button class="primary-btn mini-reset">重新开始</button>';$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：播撒、收获与分数反馈。双方完整回合和额外回合在正式模块中记录。';reset();return()=>c.removeEventListener('click',click);},
    carrom(ctx,c,controls,status,note){let striker={x:360,y:360},disc={x:360,y:230,vx:0,vy:0},drag=false,start=null,anim;function draw(){ctx.fillStyle='#9f754b';ctx.fillRect(110,25,500,390);ctx.fillStyle='#e4c58d';ctx.fillRect(132,47,456,346);ctx.strokeStyle='#7e4c31';ctx.lineWidth=8;ctx.strokeRect(132,47,456,346);[[155,70],[565,70],[155,370],[565,370]].forEach(p=>{ctx.fillStyle='#542c27';ctx.beginPath();ctx.arc(p[0],p[1],13,0,Math.PI*2);ctx.fill();});ctx.fillStyle='#e6575b';ctx.beginPath();ctx.arc(disc.x,disc.y,11,0,Math.PI*2);ctx.fill();ctx.fillStyle='#f4ddae';ctx.beginPath();ctx.arc(striker.x,striker.y,15,0,Math.PI*2);ctx.fill();if(start){ctx.strokeStyle='#77e2c1';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(striker.x,striker.y);ctx.lineTo(start.x,start.y);ctx.stroke();}}function step(){disc.x+=disc.vx;disc.y+=disc.vy;disc.vx*=.985;disc.vy*=.985;if(disc.x<145||disc.x>575)disc.vx*=-.92;if(disc.y<60||disc.y>380)disc.vy*=-.92;if(Math.hypot(disc.vx,disc.vy)<.1){disc.vx=disc.vy=0;cancelAnimationFrame(anim);status.textContent='静止 · 再次拖拽瞄准';}draw();if(disc.vx||disc.vy)anim=requestAnimationFrame(step);}function pos(e){const q=c.getBoundingClientRect();return{x:(e.clientX-q.left)*c.width/q.width,y:(e.clientY-q.top)*c.height/q.height};}function down(e){const p=pos(e);if(Math.hypot(p.x-striker.x,p.y-striker.y)<35){drag=true;start=p;draw();}}function up(e){if(!drag)return;const p=pos(e),dx=striker.x-p.x,dy=striker.y-p.y;drag=false;start=null;disc.x=striker.x;disc.y=striker.y;disc.vx=dx*.08;disc.vy=dy*.08;status.textContent='击球中 · 观察反弹';step();}function reset(){cancelAnimationFrame(anim);disc={x:360,y:230,vx:0,vy:0};striker={x:360,y:360};drag=false;start=null;status.textContent='拖拽白色击球盘，松开出杆';draw();}c.addEventListener('pointerdown',down);c.addEventListener('pointerup',up);controls.innerHTML='<button class="primary-btn mini-reset">重新开始</button>';$('.mini-reset',controls).onclick=reset;note.textContent='互动样板：瞄准、力度、边界反弹与静止判断。正式规则会加入落袋、Queen、犯规与计分。';reset();return()=>{cancelAnimationFrame(anim);c.removeEventListener('pointerdown',down);c.removeEventListener('pointerup',up);};}
  };

  $$('.filter-chip').forEach(b => b.addEventListener('click', () => { activeFamily=b.dataset.filter; render(); }));
  $$('.sub-filter').forEach(b => b.addEventListener('click', () => { activeMode=b.dataset.mode; render(); }));
  $('#search').addEventListener('input', e => { searchTerm=e.target.value.trim(); render(); });
  $('#sort-btn').addEventListener('click', () => { sortMode = sortMode === '推荐' ? '可玩优先' : (sortMode === '可玩优先' ? '名称' : '推荐'); $('#sort-btn').innerHTML=`${sortMode} <span>⌄</span>`; render(); });
  $('#show-all').addEventListener('click', () => { activeFamily='全部'; activeMode='all'; searchTerm=''; $('#search').value=''; render(); window.scrollTo({top:document.querySelector('.library-section').offsetTop-20,behavior:'smooth'}); });
  $('#clear-filters').addEventListener('click', () => { activeFamily='全部';activeMode='all';searchTerm='';$('#search').value='';render(); });
  $('#dismiss-continue').addEventListener('click',()=>$('#continue-card').classList.add('hidden'));
  $('#resume-btn').addEventListener('click',()=>openDetails(games.find(g=>g.id==='gomoku')||games[0])); $('#continue-action').addEventListener('click',()=>openDetails(games.find(g=>g.id==='gomoku')||games[0])); $('#quick-play').addEventListener('click',()=>{const choices=filteredGames().filter(g=>['playable','preview'].includes(g.status));openDetails(choices[Math.floor(Math.random()*choices.length)]||games[0]);});
  $('#open-help').addEventListener('click',()=>toast('搜索 / 筛选 / 打开游戏卡片即可查看规则、教程与状态。')); $('#open-settings').addEventListener('click',()=>toast('设置面板将在核心服务接入后保存字体、音量与无障碍偏好。'));
  $$('[data-close-modal]').forEach(b=>b.addEventListener('click',closeModal)); $('#modal-backdrop').addEventListener('click',e=>{if(e.target.id==='modal-backdrop')closeModal();}); $('#modal-start').addEventListener('click',()=>selectedGame&&openPlayable(selectedGame)); $('#modal-favorite').addEventListener('click',()=>{if(selectedGame){const fake={classList:{toggle(){}},textContent:''};toggleFavorite(selectedGame,fake);$('#modal-favorite').textContent=favoriteIds.has(selectedGame.id)?'★ 已收藏':'☆ 收藏';}}); $$('.modal-tab').forEach(b=>b.addEventListener('click',()=>{$$('.modal-tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');showModalPanel(b.dataset.panel);}));
  document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();$('#search').focus();}if(e.key==='Escape'){closeModal();closePlay();}});
  loadCatalog();
})();
