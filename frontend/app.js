// Глобальные переменные для трендов
let lastTemp = null;
let lastHum = null;

// Переключение вкладок (десктоп + мобильные)
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');

  document.querySelectorAll('.tab-btn, .nav-item').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.tab === tabId) btn.classList.add('active');
  });
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// Тёмная тема
const themeToggle = document.getElementById('themeToggle');
const html = document.documentElement;
themeToggle.addEventListener('click', () => {
  html.classList.toggle('dark');
  const isDark = html.classList.contains('dark');
  themeToggle.innerHTML = isDark ? '<span>☀️</span> Светлая' : '<span>🌙</span> Тёмная';
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
});
if (localStorage.getItem('theme') === 'dark') {
  html.classList.add('dark');
  themeToggle.innerHTML = '<span>☀️</span> Светлая';
}

// Обновление времени в шапке
function updateClock() {
  const now = new Date();
  document.getElementById('liveTime').textContent = now.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}
setInterval(updateClock, 1000);
updateClock();

// Обработчики кнопок периода
document.querySelectorAll('.period-btn').forEach(btn => {
  btn.addEventListener('click', function (e) {
    const group = this.parentElement;
    group.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
  });
});

// Получение последних показаний с сервера
async function fetchLatest() {
  try {
    const resp = await fetch('/api/latest');
    if (!resp.ok) return null;
    const j = await resp.json();
    if (!j.success) return null;
    return j.data;
  } catch (e) {
    console.warn('Ошибка fetchLatest', e);
    return null;
  }
}

// Описание состояния по температуре
function getTempDescription(temp) {
  if (temp === null || temp === undefined) return '—';
  if (temp < 10) return 'Очень холодно';
  if (temp < 18) return 'Прохладно';
  if (temp < 24) return 'Комфортно';
  if (temp < 29) return 'Тепло';
  return 'Жарко';
}

// Описание состояния по влажности
function getHumDescription(hum) {
  if (hum === null || hum === undefined) return '—';
  if (hum < 30) return 'Сухо';
  if (hum < 60) return 'Нормально';
  if (hum < 80) return 'Влажно';
  return 'Очень влажно';
}

// Обновление тренда (стрелка и дельта)
function updateTrend(element, current, previous) {
  if (!element) return;
  if (previous === null || current === null || previous === current) {
    element.textContent = '—';
    element.className = 'trend';
    return;
  }
  const delta = current - previous;
  const sign = delta > 0 ? '+' : '';
  const arrow = delta > 0 ? '▲' : '▼';
  element.textContent = `${arrow} ${sign}${delta.toFixed(1)}`;
  element.className = `trend ${delta > 0 ? 'up' : 'down'}`;
}

// Основная функция обновления обзора
async function updateOverview() {
  const latest = await fetchLatest();

  const tempEl = document.getElementById('tempValue');
  const humEl = document.getElementById('humValue');
  const statusText = document.getElementById('statusText');
  const statusDot = document.getElementById('statusDot');
  const updatedAgo = document.getElementById('updatedAgo');
  const tempDesc = document.getElementById('tempDesc');
  const humDesc = document.getElementById('humDesc');
  const tempTrend = document.getElementById('tempTrend');
  const humTrend = document.getElementById('humTrend');

  if (!latest) {
    tempEl.textContent = '--°C';
    humEl.textContent = '--%';
    statusText.textContent = 'ESP32 —';
    updatedAgo.textContent = 'Обновлено: —';
    statusDot.classList.add('offline');
    tempDesc.textContent = '—';
    humDesc.textContent = '—';
    tempTrend.textContent = '—';
    humTrend.textContent = '—';
    return;
  }

  const t = latest.temperature;
  const h = latest.humidity;
  const ts = new Date(latest.timestamp);

  // Основные значения
  tempEl.textContent = t !== null ? t.toFixed(1) + '°C' : '—';
  humEl.textContent = h !== null ? Math.round(h) + '%' : '—';

  // Статус (онлайн, если данные свежее 20 секунд)
  const ageSec = Math.floor((Date.now() - ts.getTime()) / 1000);
  updatedAgo.textContent = `Обновлено: ${ageSec}с`;
  if (ageSec < 20) {
    statusText.textContent = 'ESP32 онлайн';
    statusDot.classList.remove('offline');
  } else {
    statusText.textContent = 'ESP32 офлайн';
    statusDot.classList.add('offline');
  }

  // Описания
  tempDesc.textContent = getTempDescription(t);
  humDesc.textContent = getHumDescription(h);

  // Тренды
  updateTrend(tempTrend, t, lastTemp);
  updateTrend(humTrend, h, lastHum);

  // Сохраняем текущие значения для следующего сравнения
  lastTemp = t;
  lastHum = h;
}

// Запуск обновления каждые 3 секунды
setInterval(updateOverview, 3000);
updateOverview();