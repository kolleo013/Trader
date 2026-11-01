// ===== КОНФИГУРАЦИЯ =====
const API_BASE = '';
let currentTicker = 'SBER';
let currentTimeframe = '1d';
let isLoading = false;

// ===== ИНИЦИАЛИЗАЦИЯ =====
document.addEventListener('DOMContentLoaded', async () => {
    try {
        createParticles();
        await loadTickers();
        await loadDashboard();
        setupEventListeners();
        updateTime();
        setInterval(updateTime, 1000);
        showToast('Система запущена', 'success');
    } catch (err) {
        console.error('Init error:', err);
        showToast('Ошибка инициализации: ' + err.message, 'error');
    }
});

// ===== ЧАСТИЦЫ =====
function createParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    const colors = ['var(--accent)', 'var(--green)', 'var(--orange)'];

    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.width = (1 + Math.random() * 3) + 'px';
        particle.style.height = particle.style.width;
        particle.style.background = colors[i % 3];
        particle.style.animationDelay = Math.random() * 8 + 's';
        particle.style.animationDuration = (6 + Math.random() * 6) + 's';
        container.appendChild(particle);
    }
}

// ===== TOAST УВЕДОМЛЕНИЯ =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle'
    };

    toast.innerHTML = `<i class="fas ${icons[type]}"></i> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== ВРЕМЯ =====
function updateTime() {
    const now = new Date();
    const el = document.getElementById('currentTime');
    if (el) el.textContent = now.toLocaleString('ru-RU');
}

// ===== СОБЫТИЯ =====
function setupEventListeners() {
    // Навигация
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (isLoading) return;

            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');

            if (btn.dataset.tab === 'screener') await loadScreener();
            if (btn.dataset.tab === 'trades') await loadTrades();
        });
    });

    // Выбор тикера
    const tickerSelect = document.getElementById('tickerSelect');
    if (tickerSelect) {
        tickerSelect.addEventListener('change', async (e) => {
            currentTicker = e.target.value;
            document.getElementById('dashboardTitle').innerHTML =
                `Дашборд: <span class="ticker-highlight">${currentTicker}</span>`;
            await loadDashboard();
            showToast(`Переключено на ${currentTicker}`, 'info');
        });
    }

    // Табы графиков
    document.querySelectorAll('.chart-tab').forEach(tab => {
        tab.addEventListener('click', async () => {
            document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTimeframe = tab.dataset.timeframe;
            await loadChart(currentTicker, currentTimeframe);
        });
    });

    // Слайдеры
    const forecastRange = document.getElementById('forecastRange');
    if (forecastRange) {
        forecastRange.addEventListener('input', (e) => {
            document.getElementById('forecastVal').textContent = e.target.value;
        });
    }

    const confidenceRange = document.getElementById('confidenceRange');
    if (confidenceRange) {
        confidenceRange.addEventListener('input', (e) => {
            document.getElementById('confidenceVal').textContent = e.target.value;
        });
    }

    // Кнопка обновления
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('loading');
            await loadDashboard();
            refreshBtn.classList.remove('loading');
            showToast('Данные обновлены', 'success');
        });
    }

    // Кнопка сканирования
    const scanBtn = document.getElementById('scanBtn');
    if (scanBtn) {
        scanBtn.addEventListener('click', async () => {
            scanBtn.classList.add('scanning');
            scanBtn.innerHTML = '<i class="fas fa-spinner"></i> Сканирование...';
            await loadScreener();
            scanBtn.classList.remove('scanning');
            scanBtn.innerHTML = '<i class="fas fa-satellite-dish"></i> Сканировать рынок';
        });
    }

    // Модальное окно
    const modalClose = document.querySelector('.modal-close');
    if (modalClose) {
        modalClose.addEventListener('click', () => {
            document.getElementById('modal').classList.remove('active');
        });
    }

    const modal = document.getElementById('modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'modal') {
                e.target.classList.remove('active');
            }
        });
    }
}

// ===== ЗАГРУЗКА ТИКЕРОВ =====
async function loadTickers() {
    try {
        const res = await fetch(`${API_BASE}/api/tickers`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const tickers = await res.json();
        const select = document.getElementById('tickerSelect');
        if (select) {
            select.innerHTML = tickers.map(t => `<option value="${t}">${t}</option>`).join('');
        }
    } catch (err) {
        console.error('Load tickers error:', err);
        showToast('Не удалось загрузить список акций', 'error');
    }
}

// ===== ЗАГРУЗКА ДАШБОРДА =====
async function loadDashboard() {
    if (isLoading) return;
    isLoading = true;

    try {
        const titleEl = document.getElementById('dashboardTitle');
        if (titleEl) {
            titleEl.innerHTML = `Дашборд: <span class="ticker-highlight">${currentTicker}</span>`;
        }

        await Promise.all([
            loadChart(currentTicker, currentTimeframe),
            loadSignals(currentTicker),
            loadStats()
        ]);
    } catch (err) {
        console.error('Dashboard error:', err);
        showToast('Ошибка загрузки дашборда', 'error');
    } finally {
        isLoading = false;
    }
}

// ===== ЗАГРУЗКА ГРАФИКА =====
async function loadChart(ticker, timeframe) {
    try {
        const res = await fetch(`${API_BASE}/api/chart/${ticker}/${timeframe}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            console.warn('Chart data error:', data.error);
            return;
        }

        const dates = data.map(d => d.date);
        const layout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#d1d4dc', size: 11, family: 'Inter, sans-serif' },
            margin: { t: 30, b: 30, l: 50, r: 20 },
            showlegend: true,
            legend: { orientation: 'h', y: 1.05, font: { size: 10 } },
            xaxis: { rangeslider: { visible: false }, gridcolor: 'rgba(48,54,61,0.6)' },
            yaxis: { gridcolor: 'rgba(48,54,61,0.6)' }
        };

        // Свечной график
        Plotly.newPlot('priceChart', [{
            x: dates,
            open: data.map(d => d.open),
            high: data.map(d => d.high),
            low: data.map(d => d.low),
            close: data.map(d => d.close),
            type: 'candlestick',
            name: 'Цена',
            increasing: { line: { color: '#00d084' } },
            decreasing: { line: { color: '#ff4757' } }
        }, {
            x: dates,
            y: data.map(d => d.bb_upper),
            type: 'scatter',
            name: 'BB Upper',
            line: { color: 'rgba(100,149,237,0.5)', dash: 'dot', width: 1 }
        }, {
            x: dates,
            y: data.map(d => d.bb_lower),
            type: 'scatter',
            name: 'BB Lower',
            line: { color: 'rgba(100,149,237,0.5)', dash: 'dot', width: 1 },
            fill: 'tonexty',
            fillcolor: 'rgba(100,149,237,0.1)'
        }, {
            x: dates,
            y: data.map(d => d.sma_20),
            type: 'scatter',
            name: 'SMA 20',
            line: { color: 'orange', width: 1.5 }
        }, {
            x: dates,
            y: data.map(d => d.sma_50),
            type: 'scatter',
            name: 'SMA 50',
            line: { color: 'purple', width: 1.5 }
        }], { ...layout, height: 400 }, { responsive: true });

        // RSI
        Plotly.newPlot('rsiChart', [{
            x: dates,
            y: data.map(d => d.rsi),
            type: 'scatter',
            name: 'RSI',
            line: { color: 'purple', width: 2 }
        }], {
            ...layout,
            height: 150,
            yaxis: { range: [0, 100], gridcolor: 'rgba(48,54,61,0.6)' },
            shapes: [
                { type: 'line', y0: 70, y1: 70, x0: dates[0], x1: dates[dates.length-1], line: { color: 'red', dash: 'dash' } },
                { type: 'line', y0: 30, y1: 30, x0: dates[0], x1: dates[dates.length-1], line: { color: 'green', dash: 'dash' } }
            ]
        }, { responsive: true });

        // MACD
        const macdColors = data.map(d => d.macd_hist >= 0 ? '#00d084' : '#ff4757');
        Plotly.newPlot('macdChart', [{
            x: dates,
            y: data.map(d => d.macd),
            type: 'scatter',
            name: 'MACD',
            line: { color: 'blue', width: 2 }
        }, {
            x: dates,
            y: data.map(d => d.macd_signal),
            type: 'scatter',
            name: 'Signal',
            line: { color: 'red', width: 2 }
        }, {
            x: dates,
            y: data.map(d => d.macd_hist),
            type: 'bar',
            name: 'Histogram',
            marker: { color: macdColors, opacity: 0.5 }
        }], { ...layout, height: 150 }, { responsive: true });

        // Объём
        const volColors = data.map(d => d.close >= d.open ? '#00d084' : '#ff4757');
        Plotly.newPlot('volumeChart', [{
            x: dates,
            y: data.map(d => d.volume),
            type: 'bar',
            name: 'Объём',
            marker: { color: volColors, opacity: 0.6 }
        }], { ...layout, height: 120 }, { responsive: true });

    } catch (err) {
        console.error('Chart error:', err);
    }
}

// ===== ЗАГРУЗКА СИГНАЛОВ =====
async function loadSignals(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/signals/${ticker}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            console.warn('Signals error:', data.error);
            return;
        }

        renderSignalBlock('signals1d', data.signals_1d);
        renderSignalBlock('signals1h', data.signals_1h);
        renderFinalForecast(data.signals_1d, data.signals_1h);
    } catch (err) {
        console.error('Signals error:', err);
    }
}

function renderSignalBlock(containerId, signals) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const metrics = container.querySelector('.signal-metrics');
    const details = container.querySelector('.signal-details');

    if (!metrics || !details) return;

    metrics.innerHTML = `
        <div class="signal-metric">
            <div class="value" style="color: var(--green)">${signals.positive || 0}</div>
            <div class="label">Позитив</div>
        </div>
        <div class="signal-metric">
            <div class="value" style="color: var(--red)">${signals.negative || 0}</div>
            <div class="label">Негатив</div>
        </div>
        <div class="signal-metric">
            <div class="value" style="color: var(--orange)">${signals.neutral || 0}</div>
            <div class="label">Нейтрал</div>
        </div>
        <div class="signal-metric">
            <div class="value" style="font-size:12px; color: ${signals.forecast_ru === 'РОСТ' ? 'var(--green)' : 'var(--red)'}">${signals.forecast_ru || 'N/A'}</div>
            <div class="label">Прогноз</div>
        </div>
    `;

    if (signals.details && signals.details.length > 0) {
        details.innerHTML = signals.details.map(d => {
            const icon = d.signal === 'positive' ? '✅' : d.signal === 'negative' ? '❌' : '⚖️';
            return `
                <div class="signal-row">
                    <span>${icon} ${d.indicator}</span>
                    <span style="color: var(--text-secondary); font-size: 11px;">${d.description}</span>
                </div>
            `;
        }).join('');
    } else {
        details.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">Нет данных</div>';
    }
}

function renderFinalForecast(sig1d, sig1h) {
    const totalPos = (sig1d.positive || 0) + (sig1h.positive || 0);
    const totalNeg = (sig1d.negative || 0) + (sig1h.negative || 0);
    const totalNeu = (sig1d.neutral || 0) + (sig1h.neutral || 0);
    const total = totalPos + totalNeg + totalNeu;
    const score = total > 0 ? ((totalPos - totalNeg) / total * 100).toFixed(1) : 0;

    const angle = (score / 100) * 90 - 90;
    const gaugeFill = document.getElementById('gaugeFill');
    const gaugeValue = document.getElementById('gaugeValue');

    if (gaugeFill) gaugeFill.style.transform = `translateX(-50%) rotate(${angle}deg)`;
    if (gaugeValue) {
        gaugeValue.textContent = score;
        gaugeValue.style.color = score > 30 ? 'var(--green)' : score < -30 ? 'var(--red)' : 'var(--orange)';
    }

    const rec = document.getElementById('forecastRec');
    if (!rec) return;

    if (score > 30) {
        rec.className = 'forecast-recommendation bullish';
        rec.innerHTML = `<h4>📈 СИЛЬНЫЙ БЫЧИЙ СИГНАЛ</h4><p>Score: ${score}% | Позитивных: ${totalPos} | Негативных: ${totalNeg}</p><p><strong>Действие:</strong> Рассмотреть покупку</p>`;
    } else if (score < -30) {
        rec.className = 'forecast-recommendation bearish';
        rec.innerHTML = `<h4>📉 СИЛЬНЫЙ МЕДВЕЖИЙ СИГНАЛ</h4><p>Score: ${score}% | Позитивных: ${totalPos} | Негативных: ${totalNeg}</p><p><strong>Действие:</strong> Избегать покупки</p>`;
    } else {
        rec.className = 'forecast-recommendation neutral';
        rec.innerHTML = `<h4>⚖️ НЕЙТРАЛЬНЫЙ СИГНАЛ</h4><p>Score: ${score}% | Позитивных: ${totalPos} | Негативных: ${totalNeg}</p><p><strong>Действие:</strong> Ждать сигнала</p>`;
    }
}

// ===== СКРИНЕР =====
async function loadScreener() {
    if (isLoading) return;
    isLoading = true;

    const tbody = document.getElementById('screenerBody');
    if (!tbody) {
        isLoading = false;
        return;
    }

    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 60px;"><div style="display:flex;flex-direction:column;align-items:center;gap:16px;"><i class="fas fa-satellite-dish" style="font-size:32px;color:var(--green);animation:spin 2s linear infinite;"></i><span style="color:var(--text-secondary);">Сканирование рынка... Это может занять 1-2 минуты</span></div></td></tr>';

    try {
        const res = await fetch(`${API_BASE}/api/screener`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color: var(--red); padding: 40px;">Ошибка: ${data.error}</td></tr>`;
            return;
        }

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 40px;">Нет данных</td></tr>';
            return;
        }

        tbody.innerHTML = data.map((item, idx) => {
            const scoreClass = item.score > 0 ? 'score-positive' : item.score < 0 ? 'score-negative' : 'score-neutral';
            const aiText = item.ai_prediction ? `${item.ai_prediction.prediction} (${(item.ai_prediction.confidence*100).toFixed(0)}%)` : '-';

            return `
                <tr style="animation: fadeIn 0.3s ease ${idx * 0.05}s both;">
                    <td style="color: var(--text-secondary);">${idx + 1}</td>
                    <td><strong>${item.ticker}</strong></td>
                    <td class="${scoreClass}">${item.score > 0 ? '+' : ''}${item.score}%</td>
                    <td>
                        <span style="
                            color: ${item.forecast_1d === 'РОСТ' ? 'var(--green)' : 'var(--red)'};
                            font-size: 12px;
                            font-weight: 600;
                            padding: 4px 8px;
                            border-radius: 4px;
                            background: ${item.forecast_1d === 'РОСТ' ? 'rgba(0,208,132,0.1)' : 'rgba(255,71,87,0.1)'}
                        ">${item.forecast_1d || '-'}</span>
                    </td>
                    <td>
                        <span style="
                            color: ${item.forecast_1h === 'РОСТ' ? 'var(--green)' : 'var(--red)'};
                            font-size: 12px;
                            font-weight: 600;
                            padding: 4px 8px;
                            border-radius: 4px;
                            background: ${item.forecast_1h === 'РОСТ' ? 'rgba(0,208,132,0.1)' : 'rgba(255,71,87,0.1)'}
                        ">${item.forecast_1h || '-'}</span>
                    </td>
                    <td style="
                        color: ${item.rsi > 70 ? 'var(--red)' : item.rsi < 30 ? 'var(--green)' : 'var(--text-primary)'};
                        font-family: 'JetBrains Mono', monospace;
                    ">${item.rsi || '-'}</td>
                    <td style="font-family: 'JetBrains Mono', monospace;">${item.price ? item.price.toFixed(2) + '₽' : '-'}</td>
                    <td>${aiText}</td>
                    <td><button class="detail-btn" onclick="showDetails('${item.ticker}')">Детали</button></td>
                </tr>
            `;
        }).join('');

        showToast(`Найдено ${data.length} акций`, 'success');

    } catch (err) {
        console.error('Screener error:', err);
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--red); padding: 40px;">Ошибка загрузки. Попробуйте ещё раз.</td></tr>';
        showToast('Ошибка сканирования', 'error');
    } finally {
        isLoading = false;
    }
}

// ===== ДЕТАЛИ =====
async function showDetails(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/signals/${ticker}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            showToast('Ошибка: ' + data.error, 'error');
            return;
        }

        const modal = document.getElementById('modal');
        const body = document.getElementById('modalBody');

        if (!modal || !body) return;

        body.innerHTML = `
            <h2 style="margin-bottom:20px; font-size:22px;">📊 ${ticker} — Детальный анализ</h2>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px">
                <div>
                    <h4 style="margin-bottom:12px; color:var(--text-secondary);">📅 1 День</h4>
                    ${renderSignalTable(data.signals_1d)}
                </div>
                <div>
                    <h4 style="margin-bottom:12px; color:var(--text-secondary);">⏰ 1 Час</h4>
                    ${renderSignalTable(data.signals_1h)}
                </div>
            </div>
            ${data.ai_prediction ? `
                <div style="margin-top:20px;padding:18px;background:var(--bg-tertiary);border-radius:12px;border:1px solid var(--border)">
                    <h4 style="margin-bottom:10px;">🤖 Прогноз ИИ</h4>
                    <p style="color:var(--text-secondary);font-size:14px;">Прогноз: <strong style="color:var(--green);">${data.ai_prediction.prediction}</strong></p>
                    <p style="color:var(--text-secondary);font-size:14px;">Вероятность покупки: <strong>${data.ai_prediction.probability_buy.toFixed(1)}%</strong></p>
                    <p style="color:var(--text-secondary);font-size:14px;">Уверенность: <strong>${(data.ai_prediction.confidence*100).toFixed(1)}%</strong></p>
                </div>
            ` : ''}
        `;

        modal.classList.add('active');
    } catch (err) {
        console.error('Details error:', err);
        showToast('Не удалось загрузить детали', 'error');
    }
}

function renderSignalTable(signals) {
    if (!signals || signals.error) {
        return '<div style="color: var(--text-secondary); padding: 20px; text-align: center;">Нет данных</div>';
    }

    return `
        <div style="margin-bottom:12px">
            <div style="display:flex;gap:12px;margin-bottom:12px">
                <span style="color:var(--green);font-weight:700;">✅ ${signals.positive || 0}</span>
                <span style="color:var(--red);font-weight:700;">❌ ${signals.negative || 0}</span>
                <span style="color:var(--orange);font-weight:700;">⚖️ ${signals.neutral || 0}</span>
            </div>
            ${signals.details && signals.details.length > 0 ? signals.details.map(d => {
                const icon = d.signal === 'positive' ? '✅' : d.signal === 'negative' ? '❌' : '⚖️';
                return `<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;display:flex;justify-content:space-between;">
                    <span>${icon} <strong>${d.indicator}</strong></span>
                    <span style="color:var(--text-secondary);">${d.description}</span>
                </div>`;
            }).join('') : '<div style="color: var(--text-secondary);">Нет деталей</div>'}
        </div>
    `;
}

// ===== СДЕЛКИ =====
async function loadTrades() {
    const tbody = document.getElementById('tradesBody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px;">⏳ Загрузка...</td></tr>';

    try {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 60px; color: var(--text-secondary);"><i class="fas fa-tools" style="font-size:32px;margin-bottom:12px;display:block;"></i>Раздел в разработке</td></tr>';
    } catch (err) {
        console.error('Trades error:', err);
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: var(--red); padding: 40px;">Ошибка загрузки</td></tr>';
    }
}

// ===== СТАТИСТИКА =====
async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const stats = await res.json();

        const totalTrades = document.getElementById('totalTrades');
        const winRate = document.getElementById('winRate');
        const totalProfit = document.getElementById('totalProfit');

        if (totalTrades) {
            animateValue(totalTrades, 0, stats.total_trades || 0, 1000);
        }
        if (winRate) {
            winRate.textContent = `${(stats.win_rate || 0).toFixed(1)}%`;
        }
        if (totalProfit) {
            const profit = stats.total_profit || 0;
            totalProfit.textContent = `${profit > 0 ? '+' : ''}${profit.toFixed(2)}₽`;
            totalProfit.style.color = profit > 0 ? 'var(--green)' : 'var(--red)';
        }
    } catch (err) {
        console.error('Stats error:', err);
    }
}

// ===== АНИМАЦИЯ ЧИСЕЛ =====
function animateValue(element, start, end, duration) {
    const range = end - start;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + range * easeProgress);

        element.textContent = current.toLocaleString('ru-RU');

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}
