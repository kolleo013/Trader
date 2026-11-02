const CONFIG = { API_BASE: '', REFRESH_INTERVAL: 30000 };

const state = {
  currentTicker: 'SBER', currentTab: 'dashboard', currentTF: '1d', chartType: 'candle',
  tickers: [], screenerData: [], newsData: [], lastPriceData: []
};

function initBackgroundParticles() {
  const canvas = document.getElementById('bgCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let width, height, particles = [];
  function resize() { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; }
  resize();
  window.addEventListener('resize', resize);
  const PARTICLE_COUNT = 60;
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({ x: Math.random() * width, y: Math.random() * height, vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3, size: Math.random() * 2 + 0.5, alpha: Math.random() * 0.5 + 0.1 });
  }
  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = width; if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height; if (p.y > height) p.y = 0;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 208, 132, ${p.alpha})`; ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(0, 208, 132, 0.8)'; ctx.fill();
    });
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y); ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 208, 132, ${0.08 * (1 - dist / 120)})`; ctx.lineWidth = 0.5; ctx.shadowBlur = 0; ctx.stroke();
        }
      }
    }
    requestAnimationFrame(animate);
  }
  animate();
}

function initRevealAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

document.addEventListener('DOMContentLoaded', () => {
  initBackgroundParticles(); initNavigation(); initTimeframeSelector(); initChartTypeSelector(); initTickerSelector();
  updateTime(); setInterval(updateTime, 60000); loadInitialData();
  setInterval(() => {
    if (state.currentTab === 'dashboard') loadTickerData(state.currentTicker);
    else if (state.currentTab === 'screener') loadScreenerData();
    else if (state.currentTab === 'news') loadNewsData();
  }, CONFIG.REFRESH_INTERVAL);
  setTimeout(initRevealAnimations, 100);
});

function updateTime() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  document.querySelectorAll('.current-time').forEach(el => el.textContent = timeStr);
}

async function loadInitialData() {
  try {
    await loadTickers(); await loadScreenerData(); await loadNewsData(); await loadTickerData(state.currentTicker);
    updateQuickOverview(); setTimeout(initRevealAnimations, 200);
  } catch (err) { console.error('Ошибка загрузки:', err); showError('Не удалось загрузить данные с сервера'); }
}

function showError(message) {
  const toast = document.createElement('div'); toast.className = 'error-toast'; toast.textContent = message;
  document.body.appendChild(toast); setTimeout(() => toast.remove(), 5000);
}

function initNavigation() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      document.getElementById(tab).classList.add('active');
      state.currentTab = tab;
      
      if (tab === 'screener') loadScreenerData();
      if (tab === 'news') {
        console.log('🔄 Переключение на вкладку Новости');
        loadNewsData();
      }
      setTimeout(initRevealAnimations, 100);
    });
  });
  document.querySelectorAll('.menu-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.toggle('open');
    });
  });
}

function initTimeframeSelector() {
  document.querySelectorAll('.timeframe-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.timeframe-btn').forEach(b => b.classList.remove('active')); btn.classList.add('active');
      state.currentTF = btn.dataset.timeframe; loadTickerData(state.currentTicker);
    });
  });
}

function initChartTypeSelector() {
  document.querySelectorAll('.chart-type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.chart-type-btn').forEach(b => b.classList.remove('active')); btn.classList.add('active');
      state.chartType = btn.dataset.type; if (state.lastPriceData.length > 0) drawPriceChart(state.lastPriceData);
    });
  });
}

function initTickerSelector() {
  const select = document.getElementById('tickerSelect');
  select.addEventListener('change', (e) => { state.currentTicker = e.target.value; loadTickerData(state.currentTicker); updateQuickOverview(); });
}

async function fetchAPI(endpoint) {
  const res = await fetch(`${CONFIG.API_BASE}${endpoint}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function loadTickers() { const data = await fetchAPI('/api/tickers'); state.tickers = data; renderTickerSelector(); }

async function loadTickerData(ticker) {
  try {
    const data = await fetchAPI(`/api/ticker/${ticker}?tf=${state.currentTF}`);
    if (data.error) { showError(data.error); return; }
    state.lastPriceData = data.price_history || [];
    updateDashboard(data); drawCharts(data);
  } catch (err) { console.error('Ошибка загрузки тикера:', err); showError('Не удалось загрузить данные тикера'); }
}

async function loadScreenerData() {
  try { const data = await fetchAPI('/api/screener'); state.screenerData = data; renderScreener(data); updateQuickOverview(); }
  catch (err) { console.error('Ошибка скринера:', err); showError('Не удалось загрузить скринер'); }
}

async function loadNewsData() {
  try {
    console.log('📡 Загрузка новостей...');
    const data = await fetchAPI('/api/news');
    console.log('📰 Получено новостей:', data?.length || 0);
    
    state.newsData = data || [];
    renderNews(state.newsData);
  } catch (err) {
    console.error('❌ Ошибка загрузки новостей:', err);
    showError('Не удалось загрузить новости');
  }
}

function adjustColor(hex, amount) {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.min(255, Math.max(0, (num >> 16) + amount));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
  const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
  return `#${(r << 16 | g << 8 | b).toString(16).padStart(6, '0')}`;
}

function updateDashboard(data) {
  const tickerInfo = state.tickers.find(t => t.ticker === state.currentTicker);
  const name = tickerInfo?.name || state.currentTicker;
  const color = tickerInfo?.color || '#2962ff';
  const logoPath = tickerInfo?.logo || '';
  document.getElementById('stockName').textContent = `${state.currentTicker} — ${name}`;
  
  const logoEl = document.getElementById('companyLogo');
  const letterEl = document.getElementById('logoLetter');
  const logoImg = document.getElementById('companyLogoImg');
  if (logoPath) {
    logoImg.src = logoPath; logoImg.style.display = 'block'; letterEl.style.display = 'none';
  } else {
    logoEl.style.background = `linear-gradient(135deg, ${color}, ${adjustColor(color, -30)})`;
    letterEl.textContent = state.currentTicker.charAt(0); logoImg.style.display = 'none'; letterEl.style.display = 'flex';
  }
  
  document.getElementById('currentPrice').textContent = `${data.price?.toFixed(2) || 0} ₽`;
  const change = data.change || 0; const changePercent = data.change_percent || 0; const isPositive = change >= 0;
  const priceChangeEl = document.getElementById('priceChangePercent');
  priceChangeEl.textContent = `${Math.abs(changePercent).toFixed(2)}%`;
  const priceChangeParent = priceChangeEl.parentElement;
  priceChangeParent.className = `price-change ${isPositive ? 'positive' : 'negative'}`;
  const arrow = priceChangeParent.querySelector('i'); if (arrow) arrow.className = isPositive ? 'fas fa-arrow-up' : 'fas fa-arrow-down';
  const deltaEl = document.getElementById('priceDelta');
  deltaEl.textContent = `${isPositive ? '+' : ''}${change.toFixed(2)} ₽`; deltaEl.className = `card-delta ${isPositive ? 'positive' : 'negative'}`;
  document.getElementById('volume').textContent = data.volume || '0M'; document.getElementById('marketCap').textContent = data.market_cap || '—';
  
  const rsi = data.rsi || 50; document.getElementById('rsiValue').textContent = rsi.toFixed(1); document.getElementById('rsiFill').style.width = `${rsi}%`;
  const rsiStatus = document.querySelector('.rsi-status');
  if (rsi > 70) { rsiStatus.className = 'rsi-status negative'; rsiStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> Перекупленность'; }
  else if (rsi < 30) { rsiStatus.className = 'rsi-status positive'; rsiStatus.innerHTML = '<i class="fas fa-check-circle"></i> Перепроданность'; }
  else { rsiStatus.className = 'rsi-status positive'; rsiStatus.innerHTML = '<i class="fas fa-check-circle"></i> Нормальная зона'; }
  
  const aiSignal = data.ai_prediction?.prediction || 'HOLD';
  const confidence = data.ai_prediction?.confidence || 50;
  const buyProb = data.ai_prediction?.buy_probability || 50;
  const signalEl = document.getElementById('aiSignal'); signalEl.textContent = aiSignal; signalEl.parentElement.className = `ai-signal ${aiSignal.toLowerCase()}`;
  document.getElementById('buyProbability').textContent = `${buyProb.toFixed(1)}%`;
  document.getElementById('modelConfidence').textContent = `${confidence.toFixed(0)}%`;
  document.getElementById('confidenceFill').style.width = `${confidence}%`;
  
  const score = data.score || 0; const scoreNorm = (score + 100) / 200; const maxOffset = 251.2; const offset = maxOffset * (1 - scoreNorm);
  const gaugeFill = document.getElementById('scoreGauge');
  gaugeFill.style.strokeDasharray = maxOffset; gaugeFill.style.strokeDashoffset = offset; gaugeFill.style.stroke = score > 0 ? '#00d084' : '#ff4757';
  document.getElementById('scoreValue').textContent = `${score > 0 ? '+' : ''}${score}`;
  const scoreLabel = document.querySelector('.score-label');
  if (score > 20) { scoreLabel.className = 'score-label positive'; scoreLabel.innerHTML = '<i class="fas fa-chart-line"></i> Бычий сигнал'; }
  else if (score < -20) { scoreLabel.className = 'score-label negative'; scoreLabel.innerHTML = '<i class="fas fa-chart-line"></i> Медвежий сигнал'; }
  else { scoreLabel.className = 'score-label'; scoreLabel.innerHTML = '<i class="fas fa-minus"></i> Нейтральный сигнал'; }
  
  updateIndicators('1d', data.signals_1d); updateIndicators('1h', data.signals_1h); updateRecommendation(data);

    updateIndicators('1d', data.signals_1d);
  updateIndicators('1h', data.signals_1h);
  updateRecommendation(data);
  
  // НОВОЕ: Загружаем новости для конкретной акции
  loadTickerNews(state.currentTicker);
}

function updateIndicators(tf, signals) {
  if (!signals || !Array.isArray(signals)) return;
  const positive = signals.filter(s => s.signal === 'positive').length;
  const negative = signals.filter(s => s.signal === 'negative').length;
  const neutral = signals.filter(s => s.signal === 'neutral').length;
  const posEl = document.getElementById(`positive${tf}`), negEl = document.getElementById(`negative${tf}`), neuEl = document.getElementById(`neutral${tf}`);
  if (posEl) posEl.textContent = positive; if (negEl) negEl.textContent = negative; if (neuEl) neuEl.textContent = neutral;
  const total = signals.length; const score = total > 0 ? ((positive - negative) / total * 100).toFixed(0) : 0;
  const scoreEl = document.getElementById(`score${tf}`);
  if (scoreEl) { scoreEl.textContent = `Score: ${score}%`; scoreEl.className = `score-badge ${score > 0 ? 'positive' : 'negative'}`; }
  const list = document.getElementById(`indicators${tf}`);
  if (list) {
    list.innerHTML = signals.map(s => `<div class="indicator-item"><div><div style="font-weight: 600;">${s.indicator}</div><div style="font-size: 11px; color: var(--text-muted);">${s.description || ''}</div></div><div class="signal ${s.signal}">${s.value || ''}</div></div>`).join('');
  }
}

function updateRecommendation(data) {
  const signals = data.signals_1d || [];
  const positive = signals.filter(s => s.signal === 'positive').length;
  const negative = signals.filter(s => s.signal === 'negative').length;
  const neutral = signals.filter(s => s.signal === 'neutral').length;
  const posEl = document.getElementById('totalPositive'), negEl = document.getElementById('totalNegative'), neuEl = document.getElementById('totalNeutral');
  if (posEl) posEl.textContent = positive; if (negEl) negEl.textContent = negative; if (neuEl) neuEl.textContent = neutral;
  const box = document.querySelector('.recommendation-box'), title = document.getElementById('recTitle'), text = document.getElementById('recText');
  if (positive >= 4) { box.className = 'recommendation-box strong-buy'; title.textContent = 'СИЛЬНЫЙ БЫЧИЙ СИГНАЛ'; title.style.color = ''; text.textContent = 'Рассмотреть покупку на откатах. Стоп-лосс ниже ближайшей поддержки.'; }
  else if (positive >= 3) { box.className = 'recommendation-box strong-buy'; title.textContent = 'БЫЧИЙ СИГНАЛ'; title.style.color = ''; text.textContent = 'Умеренно позитивная картина. Можно рассмотреть частичное открытие позиции.'; }
  else if (negative >= 4) { box.className = 'recommendation-box strong-sell'; title.textContent = 'СИЛЬНЫЙ МЕДВЕЖИЙ СИГНАЛ'; title.style.color = ''; text.textContent = 'Рекомендуется воздержаться от покупки или рассмотреть шорт.'; }
  else if (negative >= 3) { box.className = 'recommendation-box strong-sell'; title.textContent = 'МЕДВЕЖИЙ СИГНАЛ'; title.style.color = ''; text.textContent = 'Негативная картина. Лучше подождать улучшения ситуации.'; }
  else { box.className = 'recommendation-box'; box.style.background = 'var(--bg-hover)'; title.textContent = 'НЕЙТРАЛЬНЫЙ СИГНАЛ'; title.style.color = 'var(--text-secondary)'; text.textContent = 'Рынок в боковом движении. Рекомендуется наблюдение.'; }
}

function drawCharts(data) {
  setTimeout(() => { drawRSIChart(data.rsi_history || []); drawMACDChart(data.macd_history || []); drawPriceChart(data.price_history || []); }, 50);
}

function drawRSIChart(history) {
  const canvas = document.getElementById('rsiChart'); if (!canvas) return;
  const ctx = canvas.getContext('2d'); const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width; canvas.height = rect.height; ctx.clearRect(0, 0, canvas.width, canvas.height);
  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const chartWidth = canvas.width - padding.left - padding.right, chartHeight = canvas.height - padding.top - padding.bottom;
  ctx.strokeStyle = '#2b3139'; ctx.lineWidth = 1;
  const yLabels = [0, 25, 50, 75, 100];
  yLabels.forEach(val => {
    const y = padding.top + chartHeight - (val / 100) * chartHeight;
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(canvas.width - padding.right, y); ctx.stroke();
    ctx.fillStyle = '#848e9c'; ctx.font = '11px Inter'; ctx.textAlign = 'right'; ctx.fillText(val, padding.left - 10, y + 4);
  });
  const y30 = padding.top + chartHeight - (30 / 100) * chartHeight, y70 = padding.top + chartHeight - (70 / 100) * chartHeight;
  ctx.strokeStyle = '#00d084'; ctx.setLineDash([5, 5]); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(padding.left, y30); ctx.lineTo(canvas.width - padding.right, y30); ctx.stroke();
  ctx.strokeStyle = '#ff4757'; ctx.beginPath(); ctx.moveTo(padding.left, y70); ctx.lineTo(canvas.width - padding.right, y70); ctx.stroke(); ctx.setLineDash([]);
  if (history.length > 1) {
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)'); gradient.addColorStop(1, 'rgba(139, 92, 246, 0)');
    ctx.beginPath(); history.forEach((item, i) => { const x = padding.left + (i / (history.length - 1)) * chartWidth; const y = padding.top + chartHeight - (item.value / 100) * chartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight); ctx.lineTo(padding.left, padding.top + chartHeight); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
    ctx.strokeStyle = '#8b5cf6'; ctx.lineWidth = 2.5; ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(139, 92, 246, 0.5)'; ctx.beginPath();
    history.forEach((item, i) => { const x = padding.left + (i / (history.length - 1)) * chartWidth; const y = padding.top + chartHeight - (item.value / 100) * chartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.stroke(); ctx.shadowBlur = 0;
  }
  if (history.length > 0) {
    ctx.fillStyle = '#848e9c'; ctx.font = '10px Inter'; ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(history.length / 6));
    for (let i = 0; i < history.length; i += step) { const x = padding.left + (i / (history.length - 1)) * chartWidth; ctx.fillText(history[i].date, x, canvas.height - 10); }
  }
}

function drawMACDChart(history) {
  const canvas = document.getElementById('macdChart'); if (!canvas) return;
  const ctx = canvas.getContext('2d'); const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width; canvas.height = rect.height; ctx.clearRect(0, 0, canvas.width, canvas.height);
  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const chartWidth = canvas.width - padding.left - padding.right, chartHeight = canvas.height - padding.top - padding.bottom;
  if (history.length === 0) return;
  const allValues = history.flatMap(h => [h.macd || 0, h.signal || 0]);
  const maxVal = Math.max(...allValues.map(Math.abs)) || 1; const range = maxVal * 1.2;
  ctx.strokeStyle = '#2b3139'; ctx.lineWidth = 1;
  const ySteps = 5;
  for (let i = 0; i <= ySteps; i++) {
    const val = -range + (2 * range / ySteps) * i;
    const y = padding.top + chartHeight - ((val + range) / (2 * range)) * chartHeight;
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(canvas.width - padding.right, y); ctx.stroke();
    ctx.fillStyle = '#848e9c'; ctx.font = '11px Inter'; ctx.textAlign = 'right'; ctx.fillText(val.toFixed(2), padding.left - 10, y + 4);
  }
  const centerY = padding.top + chartHeight / 2;
  ctx.strokeStyle = '#5e6673'; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(padding.left, centerY); ctx.lineTo(canvas.width - padding.right, centerY); ctx.stroke(); ctx.setLineDash([]);
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2.5; ctx.shadowBlur = 8; ctx.shadowColor = 'rgba(59, 130, 246, 0.6)'; ctx.beginPath();
  history.forEach((h, i) => { const x = padding.left + (i / (history.length - 1)) * chartWidth; const y = padding.top + chartHeight - (((h.macd || 0) + range) / (2 * range)) * chartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
  ctx.stroke();
  ctx.strokeStyle = '#ff4757'; ctx.shadowColor = 'rgba(255, 71, 87, 0.6)'; ctx.beginPath();
  history.forEach((h, i) => { const x = padding.left + (i / (history.length - 1)) * chartWidth; const y = padding.top + chartHeight - (((h.signal || 0) + range) / (2 * range)) * chartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
  ctx.stroke(); ctx.shadowBlur = 0;
  ctx.fillStyle = '#848e9c'; ctx.font = '10px Inter'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(history.length / 6));
  for (let i = 0; i < history.length; i += step) { const x = padding.left + (i / (history.length - 1)) * chartWidth; ctx.fillText(history[i].date, x, canvas.height - 10); }
}

function drawPriceChart(history) {
  const canvas = document.getElementById('priceChart'); if (!canvas) return;
  const ctx = canvas.getContext('2d'); const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width; canvas.height = rect.height; ctx.clearRect(0, 0, canvas.width, canvas.height);
  const padding = { top: 20, right: 20, bottom: 40, left: 70 };
  const chartWidth = canvas.width - padding.left - padding.right, chartHeight = canvas.height - padding.top - padding.bottom;
  if (history.length === 0) return;
  const prices = history.map(h => h.close), highs = history.map(h => h.high), lows = history.map(h => h.low), volumes = history.map(h => h.volume || 0);
  const minPrice = Math.min(...lows) * 0.9995, maxPrice = Math.max(...highs) * 1.0005, maxVolume = Math.max(...volumes) || 1;
  const priceRange = maxPrice - minPrice || 1, priceChartHeight = chartHeight * 0.75, volumeChartHeight = chartHeight * 0.22;
  ctx.strokeStyle = '#2b3139'; ctx.lineWidth = 1;
  const priceSteps = 5;
  for (let i = 0; i <= priceSteps; i++) {
    const price = minPrice + (priceRange / priceSteps) * i;
    const y = padding.top + priceChartHeight - (price - minPrice) / priceRange * priceChartHeight;
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(canvas.width - padding.right, y); ctx.stroke();
    ctx.fillStyle = '#848e9c'; ctx.font = '11px JetBrains Mono'; ctx.textAlign = 'right'; ctx.fillText(price.toFixed(2), padding.left - 10, y + 4);
  }
  const barWidth = Math.max(3, chartWidth / history.length * 0.7), spacing = chartWidth / history.length;
  if (state.chartType === 'candle') {
    history.forEach((h, i) => {
      const x = padding.left + i * spacing + spacing / 2;
      const isUp = h.close >= h.open; const color = isUp ? '#00d084' : '#ff4757';
      const highY = padding.top + priceChartHeight - (h.high - minPrice) / priceRange * priceChartHeight;
      const lowY = padding.top + priceChartHeight - (h.low - minPrice) / priceRange * priceChartHeight;
      const openY = padding.top + priceChartHeight - (h.open - minPrice) / priceRange * priceChartHeight;
      const closeY = padding.top + priceChartHeight - (h.close - minPrice) / priceRange * priceChartHeight;
      ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x, highY); ctx.lineTo(x, lowY); ctx.stroke();
      const bodyTop = Math.min(openY, closeY), bodyHeight = Math.max(1, Math.abs(closeY - openY));
      ctx.fillStyle = color; ctx.shadowBlur = 4; ctx.shadowColor = color; ctx.fillRect(x - barWidth / 2, bodyTop, barWidth, bodyHeight); ctx.shadowBlur = 0;
    });
  } else {
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + priceChartHeight);
    gradient.addColorStop(0, 'rgba(234, 236, 239, 0.3)'); gradient.addColorStop(1, 'rgba(234, 236, 239, 0)');
    ctx.beginPath(); history.forEach((h, i) => { const x = padding.left + i * spacing + spacing / 2; const y = padding.top + priceChartHeight - (h.close - minPrice) / priceRange * priceChartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.lineTo(padding.left + (history.length - 1) * spacing + spacing / 2, padding.top + priceChartHeight); ctx.lineTo(padding.left + spacing / 2, padding.top + priceChartHeight); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
    ctx.strokeStyle = '#eaecef'; ctx.lineWidth = 2.5; ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(234, 236, 239, 0.5)'; ctx.beginPath();
    history.forEach((h, i) => { const x = padding.left + i * spacing + spacing / 2; const y = padding.top + priceChartHeight - (h.close - minPrice) / priceRange * priceChartHeight; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.stroke(); ctx.shadowBlur = 0;
  }
  const smaPoints = history.filter(h => h.sma_20 !== null && h.sma_20 !== undefined);
  if (smaPoints.length > 1) {
    ctx.strokeStyle = '#ffa502'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.shadowBlur = 6; ctx.shadowColor = 'rgba(255, 165, 2, 0.5)'; ctx.beginPath();
    smaPoints.forEach((h, idx) => { const i = history.indexOf(h); const x = padding.left + i * spacing + spacing / 2; const y = padding.top + priceChartHeight - ((h.sma_20 - minPrice) / priceRange) * priceChartHeight; if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.stroke(); ctx.setLineDash([]); ctx.shadowBlur = 0;
  }
  history.forEach((h, i) => {
    const x = padding.left + i * spacing + spacing / 2; const barH = (h.volume / maxVolume) * volumeChartHeight; const isUp = h.close >= h.open;
    ctx.fillStyle = isUp ? '#00d084' : '#ff4757'; ctx.globalAlpha = 0.5; ctx.fillRect(x - barWidth / 2, canvas.height - padding.bottom - barH, barWidth, barH); ctx.globalAlpha = 1;
  });
  ctx.fillStyle = '#848e9c'; ctx.font = '10px Inter'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(history.length / 8));
  for (let i = 0; i < history.length; i += step) { const x = padding.left + i * spacing + spacing / 2; ctx.fillText(history[i].date.split(' ')[0], x, canvas.height - 12); }
}

// НОВАЯ ФУНКЦИЯ ДЛЯ ЦВЕТА ПРОГНОЗА
function getForecastColor(forecast) {
  if (!forecast) return '#848e9c';
  const text = forecast.toLowerCase();
  if (text.includes('медвеж') || text.includes('пад') || text.includes('sell') || text.includes('прода')) return '#ff4757';
  if (text.includes('нейтр') || text.includes('hold') || text.includes('бок') || text.includes('ожид')) return '#ffa502';
  if (text.includes('быч') || text.includes('рост') || text.includes('buy') || text.includes('покуп')) return '#00d084';
  return '#848e9c';
}

function renderScreener(data) {
  const tbody = document.getElementById('screenerBody');
  if (!data || data.length === 0) { tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 40px; color: #848e9c;">Нет данных</td></tr>'; return; }
  const sorted = [...data].sort((a, b) => b.score - a.score);
  const bullish = sorted.filter(d => d.score > 20).length, bearish = sorted.filter(d => d.score < -20).length, neutral = sorted.length - bullish - bearish;
  const totalEl = document.getElementById('totalStocks'), bullEl = document.getElementById('bullishCount'), bearEl = document.getElementById('bearishCount'), neuEl = document.getElementById('neutralCount');
  if (totalEl) totalEl.textContent = sorted.length; if (bullEl) bullEl.textContent = bullish; if (bearEl) bearEl.textContent = bearish; if (neuEl) neuEl.textContent = neutral;
  tbody.innerHTML = sorted.map((item, idx) => {
    const isPositive = item.score > 0; const scoreClass = isPositive ? 'positive' : 'negative';
    const aiClass = (item.ai_prediction || 'HOLD').toLowerCase();
    const macdSignal = item.macd_signal || 'neutral';
    const macdIcon = macdSignal === 'bullish' ? '↑' : macdSignal === 'bearish' ? '↓' : '→';
    const macdColor = macdSignal === 'bullish' ? '#00d084' : macdSignal === 'bearish' ? '#ff4757' : '#848e9c';
    const macdLabel = macdSignal === 'bullish' ? 'Бычий' : macdSignal === 'bearish' ? 'Медв.' : 'Нейтр.';
    const color = item.color || '#2962ff';
    return `
      <tr onclick="selectTicker('${item.ticker}')">
        <td>${idx + 1}</td>
        <td class="ticker-cell">
          <div class="ticker-logo" style="background: linear-gradient(135deg, ${color}, ${adjustColor(color, -30)});">
            <img src="${item.logo || ''}" alt="" style="width:100%;height:100%;object-fit:contain;" onerror="this.style.display='none';this.parentElement.innerHTML='${item.ticker.substring(0,2)}'">
          </div>
          ${item.ticker}
        </td>
        <td style="font-family: var(--font-mono); font-weight: 600;">${item.price?.toFixed(2) || 0} ₽</td>
        <td style="color: ${item.change >= 0 ? '#00d084' : '#ff4757'}; font-family: var(--font-mono); font-weight: 600;">${item.change >= 0 ? '+' : ''}${item.change_percent?.toFixed(2) || 0}%</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 60px; height: 6px; background: #2a3038; border-radius: 3px; overflow: hidden;">
              <div style="width: ${Math.min(100, Math.abs(item.score))}%; height: 100%; background: ${isPositive ? '#00d084' : '#ff4757'}; box-shadow: 0 0 8px ${isPositive ? '#00d084' : '#ff4757'};"></div>
            </div>
            <span class="score-cell ${scoreClass}">${item.score > 0 ? '+' : ''}${item.score}</span>
          </div>
        </td>
        <td style="font-family: var(--font-mono);">${item.rsi?.toFixed(1) || 0}</td>
        <td><span style="color: ${macdColor}; font-weight: 700; font-size: 16px;">${macdIcon}</span><div style="font-size: 11px; color: #848e9c;">${macdLabel}</div></td>
        <td><span style="color: ${getForecastColor(item.forecast_1d)}; font-weight: 600;">${item.forecast_1d || '—'}</span></td>
        <td><span class="ai-badge ${aiClass}">${item.ai_prediction || 'HOLD'} (${item.ai_confidence?.toFixed(0) || 0}%)</span></td>
        <td><button class="action-btn" onclick="event.stopPropagation(); selectTicker('${item.ticker}')"><i class="fas fa-arrow-right"></i></button></td>
      </tr>
    `;
  }).join('');
}

function selectTicker(ticker) {
  state.currentTicker = ticker; const select = document.getElementById('tickerSelect'); if (select) select.value = ticker;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const dashBtn = document.querySelector('[data-tab="dashboard"]'); if (dashBtn) dashBtn.classList.add('active');
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  const dashTab = document.getElementById('dashboard'); if (dashTab) dashTab.classList.add('active');
  state.currentTab = 'dashboard'; loadTickerData(ticker); updateQuickOverview(); setTimeout(initRevealAnimations, 100);
}

function renderTickerSelector() {
  const select = document.getElementById('tickerSelect'); if (!select) return;
  select.innerHTML = state.tickers.map(t => `<option value="${t.ticker}">${t.ticker} — ${t.name}</option>`).join('');
  select.value = state.currentTicker;
}

function updateQuickOverview() {
  const list = document.getElementById('quickOverviewList'); if (!list) return;
  if (state.screenerData.length === 0) { list.innerHTML = '<div style="color: #848e9c; font-size: 12px; padding: 8px;">Загрузка...</div>'; return; }
  const topByVolume = [...state.screenerData].sort((a, b) => (b.volume || 0) - (a.volume || 0)).slice(0, 5);
  list.innerHTML = topByVolume.map(item => {
    const isPositive = item.change >= 0; const color = item.color || '#2962ff';
    return `
      <div class="quick-stock-item" onclick="selectTicker('${item.ticker}')">
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:24px;height:24px;border-radius:5px;background:linear-gradient(135deg,${color},${adjustColor(color,-30)});display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:white;overflow:hidden;">
            <img src="${item.logo || ''}" alt="" style="width:100%;height:100%;object-fit:contain;" onerror="this.style.display='none';this.parentElement.innerHTML='${item.ticker.substring(0,2)}'">
          </div>
          <span class="ticker">${item.ticker}</span>
        </div>
        <span class="change" style="color: ${isPositive ? '#00d084' : '#ff4757'};">${item.price?.toFixed(2) || 0}₽ ${isPositive ? '+' : ''}${item.change_percent?.toFixed(2) || 0}%</span>
      </div>
    `;
  }).join('');
}

function renderNews(data) {
  const feed = document.getElementById('newsFeed');
  if (!feed) {
    console.error('❌ Элемент newsFeed не найден!');
    return;
  }
  
  if (!data || data.length === 0) {
    feed.innerHTML = '<div style="text-align: center; padding: 40px; color: #848e9c;">Нет новостей</div>';
    return;
  }
  
  console.log('🎨 Рендеринг', data.length, 'новостей');
  
  const positive = data.filter(n => n.sentiment === 'positive').length;
  const negative = data.filter(n => n.sentiment === 'negative').length;
  const neutral = data.filter(n => n.sentiment === 'neutral').length;
  
  const posEl = document.getElementById('positiveNews');
  const negEl = document.getElementById('negativeNews');
  const neuEl = document.getElementById('neutralNews');
  if (posEl) posEl.textContent = positive;
  if (negEl) negEl.textContent = negative;
  if (neuEl) neuEl.textContent = neutral;
  
  try {
    feed.innerHTML = data.map((news, index) => {
      const sentimentClass = news.sentiment || 'neutral';
      const sentimentText = news.sentiment_text || (sentimentClass === 'positive' ? 'Позитив' : sentimentClass === 'negative' ? 'Негатив' : 'Нейтрально');
      const sentimentScore = news.sentiment_score || 0;
      const scoreDisplay = sentimentScore > 0 ? `+${sentimentScore}` : sentimentScore;
      
      const tickers = news.affects || [];
      const tickersHTML = tickers.map(t => `<span class="news-ticker-tag">${t}</span>`).join('');
      
      return `
        <div class="news-item ${sentimentClass}" style="animation: fadeIn 0.3s ease ${index * 0.05}s both;">
          <div class="news-content">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap;">
              <span class="sentiment-badge ${sentimentClass}">${sentimentText} (${scoreDisplay})</span>
              <span style="color: #5e6673; font-size: 12px;">${news.source || ''}</span>
              <span style="color: #5e6673; font-size: 12px;">•</span>
              <span style="color: #5e6673; font-size: 12px;">${news.time_ago || ''}</span>
            </div>
            <a href="${news.link || '#'}" target="_blank" class="news-title" style="text-decoration: none; color: inherit; display: block;">${news.title || 'Без заголовка'}</a>
            <div class="news-desc">${news.description || ''}</div>
            ${tickers.length > 0 ? `<div style="margin-top: 10px; font-size: 12px; color: #5e6673;">Влияет на: ${tickersHTML}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
    
    console.log('✅ Новости отрендерены');
  } catch (err) {
    console.error('❌ Ошибка рендеринга новостей:', err);
    feed.innerHTML = `<div style="text-align: center; padding: 40px; color: #ff4757;">Ошибка отображения: ${err.message}</div>`;
  }
}

async function loadTickerNews(ticker) {
  const feed = document.getElementById('tickerNewsFeed');
  const nameEl = document.getElementById('tickerNewsName');
  if (!feed || !nameEl) return;
  
  nameEl.textContent = ticker;
  feed.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary);"><i class="fas fa-spinner fa-spin"></i> Анализ новостного фона...</div>';
  
  try {
    const data = await fetchAPI(`/api/ticker/${ticker}/news`);
    
    if (!data || data.length === 0) {
      feed.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">Прямых новостей по этому тикеру за последние часы не найдено. ИИ опирается на технические данные.</div>';
      return;
    }
    
    feed.innerHTML = data.map(news => {
      const sentimentClass = news.sentiment || 'neutral';
      const tickersHTML = news.affects.map(t => `<span class="news-ticker-tag">${t}</span>`).join('');
      
      return `
        <div class="ticker-news-item ${sentimentClass}">
          <div class="ticker-news-content">
            <a href="${news.link}" target="_blank" class="ticker-news-title">${news.title}</a>
            <div class="ticker-news-desc">${news.description}</div>
            <div class="ticker-news-meta">
              <span class="sentiment-badge ${sentimentClass}">${news.sentiment_text} (${news.sentiment_score > 0 ? '+' : ''}${news.sentiment_score})</span>
              <span style="font-size: 12px; color: var(--text-muted);">${news.source} • ${news.time_ago}</span>
              ${tickersHTML ? `<span style="font-size: 12px; color: var(--text-muted); margin-left: auto;">Влияет на: ${tickersHTML}</span>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');
    
  } catch (err) {
    console.error('Ошибка загрузки новостей тикера:', err);
    feed.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--accent-red);">Не удалось загрузить новости</div>';
  }
}

window.selectTicker = selectTicker;