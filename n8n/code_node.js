// n8n「Code」節點（Mode：Run Once for All Items）
// 依 email 一人一封，把昨天的錯題依詞性（動詞/名詞/形容詞）分組寄出日誌信。
const rows = $input.all();

// 1) 依 email 聚合同一個人昨天的所有局數
const byUser = {};
for (const item of rows) {
  const d = item.json;
  const email = (d.email || '').trim();
  if (!email) continue; // 沒 email 的人跳過（保險，SQL 其實已過濾）

  if (!byUser[email]) {
    byUser[email] = {
      learner: d.learner || '同學',
      games: 0, correct: 0, rounds: 0, wrongTotal: 0,
      wrongByCat: { '動詞': {}, '名詞': {}, '形容詞': {}, '其他': {} },
    };
  }
  const u = byUser[email];
  u.games   += 1;
  u.correct += Number(d.score) || 0;
  u.rounds  += Number(d.total_rounds) || 0;

  // wrong_words 是 JSON 字串，解析成陣列（容錯：壞掉就當空陣列）
  let wrongs = d.wrong_words;
  if (typeof wrongs === 'string') {
    try { wrongs = JSON.parse(wrongs || '[]'); } catch (e) { wrongs = []; }
  }
  if (!Array.isArray(wrongs)) wrongs = [];

  for (const w of wrongs) {
    const cat = ['動詞', '名詞', '形容詞'].includes(w.category) ? w.category : '其他';
    const key = (w.japanese || '') + '|' + (w.chinese || '');
    u.wrongByCat[cat][key] = (u.wrongByCat[cat][key] || 0) + 1; // 累計出現次數
    u.wrongTotal += 1;
  }
}

// 2) 小工具
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
const CAT_META = {
  '動詞':  { icon: '🏃', color: '#2e86de' },
  '名詞':  { icon: '📦', color: '#8e44ad' },
  '形容詞': { icon: '🎨', color: '#c0392b' },
  '其他':  { icon: '📝', color: '#555555' },
};
function catBlock(cat, wordsObj) {
  const entries = Object.entries(wordsObj);
  if (entries.length === 0) return '';
  const meta = CAT_META[cat];
  const lis = entries.map(([key, count]) => {
    const [jp, zh] = key.split('|');
    const times = count > 1 ? ` <span style="color:#999;">×${count}</span>` : '';
    return `<li style="margin:4px 0;">${esc(jp)}<span style="color:#888;">（${esc(zh)}）</span>${times}</li>`;
  }).join('');
  return `<div style="margin:14px 0;">
    <div style="font-weight:700; color:${meta.color}; font-size:15px; margin-bottom:4px;">
      ${meta.icon} ${cat}（${entries.length} 個）
    </div>
    <ul style="margin:0; padding-left:22px; color:#333; font-size:14px; line-height:1.6;">${lis}</ul>
  </div>`;
}

// 3) 每個人組一封信
const out = [];
for (const email of Object.keys(byUser)) {
  const u = byUser[email];
  const accuracy = u.rounds > 0 ? Math.round((u.correct / u.rounds) * 100) : 0;

  let wrongSection;
  if (u.wrongTotal === 0) {
    wrongSection = `<p style="color:#27ae60; font-weight:700;">🎉 昨天全部答對，沒有錯題，太厲害了！</p>`;
  } else {
    wrongSection =
      catBlock('動詞',  u.wrongByCat['動詞']) +
      catBlock('名詞',  u.wrongByCat['名詞']) +
      catBlock('形容詞', u.wrongByCat['形容詞']) +
      catBlock('其他',  u.wrongByCat['其他']);
  }

  const html = `<div style="font-family:'Microsoft JhengHei',Arial,sans-serif; max-width:560px; margin:0 auto; color:#222;">
    <h2 style="color:#c0392b;">🦖 單字小恐龍日誌</h2>
    <p>${esc(u.learner)} 同學，這是你昨天的練習回顧 👇</p>
    <table style="border-collapse:collapse; width:100%; margin:12px 0; font-size:14px;">
      <tr><td style="padding:6px 10px; background:#f5f5f5;">遊玩局數</td><td style="padding:6px 10px;">${u.games} 局</td></tr>
      <tr><td style="padding:6px 10px; background:#f5f5f5;">答對 / 總題數</td><td style="padding:6px 10px;">${u.correct} / ${u.rounds}</td></tr>
      <tr><td style="padding:6px 10px; background:#f5f5f5;">正確率</td><td style="padding:6px 10px;">${accuracy}%</td></tr>
    </table>
    <h3 style="color:#333; border-bottom:2px solid #eee; padding-bottom:4px;">✏️ 錯題複習（依詞性分組）</h3>
    ${wrongSection}
    <p style="color:#888; font-size:13px; margin-top:20px;">今天也繼續加油！小葵老師陪你一起學日文 🌸</p>
  </div>`;

  out.push({ json: { to: email, subject: `🦖 單字小恐龍日誌 — ${u.learner} 的昨日回顧`, html } });
}

return out;
