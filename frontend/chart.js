(function () {
  'use strict';

  // Цветовая схема (меняется при переключении темы)
  const lightColors = {
    grid: '#E2E8F0',
    text: '#64748B',
    tempLine: '#EF4444',
    humLine: '#3B82F6',
  };
  const darkColors = {
    grid: '#334155',
    text: '#94A3B8',
    tempLine: '#F87171',
    humLine: '#60A5FA',
  };
  let currentColors = document.documentElement.classList.contains('dark') ? darkColors : lightColors;

  // Объекты графиков
  let tempChart, humChart, sparklineChart;

  // Активный период (по умолчанию 1 час)
  let activePeriod = '1h';

  // ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

  /**
   * Загружает реальные данные с бэкенда
   * @param {string} period - период: '1h', '6h', '24h', '7d', '30d', 'all'
   * @returns {Promise<Array>} массив объектов {timestamp, temperature, humidity}
   */
  async function fetchRealData(period) {
    try {
      const response = await fetch(`/api/data?period=${period}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const json = await response.json();
      if (!json.success) {
        throw new Error(json.error || 'Ошибка API');
      }
      return json.data; // массив { timestamp, temperature, humidity }
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      return []; // при ошибке возвращаем пустой массив
    }
  }

  // Универсальная функция загрузки (использует реальный API)
  async function loadData(period) {
    return fetchRealData(period);
  }

  // Преобразование данных в формат для Chart.js
  function prepareDatasets(data) {
    const labels = data.map(d => {
      const date = new Date(d.timestamp);
      // Для длинных периодов показываем дату+время, для коротких — только время
      if (activePeriod === '7d' || activePeriod === '30d' || activePeriod === 'all') {
        return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
      }
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    });
    const tempData = data.map(d => d.temperature);
    const humData = data.map(d => d.humidity);
    return { labels, tempData, humData };
  }

  // Обновление графика
  function updateChart(chart, labels, data, color, yMin, yMax) {
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].borderColor = color;
    if (yMin !== undefined && chart.options.scales?.y) {
      chart.options.scales.y.min = yMin;
      chart.options.scales.y.max = yMax;
    }
    chart.update();
  }

  // ===================== ИНИЦИАЛИЗАЦИЯ ГРАФИКОВ =====================

  function createSparkline(container) {
    const canvas = document.createElement('canvas');
    canvas.id = 'sparklineCanvas';
    container.innerHTML = '';
    container.appendChild(canvas);

    sparklineChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Температура',
          data: [],
          borderColor: currentColors.tempLine,
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true, mode: 'index', intersect: false }
        },
        scales: {
          x: { display: false },
          y: { display: false, min: 15, max: 35 }
        },
        animation: { duration: 300 }
      }
    });
  }

  function createTempChart(container) {
    const canvas = document.createElement('canvas');
    canvas.id = 'tempChartCanvas';
    container.innerHTML = '';
    container.appendChild(canvas);

    tempChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Температура (°C)',
          data: [],
          borderColor: currentColors.tempLine,
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, labels: { color: currentColors.text } },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          x: {
            grid: { color: currentColors.grid },
            ticks: { color: currentColors.text, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
          },
          y: {
            grid: { color: currentColors.grid },
            ticks: { color: currentColors.text, callback: v => v + '°' },
            min: 10,
            max: 40
          }
        }
      }
    });
  }

  function createHumChart(container) {
    const canvas = document.createElement('canvas');
    canvas.id = 'humChartCanvas';
    container.innerHTML = '';
    container.appendChild(canvas);

    humChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Влажность (%)',
          data: [],
          borderColor: currentColors.humLine,
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, labels: { color: currentColors.text } },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          x: {
            grid: { color: currentColors.grid },
            ticks: { color: currentColors.text, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
          },
          y: {
            grid: { color: currentColors.grid },
            ticks: { color: currentColors.text, callback: v => v + '%' },
            min: 0,
            max: 100
          }
        }
      }
    });
  }

  // ===================== ОБНОВЛЕНИЕ ДАННЫХ =====================

  async function refreshCharts(period) {
    activePeriod = period;
    const data = await loadData(period);
    if (!data || data.length === 0) {
      console.warn('Нет данных для отображения');
      if (tempChart) tempChart.data.labels = [];
      if (humChart) humChart.data.labels = [];
      if (sparklineChart) sparklineChart.data.labels = [];
      tempChart?.update();
      humChart?.update();
      sparklineChart?.update();
      return;
    }
    const { labels, tempData, humData } = prepareDatasets(data);

    if (tempChart) updateChart(tempChart, labels, tempData, currentColors.tempLine, 10, 40);
    if (humChart) updateChart(humChart, labels, humData, currentColors.humLine, 0, 100);

    // Спарклайн: последние 20 точек температуры
    if (sparklineChart) {
      const recent = data.slice(-20);
      const sparkLabels = recent.map(d => {
        const date = new Date(d.timestamp);
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      });
      const sparkTemp = recent.map(d => d.temperature);
      sparklineChart.data.labels = sparkLabels;
      sparklineChart.data.datasets[0].data = sparkTemp;
      sparklineChart.data.datasets[0].borderColor = currentColors.tempLine;
      sparklineChart.update();
    }
  }

  // ===================== СМЕНА ТЕМЫ =====================

  function updateChartColors() {
    currentColors = document.documentElement.classList.contains('dark') ? darkColors : lightColors;

    [tempChart, humChart, sparklineChart].forEach(chart => {
      if (!chart) return;
      if (chart.options.scales?.x) {
        chart.options.scales.x.grid.color = currentColors.grid;
        chart.options.scales.x.ticks.color = currentColors.text;
      }
      if (chart.options.scales?.y) {
        chart.options.scales.y.grid.color = currentColors.grid;
        chart.options.scales.y.ticks.color = currentColors.text;
      }
      if (chart.options.plugins?.legend) {
        chart.options.plugins.legend.labels.color = currentColors.text;
      }
      if (chart === tempChart || chart === sparklineChart) {
        chart.data.datasets[0].borderColor = currentColors.tempLine;
      } else if (chart === humChart) {
        chart.data.datasets[0].borderColor = currentColors.humLine;
      }
      chart.update();
    });
  }

  // Наблюдатель за сменой тёмной темы
  const observer = new MutationObserver(mutations => {
    mutations.forEach(mu => {
      if (mu.attributeName === 'class') {
        updateChartColors();
      }
    });
  });
  observer.observe(document.documentElement, { attributes: true });

  // ===================== ПРИВЯЗКА К ИНТЕРФЕЙСУ =====================

  function bindPeriodButtons() {
    const container = document.getElementById('history');
    if (!container) return;

    container.querySelectorAll('.period-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.textContent.trim();
        const periodMap = {
          '1ч': '1h', '6ч': '6h', '24ч': '24h', '7д': '7d', '30д': '30d'
        };
        const period = periodMap[text] || '1h';
        activePeriod = period;

        container.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        refreshCharts(period);
      });
    });
  }

  function bindSparklineClick() {
    const sparkContainer = document.querySelector('#overview .chart-placeholder');
    if (!sparkContainer) return;
    sparkContainer.style.cursor = 'pointer';
    sparkContainer.addEventListener('click', () => {
      const historyTabBtn = document.querySelector('.tab-btn[data-tab="history"]') ||
                            document.querySelector('.nav-item[data-tab="history"]');
      if (historyTabBtn) historyTabBtn.click();
    });
  }

  // ===================== ПУБЛИЧНЫЙ API =====================

  window.climatMonitorCharts = {
    resize: () => {
      tempChart?.resize();
      humChart?.resize();
      sparklineChart?.resize();
    },
    refresh: refreshCharts,
    getActivePeriod: () => activePeriod,
    updateTheme: updateChartColors
  };

  // ===================== ТОЧКА ВХОДА =====================

  document.addEventListener('DOMContentLoaded', () => {
    const placeholders = document.querySelectorAll('.chart-placeholder');
    if (placeholders.length < 3) {
      console.warn('Не найдены все контейнеры для графиков (ожидается 3: спарклайн, температура, влажность)');
    }

    if (placeholders[0]) createSparkline(placeholders[0]);
    if (placeholders[1]) createTempChart(placeholders[1]);
    if (placeholders[2]) createHumChart(placeholders[2]);

    refreshCharts('1h');
    bindPeriodButtons();
    bindSparklineClick();
    updateChartColors();
  });
})();