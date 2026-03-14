{
  "name": "fast-drop-server",
  "version": "1.0.0",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.18.2"
  }
}

const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const DATA_FILE = path.join(__dirname, 'data.json');

app.use(cors());
app.use(express.json());

function loadData() {
  try {
    if (!fs.existsSync(DATA_FILE)) return {};
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  } catch { return {}; }
}

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

function getUser(data, userId) {
  if (!data[userId]) {
    data[userId] = { balance: 0, gifts: [], daily_last: 0, vip_bonus: false, promos_used: [] };
  }
  return data[userId];
}

// ── Balance ──
app.get('/api/user/:userId/balance', (req, res) => {
  const data = loadData();
  res.json({ balance: getUser(data, req.params.userId).balance });
});

app.post('/api/user/:userId/balance', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  user.balance = req.body.balance ?? 0;
  saveData(data);
  res.json({ balance: user.balance });
});

// ── Gifts ──
app.get('/api/user/:userId/gifts', (req, res) => {
  const data = loadData();
  res.json({ gifts: getUser(data, req.params.userId).gifts });
});

app.post('/api/user/:userId/gifts', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  if (req.body.gift) { user.gifts.push(req.body.gift); saveData(data); }
  res.json({ success: true });
});

app.delete('/api/user/:userId/gifts/:code', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  const gift = user.gifts.find(g => g.code === req.params.code);
  if (!gift) return res.status(404).json({ error: 'Not found' });
  user.gifts = user.gifts.filter(g => g.code !== req.params.code);
  saveData(data);
  res.json({ success: true, gift });
});

// ── Daily ──
app.get('/api/user/:userId/daily', (req, res) => {
  const data = loadData();
  res.json({ daily_last: getUser(data, req.params.userId).daily_last });
});

app.post('/api/user/:userId/daily', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  user.daily_last = req.body.daily_last ?? 0;
  saveData(data);
  res.json({ daily_last: user.daily_last });
});

// ── VIP ──
app.get('/api/user/:userId/vip', (req, res) => {
  const data = loadData();
  res.json({ vip_bonus: getUser(data, req.params.userId).vip_bonus });
});

app.post('/api/user/:userId/vip', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  user.vip_bonus = true;
  saveData(data);
  res.json({ vip_bonus: true });
});

// ── Promo ──
app.get('/api/user/:userId/promo/:code', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  res.json({ used: (user.promos_used || []).includes(req.params.code) });
});

app.post('/api/user/:userId/promo/:code', (req, res) => {
  const data = loadData();
  const user = getUser(data, req.params.userId);
  if (!user.promos_used) user.promos_used = [];
  if (!user.promos_used.includes(req.params.code)) user.promos_used.push(req.params.code);
  saveData(data);
  res.json({ used: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server on port ${PORT}`));


// ===== КОНФИГУРАЦИЯ =====
const API_BASE = 'https://fast-drop-production-95b3.up.railway.app';

// ===== ЛОКАЛЬНЫЙ КЭШ (синхронная работа UI) =====
let _balance = 0;
let _gifts = [];
let _dailyLast = 0;
let userId = null;

// ===== API HELPERS =====
async function apiGet(path) {
  try {
    const res = await fetch(API_BASE + path);
    if (!res.ok) return null;
    return await res.json();
  } catch(e) { console.error('GET', path, e); return null; }
}

async function apiPost(path, body) {
  try {
    const res = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) return null;
    return await res.json();
  } catch(e) { console.error('POST', path, e); return null; }
}

async function apiDelete(path) {
  try {
    const res = await fetch(API_BASE + path, { method: 'DELETE' });
    if (!res.ok) return null;
    return await res.json();
  } catch(e) { console.error('DELETE', path, e); return null; }
}

// ===== БАЛАНС =====
function getBalance() { return _balance; }

function setBalance(value) {
  _balance = value;
  const el = document.getElementById('balance');
  if (el) el.textContent = value;
  document.querySelectorAll('.modal-balance').forEach(el => el.textContent = value);
  if (userId) apiPost(`/api/user/${userId}/balance`, { balance: value });
}

// ===== ИНИЦИАЛИЗАЦИЯ ДАННЫХ С СЕРВЕРА =====
async function initData() {
  if (!userId) return;
  const [balData, giftsData, dailyData] = await Promise.all([
    apiGet(`/api/user/${userId}/balance`),
    apiGet(`/api/user/${userId}/gifts`),
    apiGet(`/api/user/${userId}/daily`)
  ]);
  if (balData !== null)   _balance   = balData.balance    || 0;
  if (giftsData !== null) _gifts     = giftsData.gifts    || [];
  if (dailyData !== null) _dailyLast = dailyData.daily_last || 0;

  const el = document.getElementById('balance');
  if (el) el.textContent = _balance;
  document.querySelectorAll('.modal-balance').forEach(el => el.textContent = _balance);
}

// ===== GUEST ID (только для идентификации, не для хранения данных) =====
function getGuestId() {
  let gid = localStorage.getItem('guest_id');
  if (!gid) { gid = Math.random().toString(36).substr(2, 9); localStorage.setItem('guest_id', gid); }
  return gid;
}

// ===== УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ =====
function notifyOwner(username, uid, prizeName, prizeStars, code, caseName) {
  const token = '8657069014:AAECyVfbXP3ta9dWLi054uR_PC00F9Q1POY';
  const chatId = '6794644473';
  const text = `🎁 Новый выигрыш!\n\n👤 Пользователь: ${username}\n🆔 ID: ${uid}\n📦 Кейс: ${caseName}\n🏆 Приз: ${prizeName}\n⭐️ Звёзд: ${prizeStars}\n🔑 Код: ${code}\n🕐 Время: ${new Date().toLocaleString('ru-RU')}`;
  fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text })
  }).catch(e => console.log('Notify error:', e));
}

// ===== ИНИЦИАЛИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ =====
let currentUser = null;

async function initUser() {
  try {
    const tg = window.Telegram.WebApp;
    tg.expand();
    tg.ready();
    const user = tg.initDataUnsafe?.user;
    if (user) {
      currentUser = user;
      userId = 'tg_' + user.id;
      document.getElementById('user-name').textContent = user.username ? '@' + user.username : user.first_name;
      document.getElementById('user-id').textContent = 'ID: ' + user.id;
    } else {
      userId = 'guest_' + getGuestId();
      document.getElementById('user-name').textContent = 'Гость';
      document.getElementById('user-id').textContent = 'ID: откройте в Telegram';
    }
  } catch(e) {
    userId = 'guest_' + getGuestId();
    document.getElementById('user-name').textContent = 'Гость';
    document.getElementById('user-id').textContent = 'ID: откройте в Telegram';
  }

  await initData();

  // VIP бонус
  if (currentUser) {
    const vipIds = [6794644473, 6227572453, 6909040298];
    if (vipIds.includes(currentUser.id)) {
      const vipData = await apiGet(`/api/user/${userId}/vip`);
      if (vipData && !vipData.vip_bonus) {
        setBalance(_balance + 100000);
        await apiPost(`/api/user/${userId}/vip`, {});
        alert('👑 VIP бонус! Вам начислено 100,000 ⭐️');
      }
    }
  }

  updateDailyTimerOnCard();
}

if (document.readyState === 'complete' || document.readyState === 'interactive') {
  setTimeout(initUser, 100);
} else {
  window.addEventListener('DOMContentLoaded', () => setTimeout(initUser, 100));
}

// ===== ПОДАРКИ =====
function generateCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let code = '';
  for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
  return code;
}

async function saveGift(prize, caseName) {
  const code = generateCode();
  const gift = {
    code,
    name: prize.name,
    img: prize.img,
    stars: prize.stars,
    caseName,
    date: new Date().toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' })
  };
  _gifts.push(gift);
  if (userId) await apiPost(`/api/user/${userId}/gifts`, { gift });

  const username = currentUser ? (currentUser.username ? '@' + currentUser.username : currentUser.first_name) : 'Гость';
  const uid = currentUser ? currentUser.id : 'неизвестно';
  notifyOwner(username, uid, prize.name, prize.stars, code, caseName);
  return code;
}

window.sellGift = async function(code) {
  const gift = _gifts.find(g => g.code === code);
  if (!gift) return;
  _gifts = _gifts.filter(g => g.code !== code);
  _balance += gift.stars;
  const el = document.getElementById('balance');
  if (el) el.textContent = _balance;
  document.querySelectorAll('.modal-balance').forEach(el => el.textContent = _balance);
  if (userId) {
    await Promise.all([
      apiDelete(`/api/user/${userId}/gifts/${code}`),
      apiPost(`/api/user/${userId}/balance`, { balance: _balance })
    ]);
  }
  showProfile();
}

window.showProfile = function() {
  const list = document.getElementById('gifts-list');
  document.getElementById('profile-page').style.display = 'block';
  if (_gifts.length === 0) {
    list.innerHTML = '<p style="color:#94a3b8; text-align:center; padding:20px;">У вас пока нет подарков</p>';
  } else {
    list.innerHTML = [..._gifts].reverse().map(g => `
      <div style="display:flex; flex-direction:column; gap:8px; background:rgba(255,255,255,0.05); border-radius:12px; padding:10px; margin-bottom:10px; border:1px solid rgba(180,77,255,0.3);">
        <div style="display:flex; align-items:center; gap:10px;">
          <img src="${g.img}" style="width:50px; height:50px; object-fit:contain; border-radius:8px;">
          <div style="flex:1;">
            <div style="font-weight:bold; color:white; font-size:14px;">${g.name}</div>
            <div style="color:#f59e0b; font-size:13px;">⭐️ ${g.stars}</div>
            <div style="color:#94a3b8; font-size:11px;">${g.date}</div>
            <div style="color:#94a3b8; font-size:11px;">📦 ${g.caseName || ''}</div>
          </div>
        </div>
        <div style="color:#94a3b8; font-size:11px;">📩 За призом:</div>
        <div style="display:flex; gap:6px;">
          <button onclick="window.Telegram.WebApp.openTelegramLink('https://t.me/Marixbuvshuypsevd')" style="flex:1; padding:5px 8px; background:rgba(180,77,255,0.2); border:1px solid #b44dff; border-radius:8px; color:#b44dff; font-size:11px; cursor:pointer;">✉️ @Marixbuvshuypsevd</button>
          <button onclick="window.Telegram.WebApp.openTelegramLink('https://t.me/blackrfly')" style="flex:1; padding:5px 8px; background:rgba(180,77,255,0.2); border:1px solid #b44dff; border-radius:8px; color:#b44dff; font-size:11px; cursor:pointer;">✉️ @blackrfly</button>
        </div>
        <div style="color:#b44dff; font-weight:bold; letter-spacing:2px; font-size:14px; text-shadow:0 0 8px #b44dff;">${g.code}</div>
        <div style="display:flex; gap:6px;">
          <button onclick="navigator.clipboard.writeText('${g.code}')" style="flex:1; padding:8px; background:rgba(180,77,255,0.2); border:1px solid #b44dff; border-radius:8px; color:#b44dff; font-size:12px; cursor:pointer;">📋 Копировать</button>
          <button onclick="sellGift('${g.code}')" style="flex:1; padding:8px; background:linear-gradient(135deg, #f59e0b, #d97706); border:none; border-radius:10px; color:white; font-size:13px; font-weight:bold; cursor:pointer;">Продать ⭐️${g.stars}</button>
        </div>
      </div>
    `).join('');
  }
}

window.showPage = function(page, btn) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (page === 'profile') { showProfile(); }
  else { document.getElementById('profile-page').style.display = 'none'; }
}

// ===== ЕЖЕДНЕВНЫЙ КЕЙС =====
const DAILY_COOLDOWN = 24 * 60 * 60 * 1000;

function getDailyTimeLeft() {
  const diff = DAILY_COOLDOWN - (Date.now() - _dailyLast);
  return diff > 0 ? diff : 0;
}

function formatTime(ms) {
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function updateDailyTimerOnCard() {
  const el = document.getElementById('daily-timer-card');
  if (!el) return;
  const left = getDailyTimeLeft();
  if (left <= 0) { el.textContent = '⭐️ Бесплатно'; el.style.color = '#f59e0b'; }
  else { el.textContent = '⏳ ' + formatTime(left); el.style.color = '#94a3b8'; }
}

setInterval(updateDailyTimerOnCard, 1000);

// ===== ПРИЗЫ =====
const prizesDaily = [
  { name: "1 звезда",  img: "pictures/images/1773342181234.png", stars: 1,  chance: 50 },
  { name: "5 звёзд",  img: "pictures/images/1773342218325.png", stars: 5,  chance: 25 },
  { name: "10 звёзд", img: "pictures/images/1773342164112.png", stars: 10, chance: 12 },
  { name: "15 звёзд", img: "pictures/images/1773342268761.png", stars: 15, chance: 7  },
  { name: "25 звёзд", img: "pictures/images/1773342131424.png", stars: 25, chance: 4  },
  { name: "50 звёзд", img: "pictures/images/1773342234083.png", stars: 50, chance: 2  },
];

const prizesLight = [
  { name: "Роза",         img: "pictures/images/1773311505678.png", stars: 25,  chance: 29 },
  { name: "Букет",        img: "pictures/images/1773311655607.png", stars: 50,  chance: 25 },
  { name: "Ракета",       img: "pictures/images/1773311691532.png", stars: 50,  chance: 20 },
  { name: "Кольцо",       img: "pictures/images/1773312032631.png", stars: 100, chance: 12 },
  { name: "Кубок",        img: "pictures/images/1773311930144.png", stars: 100, chance: 11 },
  { name: "Instant Ramen",img: "pictures/images/1773311281720.png", stars: 650, chance: 1  },
  { name: "Lol Pop",      img: "pictures/images/1773311237773.png", stars: 650, chance: 1  },
  { name: "Cookie Heart", img: "pictures/images/1773311201181.png", stars: 650, chance: 1  },
];

const prizesEvilEye = [
  { name: "Мишка",   img: "pictures/images/1773322669546.png", stars: 15,  chance: 40   },
  { name: "Сердечко",img: "pictures/images/1773322700647.png", stars: 15,  chance: 30   },
  { name: "Роза",    img: "pictures/images/1773311505678.png", stars: 25,  chance: 20   },
  { name: "Торт",    img: "pictures/images/1773322467517.png", stars: 50,  chance: 7    },
  { name: "Кольцо",  img: "pictures/images/1773312032631.png", stars: 100, chance: 1    },
  { name: "Кубок",   img: "pictures/images/1773311930144.png", stars: 100, chance: 0.9  },
  { name: "Evil Eye",img: "pictures/images/1773322554814.png", stars: 750, chance: 0.08 },
];

const prizesWomans = [
  { name: "Торт",             img: "pictures/images/1773322467517.png",          stars: 50,  chance: 39 },
  { name: "Ракета",           img: "pictures/images/1773311691532.png",          stars: 50,  chance: 39 },
  { name: "Кубок",            img: "pictures/images/1773311930144.png",          stars: 100, chance: 9  },
  { name: "Кольцо",           img: "pictures/images/1773312032631.png",          stars: 100, chance: 8  },
  { name: "NFT Букет",        img: "pictures/images/IMG_20260312_210935_560.png", stars: 350, chance: 3  },
  { name: "NFT Ваза роз",     img: "pictures/images/IMG_20260312_210932_483.png", stars: 600, chance: 1  },
  { name: "NFT Пакет с розами",img:"pictures/images/IMG_20260312_210934_051.png", stars: 650, chance: 1  },
];

function getPrize(prizesArr) {
  let rand = Math.random() * 100, sum = 0;
  for (let prize of prizesArr) { sum += prize.chance; if (rand <= sum) return prize; }
  return prizesArr[0];
}

// ===== СОЗДАНИЕ ОБЫЧНОГО МОДАЛА =====
function createModal(id, title, prizes, price) {
  const modal = document.createElement('div');
  modal.id = id;
  modal.innerHTML = `
    <div class="modal-bg">
      <div class="modal-box">
        <div class="modal-title">🎁 ${title}</div>
        <div style="font-size:16px; font-weight:bold; color:#f59e0b;">⭐️ <span class="modal-balance">${_balance}</span></div>
        <button class="back-btn-top" id="${id}-back-top">← В меню</button>
        <div class="roulette-wrap">
          <div class="roulette-arrow">▼</div>
          <div class="roulette-track-wrap">
            <div class="roulette-track" id="${id}-track"></div>
          </div>
        </div>
        <button class="open-btn" id="${id}-open-btn">Открыть за ${price} ⭐️</button>
        <div class="modal-result" id="${id}-result" style="display:none">
          <img class="result-img" id="${id}-result-img">
          <div class="result-name" id="${id}-result-name"></div>
          <div class="result-stars" id="${id}-result-stars"></div>
          <div class="result-code-wrap">
            <span class="result-code-label">Код подарка:</span>
            <span class="result-code" id="${id}-result-code"></span>
            <button onclick="navigator.clipboard.writeText(document.getElementById('${id}-result-code').textContent)" style="margin-top:6px; padding:6px 16px; background:rgba(180,77,255,0.2); border:1px solid #b44dff; border-radius:8px; color:#b44dff; font-size:13px; cursor:pointer;">📋 Копировать</button>
          </div>
          <button class="result-btn" id="${id}-result-btn">Открыть ещё раз ⭐️</button>
          <button class="back-btn" id="${id}-back-btn">← Вернуться в меню</button>
        </div>
        <div class="prizes-list">
          ${prizes.map(p => `
            <div class="prize-row">
              <img src="${p.img}" class="prize-row-img">
              <div class="prize-row-info">
                <span class="prize-row-name">${p.name}</span>
                <span class="prize-row-stars">⭐️ ${p.stars}</span>
              </div>
            </div>
          `).join('')}
        </div>
        <button class="back-btn-bottom" id="${id}-back-bottom">← Вернуться в меню</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  modal.style.display = 'none';

  document.getElementById(`${id}-open-btn`).addEventListener('click', async () => {
    const balance = getBalance();
    if (balance < price) { alert(`Недостаточно звёзд! Нужно ${price} ⭐️`); return; }
    setBalance(balance - price);
    document.getElementById(`${id}-open-btn`).disabled = true;
    document.getElementById(`${id}-result`).style.display = 'none';
    const prize = getPrize(prizes);
    const track = document.getElementById(`${id}-track`);
    track.style.transition = 'none';
    track.style.transform = 'translateX(0)';
    const items = [];
    for (let i = 0; i < 40; i++) items.push(prizes[Math.floor(Math.random() * prizes.length)]);
    items[32] = prize;
    track.innerHTML = items.map(p => `<div class="roulette-item"><img src="${p.img}" alt="${p.name}"><span>${p.name}</span></div>`).join('');
    const offset = 32 * 108 - 140;
    setTimeout(() => { track.style.transition = 'transform 4s cubic-bezier(0.12, 0.8, 0.25, 1)'; track.style.transform = `translateX(-${offset}px)`; }, 100);
    setTimeout(async () => {
      const code = await saveGift(prize, title);
      document.getElementById(`${id}-result-img`).src = prize.img;
      document.getElementById(`${id}-result-name`).textContent = prize.name;
      document.getElementById(`${id}-result-stars`).textContent = '⭐️ ' + prize.stars + ' звёзд';
      document.getElementById(`${id}-result-code`).textContent = code;
      document.getElementById(`${id}-result`).style.display = 'flex';
      document.getElementById(`${id}-open-btn`).disabled = false;
    }, 4500);
  });

  document.getElementById(`${id}-result-btn`).addEventListener('click', () => { document.getElementById(`${id}-result`).style.display = 'none'; });
  document.getElementById(`${id}-back-btn`).addEventListener('click', () => { modal.style.display = 'none'; });
  document.getElementById(`${id}-back-top`).addEventListener('click', () => { modal.style.display = 'none'; });
  document.getElementById(`${id}-back-bottom`).addEventListener('click', () => { modal.style.display = 'none'; });
  return modal;
}

// ===== ЕЖЕДНЕВНЫЙ МОДАЛ =====
function createDailyModal() {
  const modal = document.createElement('div');
  modal.id = 'modal-daily';
  modal.innerHTML = `
    <div class="modal-bg">
      <div class="modal-box">
        <div class="modal-title">🎁 Ежедневный кейс</div>
        <div style="font-size:16px; font-weight:bold; color:#f59e0b;">⭐️ <span class="modal-balance">${_balance}</span></div>
        <button class="back-btn-top" id="daily-back-top">← В меню</button>
        <div class="roulette-wrap">
          <div class="roulette-arrow">▼</div>
          <div class="roulette-track-wrap">
            <div class="roulette-track" id="daily-track"></div>
          </div>
        </div>
        <button class="open-btn" id="daily-open-btn">Открыть бесплатно</button>
        <div id="daily-timer-modal-wrap" style="display:none; text-align:center; background:rgba(255,255,255,0.05); border-radius:12px; padding:14px; width:100%; border:1px solid rgba(255,255,255,0.1);">
          <div style="font-size:13px; color:#94a3b8; margin-bottom:6px;">Следующий кейс через:</div>
          <div id="daily-timer-modal" style="font-size:26px; font-weight:bold; color:#f59e0b; letter-spacing:2px; text-shadow:0 0 10px #f59e0b;"></div>
        </div>
        <div class="modal-result" id="daily-result" style="display:none">
          <img class="result-img" id="daily-result-img">
          <div class="result-name" id="daily-result-name"></div>
          <div class="result-stars" id="daily-result-stars"></div>
          <button class="back-btn" id="daily-back-btn">← Вернуться в меню</button>
        </div>
        <div class="prizes-list">
          ${prizesDaily.map(p => `
            <div class="prize-row">
              <img src="${p.img}" class="prize-row-img">
              <div class="prize-row-info">
                <span class="prize-row-name">${p.name}</span>
                <span class="prize-row-stars">⭐️ ${p.stars}</span>
              </div>
            </div>
          `).join('')}
        </div>
        <button class="back-btn-bottom" id="daily-back-bottom">← Вернуться в меню</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  modal.style.display = 'none';

  function updateDailyModalTimer() {
    const left = getDailyTimeLeft();
    const btn = document.getElementById('daily-open-btn');
    const timerWrap = document.getElementById('daily-timer-modal-wrap');
    const timerEl = document.getElementById('daily-timer-modal');
    if (left <= 0) {
      btn.disabled = false; btn.textContent = 'Открыть бесплатно'; btn.style.opacity = '1';
      timerWrap.style.display = 'none';
    } else {
      btn.disabled = true; btn.textContent = 'Недоступно'; btn.style.opacity = '0.5';
      timerWrap.style.display = 'block'; timerEl.textContent = formatTime(left);
    }
  }

  setInterval(updateDailyModalTimer, 1000);
  updateDailyModalTimer();

  document.getElementById('daily-open-btn').addEventListener('click', async () => {
    if (getDailyTimeLeft() > 0) return;
    document.getElementById('daily-open-btn').disabled = true;
    document.getElementById('daily-result').style.display = 'none';
    const prize = getPrize(prizesDaily);
    const track = document.getElementById('daily-track');
    track.style.transition = 'none'; track.style.transform = 'translateX(0)';
    const items = [];
    for (let i = 0; i < 40; i++) items.push(prizesDaily[Math.floor(Math.random() * prizesDaily.length)]);
    items[32] = prize;
    track.innerHTML = items.map(p => `<div class="roulette-item"><img src="${p.img}" alt="${p.name}"><span>${p.name}</span></div>`).join('');
    const offset = 32 * 108 - 140;
    setTimeout(() => { track.style.transition = 'transform 4s cubic-bezier(0.12, 0.8, 0.25, 1)'; track.style.transform = `translateX(-${offset}px)`; }, 100);
    setTimeout(async () => {
      _dailyLast = Date.now();
      if (userId) await apiPost(`/api/user/${userId}/daily`, { daily_last: _dailyLast });
      setBalance(_balance + prize.stars);
      const username = currentUser ? (currentUser.username ? '@' + currentUser.username : currentUser.first_name) : 'Гость';
      const uid = currentUser ? currentUser.id : 'неизвестно';
      notifyOwner(username, uid, prize.name, prize.stars, '—', 'Ежедневный кейс');
      document.getElementById('daily-result-img').src = prize.img;
      document.getElementById('daily-result-name').textContent = prize.name;
      document.getElementById('daily-result-stars').textContent = '⭐️ +' + prize.stars + ' звёзд добавлено!';
      document.getElementById('daily-result').style.display = 'flex';
      updateDailyModalTimer();
      updateDailyTimerOnCard();
    }, 4500);
  });

  document.getElementById('daily-back-btn').addEventListener('click', () => { modal.style.display = 'none'; });
  document.getElementById('daily-back-top').addEventListener('click', () => { modal.style.display = 'none'; });
  document.getElementById('daily-back-bottom').addEventListener('click', () => { modal.style.display = 'none'; });
  return modal;
}

// ===== СОЗДАЁМ МОДАЛЫ =====
const modalDaily   = createDailyModal();
const modalLight   = createModal('modal-light',   'Light Case',    prizesLight,   169);
const modalEvilEye = createModal('modal-evileye', 'Evil Eye Case', prizesEvilEye, 19);
const modalWomans  = createModal('modal-womans',  "Woman's Case",  prizesWomans,  99);

// ===== СТИЛИ =====
const style = document.createElement('style');
style.textContent = `
  #modal-daily, #modal-light, #modal-evileye, #modal-womans { position:fixed; top:0; left:0; width:100%; height:100%; z-index:1000; overflow-y:auto; }
  .modal-bg { min-height:100%; background:radial-gradient(ellipse at top, #1a0a3e 0%, #0a0a1a 50%, #000510 100%); display:flex; align-items:flex-start; justify-content:center; padding:20px 10px 40px 10px; }
  .modal-box { width:100%; max-width:420px; display:flex; flex-direction:column; align-items:center; gap:20px; }
  .modal-title { font-size:22px; font-weight:bold; color:white; text-shadow:0 0 15px #b44dff; }
  .back-btn-top { width:100%; padding:10px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:12px; color:white; font-size:14px; cursor:pointer; }
  .roulette-wrap { width:100%; display:flex; flex-direction:column; align-items:center; }
  .roulette-arrow { font-size:24px; color:#b44dff; text-shadow:0 0 10px #b44dff; margin-bottom:4px; }
  .roulette-track-wrap { width:100%; overflow:hidden; border:2px solid #b44dff; border-radius:12px; box-shadow:0 0 20px #b44dff; background:rgba(0,0,0,0.5); height:120px; }
  .roulette-track { display:flex; align-items:center; height:120px; }
  .roulette-item { min-width:100px; height:110px; display:flex; flex-direction:column; align-items:center; justify-content:center; margin:0 4px; border-radius:10px; background:linear-gradient(145deg, #1a0a3e, #0d1b3e); border:1px solid rgba(180,77,255,0.4); gap:4px; flex-shrink:0; }
  .roulette-item img { width:60px; height:60px; object-fit:contain; }
  .roulette-item span { font-size:10px; color:#ccc; }
  .open-btn { width:100%; padding:14px; background:linear-gradient(135deg, #b44dff, #6600cc); border:none; border-radius:12px; color:white; font-size:18px; font-weight:bold; cursor:pointer; box-shadow:0 0 15px #b44dff; }
  .modal-result { display:flex; flex-direction:column; align-items:center; gap:10px; background:radial-gradient(ellipse, #1a3a1a, #0a1a0a); border:2px solid #4ade80; box-shadow:0 0 20px #4ade80; border-radius:16px; padding:20px 30px; width:100%; }
  .result-img { width:100px; height:100px; object-fit:contain; }
  .result-name { font-size:22px; font-weight:bold; color:white; }
  .result-stars { font-size:18px; color:#f59e0b; }
  .result-code-wrap { display:flex; flex-direction:column; align-items:center; gap:4px; background:rgba(0,0,0,0.4); border-radius:10px; padding:8px 20px; width:100%; }
  .result-code-label { font-size:12px; color:#94a3b8; }
  .result-code { font-size:20px; font-weight:bold; color:#b44dff; letter-spacing:3px; text-shadow:0 0 10px #b44dff; }
  .result-btn { width:100%; padding:12px; background:linear-gradient(135deg, #b44dff, #6600cc); border:none; border-radius:12px; color:white; font-size:15px; font-weight:bold; cursor:pointer; box-shadow:0 0 15px #b44dff; }
  .back-btn, .back-btn-bottom { width:100%; padding:12px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:12px; color:white; font-size:15px; cursor:pointer; }
  .prizes-list { width:100%; background:linear-gradient(180deg, #0a2a0a, #051505); border-radius:16px; border:2px solid #4ade80; box-shadow:0 0 20px rgba(74,222,128,0.3); padding:10px; display:flex; flex-direction:column; gap:8px; }
  .prize-row { display:flex; align-items:center; gap:10px; background:rgba(255,255,255,0.05); border-radius:10px; padding:8px; }
  .prize-row-img { width:50px; height:50px; object-fit:contain; border-radius:8px; background:rgba(0,0,0,0.3); }
  .prize-row-info { display:flex; flex-direction:column; flex:1; }
  .prize-row-name { font-size:14px; font-weight:bold; color:white; }
  .prize-row-stars { font-size:13px; color:#f59e0b; }
`;
document.head.appendChild(style);

// ===== ОТКРЫТИЕ КЕЙСОВ =====
document.querySelectorAll('.case').forEach(button => {
  button.addEventListener('click', () => {
    if (button.dataset.id === '1') modalDaily.style.display   = 'block';
    if (button.dataset.id === '2') modalLight.style.display   = 'block';
    if (button.dataset.id === '3') modalEvilEye.style.display = 'block';
    if (button.dataset.id === '4') modalWomans.style.display  = 'block';
  });
});

// ===== МОДАЛ ЗВЁЗД =====
function openStarsModal() {
  document.getElementById('stars-modal').style.display = 'block';
  switchStarsTab('buy');
}

const starsModalEl = document.createElement('div');
starsModalEl.id = 'stars-modal';
starsModalEl.style.display = 'none';
starsModalEl.innerHTML = `
  <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:radial-gradient(ellipse at top, #1a0a3e 0%, #0a0a1a 50%, #000510 100%); z-index:2000; overflow-y:auto; padding:20px 10px 40px;">
    <div style="max-width:420px; margin:0 auto; display:flex; flex-direction:column; gap:16px;">
      <div style="font-size:22px; font-weight:bold; color:white; text-align:center; text-shadow:0 0 15px #b44dff;">⭐️ Звёзды</div>
      <div style="display:flex; gap:8px;">
        <button id="stars-tab-buy"   onclick="switchStarsTab('buy')"   style="flex:1; padding:10px; border-radius:10px; border:2px solid #b44dff; background:rgba(180,77,255,0.3); color:white; font-size:14px; font-weight:bold; cursor:pointer;">💫 Купить</button>
        <button id="stars-tab-promo" onclick="switchStarsTab('promo')" style="flex:1; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.2); background:rgba(255,255,255,0.05); color:white; font-size:14px; cursor:pointer;">🎟 Промокод</button>
        <button id="stars-tab-ton"   onclick="switchStarsTab('ton')"   style="flex:1; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.2); background:rgba(255,255,255,0.05); color:white; font-size:14px; cursor:pointer;">💎 TON</button>
      </div>
      <div id="stars-content-buy" style="display:flex; flex-direction:column; gap:10px;">
        <div style="color:#94a3b8; font-size:13px; text-align:center;">Введите количество звёзд для покупки</div>
        <input id="stars-amount-input" type="number" min="1" placeholder="Например: 500" style="width:100%; padding:12px; border-radius:12px; border:2px solid #b44dff; background:rgba(0,0,0,0.4); color:white; font-size:16px; text-align:center; outline:none; box-sizing:border-box;">
        <button onclick="buyStars()" style="width:100%; padding:14px; background:linear-gradient(135deg, #b44dff, #6600cc); border:none; border-radius:12px; color:white; font-size:16px; font-weight:bold; cursor:pointer; box-shadow:0 0 15px #b44dff;">Купить ⭐️</button>
      </div>
      <div id="stars-content-promo" style="display:none; flex-direction:column; gap:10px;">
        <div style="color:#94a3b8; font-size:13px; text-align:center;">Введите промокод для получения звёзд</div>
        <input id="promo-input" type="text" placeholder="Введите промокод..." style="width:100%; padding:12px; border-radius:12px; border:2px solid #b44dff; background:rgba(0,0,0,0.4); color:white; font-size:16px; text-align:center; outline:none; box-sizing:border-box;">
        <button onclick="activatePromo()" style="width:100%; padding:14px; background:linear-gradient(135deg, #b44dff, #6600cc); border:none; border-radius:12px; color:white; font-size:16px; font-weight:bold; cursor:pointer; box-shadow:0 0 15px #b44dff;">Активировать</button>
        <div id="promo-result" style="text-align:center; font-size:14px;"></div>
      </div>
      <div id="stars-content-ton" style="display:none; flex-direction:column; align-items:center; gap:12px; padding:20px 0;">
        <div style="font-size:48px;">💎</div>
        <div style="font-size:20px; font-weight:bold; color:white;">Оплата через TON</div>
        <div style="color:#94a3b8; font-size:13px; text-align:center;">1 TON = 90 ⭐️<br>Введите количество звёзд</div>
        <input id="ton-stars-input" type="number" min="1" step="1" placeholder="Например: 1" style="width:100%; padding:12px; border-radius:12px; border:2px solid #0098ea; background:rgba(0,0,0,0.4); color:white; font-size:16px; text-align:center; outline:none; box-sizing:border-box;">
        <div id="ton-amount-display" style="color:#0098ea; font-size:16px; font-weight:bold;">≈ 0 TON</div>
        <button onclick="payTON()" style="width:100%; padding:14px; background:linear-gradient(135deg, #0098ea, #0066cc); border:none; border-radius:12px; color:white; font-size:16px; font-weight:bold; cursor:pointer; box-shadow:0 0 15px #0098ea;">💎 Оплатить TON</button>
        <div style="color:#94a3b8; font-size:11px; text-align:center;">После оплаты напишите нам — звёзды начислим вручную</div>
      </div>
      <button onclick="document.getElementById('stars-modal').style.display='none'" style="width:100%; padding:12px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:12px; color:white; font-size:15px; cursor:pointer;">← Закрыть</button>
    </div>
  </div>
`;
document.body.appendChild(starsModalEl);

function switchStarsTab(tab) {
  ['buy','promo','ton'].forEach(t => {
    const c = document.getElementById('stars-content-' + t);
    const b = document.getElementById('stars-tab-' + t);
    if (c) c.style.display = 'none';
    if (b) { b.style.background = 'rgba(255,255,255,0.05)'; b.style.border = '1px solid rgba(255,255,255,0.2)'; b.style.fontWeight = 'normal'; }
  });
  const ac = document.getElementById('stars-content-' + tab);
  const ab = document.getElementById('stars-tab-' + tab);
  if (ac) { ac.style.display = 'flex'; ac.style.flexDirection = 'column'; }
  if (ab) { ab.style.background = 'rgba(180,77,255,0.3)'; ab.style.border = '2px solid #b44dff'; ab.style.fontWeight = 'bold'; }
}

function buyStars() {
  const amount = parseInt(document.getElementById('stars-amount-input').value);
  if (!amount || amount < 1) { alert('Введите количество звёзд!'); return; }
  const tg = window.Telegram?.WebApp;
  if (!tg) { alert('Откройте приложение через Telegram'); return; }
  try { tg.openTelegramLink(`https://t.me/FastDropFirstBot?start=buy_${amount}`); }
  catch(e) { alert('Не удалось открыть бота'); }
}

const PROMO_CODES = { "FREE10": 10, "START50": 50 };

async function activatePromo() {
  const input = document.getElementById('promo-input');
  const result = document.getElementById('promo-result');
  const code = input.value.trim().toUpperCase();
  if (!code) { result.textContent = '❌ Введите промокод!'; result.style.color = '#f87171'; return; }
  const reward = PROMO_CODES[code];
  if (!reward) { result.textContent = '❌ Неверный промокод!'; result.style.color = '#f87171'; return; }
  const uid = userId || 'guest_' + getGuestId();
  const checkData = await apiGet(`/api/user/${uid}/promo/${code}`);
  if (checkData && checkData.used) { result.textContent = '❌ Промокод уже использован!'; result.style.color = '#f87171'; return; }
  setBalance(_balance + reward);
  await apiPost(`/api/user/${uid}/promo/${code}`, {});
  result.textContent = `✅ Получено +${reward} ⭐️`;
  result.style.color = '#4ade80';
}

function payTON() {
  const stars = parseInt(document.getElementById('ton-stars-input').value);
  if (!stars || stars < 1) { alert('Введите количество звёзд!'); return; }
  const ton = (stars / 90).toFixed(2);
  const address = 'UQAzX8me42V164qefMy6GCp3TA8Q9pXT6Y8Jlh0R3-gcDqim';
  const url = `https://t.me/wallet?startattach=ton_transfer_${address}_${ton}`;
  try { Telegram.WebApp.openTelegramLink(url); } catch { window.open(url, '_blank'); }
}