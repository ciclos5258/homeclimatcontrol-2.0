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