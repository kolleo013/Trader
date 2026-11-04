'use strict';
const $ = id => document.getElementById(id);
const state = {ticker: 'SBER', tf: '1d', tab: 'dashboard', tickers: [], rows: [], news: [], detail: null, descending: true};
let detailRequest = 0, newsRequest = 0;
const pending = new Set();
const number = (n, digits = 2) => n == null || !Number.isFinite(Number(n)) ? '—' : Number(n).toLocaleString('ru-RU', {maximumFractionDigits: digits, minimumFractionDigits: digits});
const signed = n => n == null ? '—' : `${n > 0 ? '+' : ''}${number(n)}`;
const tone = n => n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral';
function element(tag, text, className) { const node = document.createElement(tag); if (text != null) node.textContent = text; if (className) node.className = className; return node; }
function safeURL(value) { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } }
async function api(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try { const response = await fetch(path, {signal: controller.signal}); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); return data; }
  finally { clearTimeout(timeout); }
}
function notice(message) { $('notice').textContent = message || ''; $('notice').hidden = !message; }
function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach(node => { node.hidden = node.id !== tab; });
  document.querySelectorAll('.nav').forEach(node => { const active = node.dataset.tab === tab; node.classList.toggle('active', active); if (active) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current'); });
  $('pageLabel').textContent = {dashboard: 'Обзор акции', screener: 'Скринер рынка', news: 'Новостной фон'}[tab];
  notice(''); refresh();
}
function watchlist() {
  $('watchlist').replaceChildren(...state.tickers.map(item => {
    const button = element('button', null, `watch${item.ticker === state.ticker ? ' active' : ''}`);
    button.append(element('span', item.ticker.slice(0, 2), 'symbol'));
    const label = element('span'); label.append(element('strong', item.ticker), element('small', item.name)); button.append(label);
    if (item.ticker === state.ticker) button.append(element('span', '•', 'star'));
    button.addEventListener('click', () => { state.ticker = item.ticker; state.detail = null; watchlist(); setTab('dashboard'); });
    return button;
  }));
}
async function loadDetail() {
  const sequence = ++detailRequest, ticker = state.ticker, tf = state.tf;
  $('stockName').textContent = state.tickers.find(t => t.ticker === ticker)?.name || ticker;
  $('stockTicker').textContent = `${ticker} · Московская биржа · Акции`;
  $('tickerMonogram').textContent = ticker.slice(0, 2);
  $('quoteContent').hidden = true;
  $('dataStatus').textContent = 'Загружаем котировки и рассчитываем сигналы…';
  $('dataStatus').className = 'data-status';
  loadTickerNews(ticker);
  try {
    const data = await api(`/api/ticker/${ticker}?tf=${tf}`);
    if (sequence !== detailRequest) return;
    state.detail = data; renderDetail(data); notice('');
  } catch (error) {
    if (sequence !== detailRequest || state.tab !== 'dashboard') return;
    state.detail = null;
    $('dataStatus').textContent = 'Данные недоступны. Можно выбрать другую акцию или повторить запрос.';
    notice(error.name === 'AbortError' ? 'Источник не ответил вовремя. Попробуйте обновить позже.' : error.message);
  }
}
function renderDetail(data) {
  $('quoteContent').hidden = false;
  const meta = data.data_status;
  $('dataStatus').className = `data-status${meta.stale ? ' stale' : ''}`;
  $('dataStatus').textContent = `${meta.stale ? '◷ Архив / устаревшие данные' : '● Получено с MOEX'} · Последняя свеча: ${meta.last_candle || '—'} MSK`;
  $('price').textContent = number(data.price);
  $('change').textContent = `${signed(data.change)} ₽ / ${signed(data.change_percent)}%`;
  $('change').className = tone(data.change);
  $('periodLabel').textContent = state.tf === '1d' ? 'К предыдущей дневной свече' : 'К предыдущей часовой свече';
  $('score').textContent = signed(data.score); $('score').className = tone(data.score);
  $('scoreFill').style.left = `${(Math.max(-100, Math.min(100, data.score)) + 100) / 2}%`;
  const pred = data.ai_prediction;
  $('prediction').textContent = {BUY: 'Рост', SELL: 'Снижение', HOLD: 'Нейтрально'}[pred.prediction] || '—';
  $('prediction').className = pred.prediction === 'BUY' ? 'positive' : pred.prediction === 'SELL' ? 'negative' : 'neutral';
  $('predictionSource').textContent = pred.source === 'model' ? 'ML-модель' : 'Правила';
  $('probability').textContent = pred.source === 'model' ? `Выход модели BUY: ${number(pred.buy_probability, 1)}%` : 'Вероятность не рассчитана';
  $('predictionNote').textContent = pred.source === 'model' ? `Горизонт: ${pred.forecast_bars} свечей. Вероятности не откалиброваны.` : 'Эвристика по индикаторам. Модель недоступна.';
  $('volatility').textContent = `${number(data.risk.bar_volatility_pct)}%`;
  $('drawdown').textContent = `Макс. просадка цены в выборке: ${number(data.risk.drawdown_pct)}%`;
  $('rsiValue').textContent = number(data.analysis.indicators.RSI, 1);
  $('signals').replaceChildren(...data.analysis.details.map(signal => {
    const row = element('div', null, 'signal-row'), copy = element('div', signal.indicator);
    copy.append(element('small', signal.description));
    row.append(copy, element('span', {positive: '+ Позитив', negative: '− Негатив', neutral: '— Нейтрально'}[signal.signal], `signal-state ${signal.signal}`)); return row;
  }));
  $('chartRange').textContent = `${data.price_history[0]?.date.slice(0, 10) || ''} — ${data.price_history.at(-1)?.date.slice(0, 10) || ''}`;
  requestAnimationFrame(drawCharts);
}
async function loadScreener() {
  if (pending.has('screener')) return;
  pending.add('screener');
  $('screenerSummary').textContent = 'Обновляем акции. При первом запросе это может занять до двух минут…';
  try { state.rows = await api('/api/screener'); renderScreener(); }
  catch (error) { $('screenerSummary').textContent = 'Не удалось обновить скринер.'; if (state.tab === 'screener') notice(error.message); }
  finally { pending.delete('screener'); }
}
function renderScreener() {
  const query = $('stockSearch').value.toLocaleLowerCase('ru');
  const rows = state.rows.filter(row => `${row.ticker} ${row.name}`.toLocaleLowerCase('ru').includes(query)).sort((a, b) => (state.descending ? -1 : 1) * ((a.score ?? -101) - (b.score ?? -101)));
  $('screenerBody').replaceChildren(...rows.map(row => {
    const tr = element('tr'), cell = element('td'), button = element('button', row.ticker, 'ticker-link');
    button.addEventListener('click', () => { state.ticker = row.ticker; watchlist(); setTab('dashboard'); });
    cell.append(button, element('small', row.name)); tr.append(cell);
    if (row.error) { const error = element('td', row.error, 'muted'); error.colSpan = 6; tr.append(error); return tr; }
    tr.append(element('td', number(row.price)), element('td', `${signed(row.change_percent)}%`, tone(row.change_percent)), element('td', signed(row.score), tone(row.score)), element('td', number(row.analysis.indicators.RSI, 1)));
    const pred = element('td', {BUY: 'Рост', HOLD: 'Нейтрально', SELL: 'Снижение'}[row.ai_prediction.prediction]);
    pred.append(element('small', row.ai_prediction.source === 'model' ? 'ML · без калибровки' : 'Правила')); tr.append(pred);
    tr.append(element('td', row.data_status.stale ? '◷ Устарели' : '● MOEX', row.data_status.stale ? 'neutral' : 'positive')); return tr;
  }));
  if (!rows.length) { const tr = element('tr'), td = element('td', 'Ничего не найдено', 'empty'); td.colSpan = 7; tr.append(td); $('screenerBody').append(tr); }
  $('screenerSummary').textContent = `${rows.length} из ${state.rows.length} акций · Недоступно: ${state.rows.filter(r => r.error).length} · Оценка — баланс индикаторов, не ожидаемая доходность`;
}
function renderNews(items, target, stale = false) {
  const root = $(target); root.replaceChildren();
  if (stale) root.append(element('p', 'Свежие новости недоступны. Сохранённая лента может быть устаревшей.', 'panel-note'));
  if (!items.length) { root.append(element('p', 'Нет подходящих новостей. Это не означает отсутствие событий на рынке.', 'empty')); return; }
  items.forEach(item => {
    const article = element('article', null, 'news-item'), meta = element('div', null, 'news-meta');
    const sentiment = ['positive', 'negative', 'neutral'].includes(item.sentiment) ? item.sentiment : 'neutral';
    meta.append(element('span', {positive: '+ Позитив', negative: '− Негатив', neutral: '— Нейтрально'}[sentiment], sentiment), element('span', item.source), element('span', item.time_ago));
    if (item.relevance) meta.append(element('span', {company: 'Компания', sector: 'Отрасль', market: 'Рынок'}[item.relevance], 'pill'));
    const url = safeURL(item.link), title = element(url ? 'a' : 'span', item.title);
    if (url) { title.href = url; title.target = '_blank'; title.rel = 'noopener noreferrer'; }
    article.append(meta, title, element('p', item.description));
    const tags = element('div', null, 'news-tags'); (item.affects || []).forEach(tag => tags.append(element('span', tag)));
    article.append(tags); root.append(article);
  });
}
async function loadTickerNews(ticker) {
  const sequence = ++newsRequest;
  $('tickerNews').replaceChildren(element('p', 'Загружаем источники…', 'empty'));
  try { const data = await api(`/api/ticker/${ticker}/news`); if (sequence === newsRequest) renderNews(data.items, 'tickerNews', data.stale); }
  catch { if (sequence === newsRequest) $('tickerNews').replaceChildren(element('p', 'Не удалось получить новости. Техническая оценка от них не зависит.', 'empty')); }
}
async function loadNews() {
  if (pending.has('news')) return; pending.add('news');
  $('newsStatus').textContent = 'Загружаем…';
  try { const data = await api('/api/news'); state.news = data.items; state.newsStale = data.stale; filterNews(); $('newsStatus').textContent = `${data.items.length} событий · ${data.stale ? 'Источники недоступны' : 'Тональность по правилам'}`; }
  catch (error) { $('newsStatus').textContent = 'Ошибка загрузки'; if (state.tab === 'news') notice(error.message); }
  finally { pending.delete('news'); }
}
function filterNews() { renderNews(state.news.filter(item => $('newsFilter').value === 'all' || item.sentiment === $('newsFilter').value), 'newsFeed', state.newsStale); }
function plot(id, history, series, fixedRange = null, levels = []) {
  const canvas = $(id), rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * scale); canvas.height = Math.round(rect.height * scale);
  const ctx = canvas.getContext('2d'); ctx.scale(scale, scale);
  const width = rect.width, height = rect.height, pad = {left: 52, right: 14, top: 18, bottom: 28};
  const values = history.flatMap(row => series.map(s => row[s.key])).filter(v => v != null && Number.isFinite(v));
  if (!values.length) return;
  let [min, max] = fixedRange || [Math.min(...values), Math.max(...values)];
  if (!fixedRange) { const margin = (max - min || Math.abs(max) * .01 || 1) * .12; min -= margin; max += margin; }
  const x = i => pad.left + i / Math.max(1, history.length - 1) * (width - pad.left - pad.right);
  const y = value => pad.top + (max - value) / (max - min) * (height - pad.top - pad.bottom);
  ctx.font = '10px system-ui'; ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) { const value = min + (max - min) * i / 4; ctx.strokeStyle = '#233139'; ctx.beginPath(); ctx.moveTo(pad.left, y(value)); ctx.lineTo(width - pad.right, y(value)); ctx.stroke(); ctx.fillStyle = '#94a6b0'; ctx.textAlign = 'right'; ctx.fillText(number(value, id === 'priceChart' ? 1 : 0), pad.left - 8, y(value) + 3); }
  levels.forEach(level => { ctx.strokeStyle = '#6c634b'; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(pad.left, y(level)); ctx.lineTo(width - pad.right, y(level)); ctx.stroke(); }); ctx.setLineDash([]);
  series.forEach(s => { ctx.strokeStyle = s.color; ctx.lineWidth = 1.8; ctx.beginPath(); let started = false; history.forEach((row, i) => { const value = row[s.key]; if (value == null || !Number.isFinite(value)) { started = false; return; } if (started) ctx.lineTo(x(i), y(value)); else ctx.moveTo(x(i), y(value)); started = true; }); ctx.stroke(); });
  ctx.fillStyle = '#94a6b0'; ctx.textAlign = 'center';
  [0, Math.floor((history.length - 1) / 2), history.length - 1].forEach(i => { if (i >= 0) ctx.fillText(history[i].date.slice(5, 10), x(i), height - 6); });
}
function drawCharts() { if (!state.detail || state.tab !== 'dashboard') return; const h = state.detail.price_history; plot('priceChart', h, [{key: 'close', color: '#a6e4c0'}, {key: 'sma_20', color: '#dfc48c'}]); plot('rsiChart', h, [{key: 'rsi', color: '#a6e4c0'}], [0, 100], [30, 70]); plot('macdChart', h, [{key: 'macd', color: '#9fbde9'}, {key: 'signal', color: '#dfc48c'}], null, [0]); }
async function refresh() {
  if (state.tab === 'dashboard') await loadDetail(); else if (state.tab === 'screener') await loadScreener(); else await loadNews();
}
document.querySelectorAll('.nav').forEach(button => button.addEventListener('click', () => setTab(button.dataset.tab)));
document.querySelectorAll('[data-tf]').forEach(button => button.addEventListener('click', () => { state.tf = button.dataset.tf; document.querySelectorAll('[data-tf]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); }); loadDetail(); }));
$('refresh').addEventListener('click', async () => { $('refresh').disabled = true; try { await refresh(); } finally { $('refresh').disabled = false; } });
$('stockSearch').addEventListener('input', renderScreener);
$('sortScore').addEventListener('click', () => { state.descending = !state.descending; $('sortScore').textContent = `Оценка ${state.descending ? '↓' : '↑'}`; renderScreener(); });
$('newsFilter').addEventListener('change', filterNews);
new ResizeObserver(drawCharts).observe($('quoteContent'));
function clock() { $('clock').textContent = new Intl.DateTimeFormat('ru-RU', {timeZone: 'Europe/Moscow', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}).format(new Date()) + ' MSK'; }
clock(); setInterval(clock, 60000);
(async () => { try { state.tickers = await api('/api/tickers'); watchlist(); await refresh(); } catch (error) { notice(`Не удалось загрузить приложение: ${error.message}`); } })();
