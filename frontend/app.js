// Переключение вкладок (десктоп + мобильные)
    function switchTab(tabId) {
      // Скрыть все контенты, показать нужный
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      
      // Обновить активные кнопки в десктопных табах и нижнем баре
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
    // Загрузка сохранённой темы
    if (localStorage.getItem('theme') === 'dark') {
      html.classList.add('dark');
      themeToggle.innerHTML = '<span>☀️</span> Светлая';
    }

    // Обновление времени в шапке
    function updateClock() {
      const now = new Date();
      document.getElementById('liveTime').textContent = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    setInterval(updateClock, 1000);
    updateClock();

    // Обработчики кнопок периода (просто демонстрация активного состояния)
    document.querySelectorAll('.period-btn').forEach(btn => {
      btn.addEventListener('click', function(e) {
        // В рамках одной группы делаем активной только себя
        const group = this.parentElement;
        group.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
      });
    });

    // Периодическое получение последних показаний для обзора
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

    async function updateOverview() {
      const latest = await fetchLatest();
      if (!latest) {
        document.getElementById('tempValue').textContent = '--°C';
        document.getElementById('humValue').textContent = '--%';
        document.getElementById('statusText').textContent = 'ESP32 —';
        document.getElementById('updatedAgo').textContent = 'Обновлено: —';
        document.getElementById('statusDot').classList.add('offline');
        return;
      }

      const t = latest.temperature;
      const h = latest.humidity;
      const ts = new Date(latest.timestamp);
      document.getElementById('tempValue').textContent = (t !== null ? t.toFixed(1) + '°C' : '—');
      document.getElementById('humValue').textContent = (h !== null ? Math.round(h) + '%' : '—');
      const ageSec = Math.floor((Date.now() - ts.getTime()) / 1000);
      document.getElementById('updatedAgo').textContent = `Обновлено: ${ageSec}s`;
      if (ageSec < 20) {
        document.getElementById('statusText').textContent = 'ESP32 онлайн';
        document.getElementById('statusDot').classList.remove('offline');
      } else {
        document.getElementById('statusText').textContent = 'ESP32 офлайн';
        document.getElementById('statusDot').classList.add('offline');
      }
    }

    // Запускаем обновление обзора каждые 3 секунды
    setInterval(updateOverview, 3000);
    updateOverview();