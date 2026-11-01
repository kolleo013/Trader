// Конфигурация
const API_BASE = '';
let currentTicker = 'SBER';
let currentTimeframe = '1d';
let isLoading = false;

// Инициализация
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadTickers();
        await loadDashboard();
        setupEventListeners();
        updateTime();
        setInterval(updateTime, 1000);
    } catch (err) {
        console.error('Init error:', err);
        showError('Ошибка инициализации: ' + err.message);
    }
});

function updateTime() {
    const now = new Date();
    document.getElementById('currentTime').textContent = 
        now.toLocaleString('ru-RU');
}

function setupEventListeners() {
    // Навигация
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (isLoading) return; // Предотвращаем множественные клики
            
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
            
            if (btn.dataset.tab === 'screener') await loadScreener();
            if (btn.dataset.tab === 'trades') await loadTrades();
        });
    });
    
    // Выбор тикера
    document.getElementById('tickerSelect').addEventListener('change', async (e) => {
        currentTicker = e.target.value;
        await loadDashboard();
    });
    
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
    document.getElementById('forecastRange').addEventListener('input', (e) => {
        document.getElementById('forecastVal').textContent = e.target.value;
    });
    
    document.getElementById('confidenceRange').addEventListener('input', (e) => {
        document.getElementById('confidenceVal').textContent = e.target.value;
    });
    
    // Кнопки обновления
    document.getElementById('refreshBtn').addEventListener('click', async () => {
        await loadDashboard();
    });
    
    document.getElementById('scanBtn').addEventListener('click', async () => {
        await loadScreener();
    });
    
    // Модальное окно
    document.querySelector('.modal-close').addEventListener('click', () => {
        document.getElementById('modal').classList.remove('active');
    });
    
    // Закрытие модалки по клику вне её
    document.getElementById('modal').addEventListener('click', (e) => {
        if (e.target.id === 'modal') {
            e.target.classList.remove('active');
        }
    });
}

async function loadTickers() {
    try {
        const res = await fetch(`${API_BASE}/api/tickers`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const tickers = await res.json();
        const select = document.getElementById('tickerSelect');
        select.innerHTML = tickers.map(t => `<option value="${t}">${t}</option>`).join('');
    } catch (err) {
        console.error('Load tickers error:', err);
        showError('Не удалось загрузить список акций');
    }
}

async function loadDashboard() {
    if (isLoading) return;
    isLoading = true;
    
    try {
        document.getElementById('dashboardTitle').textContent = `Дашборд: ${currentTicker}`;
        await Promise.all([
            loadChart(currentTicker, currentTimeframe),
            loadSignals(currentTicker),
            loadStats()
        ]);
    } catch (err) {
        console.error('Dashboard error:', err);
        showError('Ошибка загрузки дашборда');
    } finally {
        isLoading = false;
    }
}

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
            font: { color: '#d1d4dc', size: 11 },
            margin: { t: 30, b: 30, l: 50, r: 20 },
            showlegend: true,
            legend: { orientation: 'h', y: 1.05, font: { size: 10 } },
            xaxis: { rangeslider: { visible: false }, gridcolor: '#2a2e39' },
            yaxis: { gridcolor: '#2a2e39' }
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
            yaxis: { range: [0, 100], gridcolor: '#2a2e39' },
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
            <div class="value">${signals.forecast_ru || 'N/A'}</div>
            <div class="label">Прогноз</div>
        </div>
    `;
    
    if (signals.details && signals.details.length > 0) {
        details.innerHTML = signals.details.map(d => {
            const icon = d.signal === 'positive' ? '✅' : d.signal === 'negative' ? '❌' : '⚖️';
            return `
                <div class="signal-row">
                    <span>${icon} ${d.indicator}</span>
                    <span style="color: var(--text-secondary)">${d.description}</span>
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
    if (gaugeValue) gaugeValue.textContent = score;
    
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
        rec.innerHTML = `<h4>️ НЕЙТРАЛЬНЫЙ СИГНАЛ</h4><p>Score: ${score}% | Позитивных: ${totalPos} | Негативных: ${totalNeg}</p><p><strong>Действие:</strong> Ждать сигнала</p>`;
    }
}

async function loadScreener() {
    if (isLoading) return;
    isLoading = true;
    
    const tbody = document.getElementById('screenerBody');
    if (!tbody) {
        isLoading = false;
        return;
    }
    
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 40px;">⏳ Загрузка данных... Это может занять 1-2 минуты</td></tr>';
    
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
                <tr>
                    <td>${idx + 1}</td>
                    <td><strong>${item.ticker}</strong></td>
                    <td class="${scoreClass}">${item.score}%</td>
                    <td>${item.forecast_1d || '-'}</td>
                    <td>${item.forecast_1h || '-'}</td>
                    <td>${item.rsi || '-'}</td>
                    <td>${item.price ? item.price.toFixed(2) + '₽' : '-'}</td>
                    <td>${aiText}</td>
                    <td><button class="detail-btn" onclick="showDetails('${item.ticker}')">Детали</button></td>
                </tr>
            `;
        }).join('');
        
    } catch (err) {
        console.error('Screener error:', err);
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--red); padding: 40px;">Ошибка загрузки. Попробуйте ещё раз.</td></tr>';
    } finally {
        isLoading = false;
    }
}

async function showDetails(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/signals/${ticker}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        if (data.error) {
            showError('Ошибка: ' + data.error);
            return;
        }
        
        const modal = document.getElementById('modal');
        const body = document.getElementById('modalBody');
        
        if (!modal || !body) return;
        
        body.innerHTML = `
            <h2> ${ticker} — Детальный анализ</h2>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px">
                <div>
                    <h4>📅 1 День</h4>
                    ${renderSignalTable(data.signals_1d)}
                </div>
                <div>
                    <h4> 1 Час</h4>
                    ${renderSignalTable(data.signals_1h)}
                </div>
            </div>
            ${data.ai_prediction ? `
                <div style="margin-top:20px;padding:16px;background:var(--bg-tertiary);border-radius:8px">
                    <h4>🤖 Прогноз ИИ</h4>
                    <p>Прогноз: <strong>${data.ai_prediction.prediction}</strong></p>
                    <p>Вероятность покупки: ${data.ai_prediction.probability_buy.toFixed(1)}%</p>
                    <p>Уверенность: ${(data.ai_prediction.confidence*100).toFixed(1)}%</p>
                </div>
            ` : ''}
        `;
        
        modal.classList.add('active');
    } catch (err) {
        console.error('Details error:', err);
        showError('Не удалось загрузить детали');
    }
}

function renderSignalTable(signals) {
    if (!signals || signals.error) {
        return '<div style="color: var(--text-secondary); padding: 20px; text-align: center;">Нет данных</div>';
    }
    
    return `
        <div style="margin-bottom:12px">
            <div style="display:flex;gap:8px;margin-bottom:12px">
                <span style="color:var(--green)">✅ ${signals.positive || 0}</span>
                <span style="color:var(--red)">❌ ${signals.negative || 0}</span>
                <span style="color:var(--orange)">⚖️ ${signals.neutral || 0}</span>
            </div>
            ${signals.details && signals.details.length > 0 ? signals.details.map(d => {
                const icon = d.signal === 'positive' ? '✅' : d.signal === 'negative' ? '❌' : '⚖️';
                return `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">
                    ${icon} <strong>${d.indicator}</strong> — ${d.description}
                </div>`;
            }).join('') : '<div style="color: var(--text-secondary);">Нет деталей</div>'}
        </div>
    `;
}

async function loadTrades() {
    const tbody = document.getElementById('tradesBody');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px;">⏳ Загрузка...</td></tr>';
    
    try {
        // Пока заглушка — можно добавить API endpoint
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px; color: var(--text-secondary);">Раздел в разработке</td></tr>';
    } catch (err) {
        console.error('Trades error:', err);
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: var(--red); padding: 40px;">Ошибка загрузки</td></tr>';
    }
}

async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const stats = await res.json();
        
        const totalTrades = document.getElementById('totalTrades');
        const winRate = document.getElementById('winRate');
        const totalProfit = document.getElementById('totalProfit');
        
        if (totalTrades) totalTrades.textContent = stats.total_trades || 0;
        if (winRate) winRate.textContent = `${(stats.win_rate || 0).toFixed(1)}%`;
        if (totalProfit) totalProfit.textContent = `${(stats.total_profit || 0).toFixed(2)}₽`;
    } catch (err) {
        console.error('Stats error:', err);
    }
}

function showError(message) {
    console.error(message);
    // Можно добавить красивое уведомление
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--red);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Добавляем анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);