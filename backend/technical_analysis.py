import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks
from datetime import datetime
import os
import time
import matplotlib.dates as mdates

# Настройка стиля графиков
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 10


# === ЧАСТЬ 1: ФУНКЦИИ ДЛЯ РАСЧЁТА ИНДИКАТОРОВ ===

def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """SMA — простая скользящая средняя."""
    return prices.rolling(window=window).mean()

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """RSI — индекс относительной силы."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD — схождение/расхождение скользящих средних."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices: pd.Series, window: int = 20, num_std: float = 2.0):
    """Bollinger Bands — полосы волатильности."""
    middle_band = calculate_sma(prices, window)
    std_dev = prices.rolling(window=window).std()
    upper_band = middle_band + (std_dev * num_std)
    lower_band = middle_band - (std_dev * num_std)
    bandwidth = (upper_band - lower_band) / middle_band
    return upper_band, middle_band, lower_band, bandwidth

def find_swing_points(prices: pd.Series, order: int = 5):
    """Находим локальные максимумы и минимумы."""
    maxima, _ = find_peaks(prices.values, distance=order)
    minima, _ = find_peaks(-prices.values, distance=order)
    return maxima, minima

def calculate_fibonacci_levels_custom(prices: pd.Series, swing_high_idx: int, swing_low_idx: int):
    """Твоя кастомная сетка Фибоначчи: -0.618, -0.27, 0, 0.5, 0.618, 0.786, 1."""
    high = prices.iloc[swing_high_idx]
    low = prices.iloc[swing_low_idx]
    
    if swing_low_idx < swing_high_idx:
        # Бычий тренд: от low к high
        diff = high - low
        levels = {
            '-61.8%': high + diff * 0.618,
            '-27.0%': high + diff * 0.27,
            '0.0%': high,
            '50.0%': low + diff * 0.5,
            '61.8%': low + diff * 0.618,
            '78.6%': low + diff * 0.786,
            '100.0%': low
        }
    else:
        # Медвежий тренд: от high к low
        diff = high - low
        levels = {
            '-61.8%': low - diff * 0.618,
            '-27.0%': low - diff * 0.27,
            '0.0%': low,
            '50.0%': high - diff * 0.5,
            '61.8%': high - diff * 0.618,
            '78.6%': high - diff * 0.786,
            '100.0%': high
        }
    
    return levels

def find_recent_fibonacci(prices: pd.Series, lookback: int = 100):
    """Находим последние значимые свинги и считаем уровни Фибоначчи."""
    recent_prices = prices.tail(lookback)
    maxima, minima = find_swing_points(recent_prices, order=10)
    
    if len(maxima) == 0 or len(minima) == 0:
        return None, None, None, None
    
    swing_high_idx = maxima[np.argmax(recent_prices.values[maxima])]
    swing_low_idx = minima[np.argmin(recent_prices.values[minima])]
    
    levels = calculate_fibonacci_levels_custom(recent_prices, swing_high_idx, swing_low_idx)
    trend = "bullish" if swing_low_idx < swing_high_idx else "bearish"
    
    return swing_high_idx, swing_low_idx, levels, trend


# === ЧАСТЬ 2: ЗАГРУЗКА ДАННЫХ С КЭШИРОВАНИЕМ ===

def load_data(filename: str, use_cache: bool = True) -> pd.DataFrame:
    """Загружаем данные с кэшированием для скорости."""
    cache_file = filename.replace('.csv', '_cache.csv')
    
    # Если кэш есть и он свежий (менее 1 часа), используем его
    if use_cache and os.path.exists(cache_file):
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age < 3600:  # 1 час
            print(f"⚡ Загружаем из кэша: {cache_file}")
            df = pd.read_csv(cache_file, parse_dates=['Date'], index_col='Date')
            print(f"✅ Загружено {len(df)} записей из кэша\n")
            return df
    
    print(f" Загружаем данные из {filename}...")
    df = pd.read_csv(filename, parse_dates=['Date'], index_col='Date')
    print(f"✅ Загружено {len(df)} записей")
    print(f"   Период: с {df.index[0].date()} по {df.index[-1].date()}\n")
    
    # Сохраняем в кэш
    if use_cache:
        df.to_csv(cache_file)
        print(f"💾 Сохранено в кэш: {cache_file}\n")
    
    return df


# === ЧАСТЬ 3: РАСЧЁТ ИНДИКАТОРОВ ===

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляем все индикаторы в DataFrame."""
    print("🧮 Считаем индикаторы...")
    
    df['SMA_20'] = calculate_sma(df['Close'], window=20)
    df['SMA_50'] = calculate_sma(df['Close'], window=50)
    df['RSI'] = calculate_rsi(df['Close'], period=14)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
    
    print("✅ Индикаторы рассчитаны\n")
    return df


# === ЧАСТЬ 4: ПОДРОБНАЯ СТАТИСТИКА ===

def print_detailed_statistics(df: pd.DataFrame, ticker: str, timeframe: str):
    """Выводим подробную статистику по всем индикаторам с пояснениями."""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    print(f"{'='*70}")
    print(f"📊 ПОДРОБНАЯ СТАТИСТИКА: {ticker} ({timeframe})")
    print(f"{'='*70}")
    
    # === ЦЕНА ===
    print(f"\n💰 ЦЕНА:")
    print(f"   Текущая: {last['Close']:.2f}₽")
    change_pct = ((last['Close'] - prev['Close']) / prev['Close'] * 100)
    print(f"   Изменение за период: {change_pct:+.2f}%")
    print(f"   Максимум: {last['High']:.2f}₽")
    print(f"   Минимум: {last['Low']:.2f}₽")
    print(f"   Объём: {last['Volume']:,.0f}")
    
    # === SMA ===
    print(f"\n СКОЛЬЗЯЩИЕ СРЕДНИЕ (SMA):")
    print(f"   SMA 20: {last['SMA_20']:.2f}₽")
    print(f"   SMA 50: {last['SMA_50']:.2f}₽")
    
    if last['Close'] > last['SMA_20']:
        print(f"   ✅ Цена выше SMA 20 — краткосрочный тренд ВОСХОДЯЩИЙ")
        print(f"      (Покупатели контролируют рынок в ближайшей перспективе)")
    else:
        print(f"   ❌ Цена ниже SMA 20 — краткосрочный тренд НИСХОДЯЩИЙ")
        print(f"      (Продавцы сильнее, возможна коррекция)")
    
    if last['Close'] > last['SMA_50']:
        print(f"   ✅ Цена выше SMA 50 — среднесрочный тренд ВОСХОДЯЩИЙ")
        print(f"      (Устойчивый рост, институциональные покупатели активны)")
    else:
        print(f"   ❌ Цена ниже SMA 50 — среднесрочный тренд НИСХОДЯЩИЙ")
        print(f"      (Долгосрочные инвесторы продают)")
    
    # === RSI ===
    print(f"\n🌡️  RSI (ИНДЕКС ОТНОСИТЕЛЬНОЙ СИЛЫ):")
    print(f"   Текущее значение: {last['RSI']:.2f}")
    
    if last['RSI'] > 70:
        print(f"   ⚠️  ЗОНА ПЕРЕКУПЛЕННОСТИ (>70)")
        print(f"      Акция 'перегрета', высокий риск коррекции.")
        print(f"      Исторически: после RSI>70 цена часто падает на 5-15% за 1-2 недели.")
    elif last['RSI'] < 30:
        print(f"   ⚠️  ЗОНА ПЕРЕПРОДАННОСТИ (<30)")
        print(f"      Акция 'недооценена', возможен отскок.")
        print(f"      Исторически: после RSI<30 цена часто растёт на 5-10% за неделю.")
    elif last['RSI'] > 60:
        print(f"   ✅ УМЕРЕННО БЫЧИЙ (60-70)")
        print(f"      Сильный восходящий импульс, но ещё не перегрет.")
    elif last['RSI'] < 40:
        print(f"   ✅ УМЕРЕННО МЕДВЕЖИЙ (30-40)")
        print(f"      Слабый нисходящий импульс, возможно восстановление.")
    else:
        print(f"   ⚖️  НЕЙТРАЛЬНАЯ ЗОНА (40-60)")
        print(f"      Нет явного тренда, рынок в боковике.")
    
    # === MACD ===
    print(f"\n📉 MACD (СХОЖДЕНИЕ/РАСХОЖДЕНИЕ СКОЛЬЗЯЩИХ СРЕДНИХ):")
    print(f"   MACD Line: {last['MACD']:.4f}")
    print(f"   Signal Line: {last['MACD_Signal']:.4f}")
    print(f"   Histogram: {last['MACD_Hist']:.4f}")
    
    if last['MACD'] > last['MACD_Signal']:
        print(f"   ✅ MACD выше Signal — БЫЧИЙ СИГНАЛ")
        print(f"      Быстрая EMA (12) выше медленной (26), тренд ускоряется вверх.")
        if last['MACD_Hist'] > prev['MACD_Hist']:
            print(f"   ✅ Гистограмма растёт — импульс усиливается")
        else:
            print(f"   ⚠️  Гистограмма падает — импульс ослабевает, возможен разворот")
    else:
        print(f"   ❌ MACD ниже Signal — МЕДВЕЖИЙ СИГНАЛ")
        print(f"      Быстрая EMA ниже медленной, тренд направлен вниз.")
        if last['MACD_Hist'] < prev['MACD_Hist']:
            print(f"   ❌ Гистограмма падает — давление продавцов усиливается")
        else:
            print(f"   ⚠️  Гистограмма растёт — возможно восстановление")
    
    # === BOLLINGER BANDS ===
    print(f"\n🔵 BOLLINGER BANDS (ПОЛОСЫ ВОЛАТИЛЬНОСТИ):")
    print(f"   Upper Band: {last['BB_Upper']:.2f}₽")
    print(f"   Middle Band (SMA 20): {last['BB_Middle']:.2f}₽")
    print(f"   Lower Band: {last['BB_Lower']:.2f}₽")
    print(f"   Ширина полос: {last['BB_Width']:.4f} ({last['BB_Width']*100:.2f}%)")
    
    distance_to_upper = (last['BB_Upper'] - last['Close']) / last['Close'] * 100
    distance_to_lower = (last['Close'] - last['BB_Lower']) / last['Close'] * 100
    
    print(f"   Расстояние до верхней полосы: {distance_to_upper:.2f}%")
    print(f"   Расстояние до нижней полосы: {distance_to_lower:.2f}%")
    
    if distance_to_upper < 1.5:
        print(f"   ⚠️  Цена у ВЕРХНЕЙ границы — возможен отскок вниз")
        print(f"      Акция 'упирается' в сопротивление, высокая вероятность коррекции.")
    elif distance_to_lower < 1.5:
        print(f"   ⚠️  Цена у НИЖНЕЙ границы — возможен отскок вверх")
        print(f"      Акция 'упирается' в поддержку, возможен разворот.")
    else:
        print(f"   ✅ Цена в середине канала — пространство для движения")
    
    # Проверка на Squeeze
    recent_widths = df['BB_Width'].tail(100)
    if last['BB_Width'] < recent_widths.quantile(0.1):
        print(f"\n   🔥 ВНИМАНИЕ: SQUEEZE (сжатие полос)!")
        print(f"      Волатильность на историческом минимуме. Ожидается резкий пробой.")
        print(f"      Стратегия: ждать направления пробоя и входить в тренд.")
    
    print(f"\n{'='*70}\n")


# === ЧАСТЬ 5: АНАЛИЗ СТРАТЕГИИ ФИБОНАЧЧИ ===

def analyze_fibonacci_strategy(df: pd.DataFrame, ticker: str, timeframe: str):
    """Анализ стратегии Фибоначчи с поддержкой LONG и SHORT."""
    last = df.iloc[-1]
    current_price = last['Close']
    
    swing_high, swing_low, fib_levels, trend = find_recent_fibonacci(df['Close'], lookback=100)
    
    print(f"{'='*70}")
    print(f"🎯 АНАЛИЗ СТРАТЕГИИ ФИБОНАЧЧИ: {ticker} ({timeframe})")
    print(f"{'='*70}")
    
    print(f"\n💰 Текущая цена: {current_price:.2f}₽")
    print(f"📊 Тренд: {trend.upper()}")
    print(f"🎯 Стратегия: {'LONG (покупка на откате)' if trend == 'bullish' else 'SHORT (продажа на отскоке)'}")
    
    if fib_levels:
        print(f"\n УРОВНИ ФИБОНАЧЧИ:")
        explanations = {
            '-61.8%': 'Цель расширения тренда (сильное движение)',
            '-27.0%': 'Цель расширения тренда (умеренное движение)',
            '0.0%': 'Локальный максимум/минимум',
            '50.0%': 'Психологический уровень (половина движения)',
            '61.8%': 'Ключевой уровень Фибоначчи (сильная поддержка/сопротивление)',
            '78.6%': 'Глубокая коррекция (последний шанс для входа)',
            '100.0%': 'Начало движения (критическая поддержка/сопротивление)'
        }
        
        for level_name, level_price in fib_levels.items():
            distance = (current_price - level_price) / current_price * 100
            
            marker = ""
            if level_name in ['61.8%', '78.6%'] and abs(distance) < 2:
                marker = "🎯 "
            elif level_name in ['-27.0%', '-61.8%'] and abs(distance) < 2:
                marker = "🚀 "
            
            print(f"   {marker}{level_name}: {level_price:.2f}₽ ({distance:+.2f}%) — {explanations.get(level_name, '')}")
    
    print(f"\n{'='*70}")
    print("🎯 СИГНАЛЫ:")
    print(f"{'='*70}")
    
    signals = []
    
    if fib_levels:
        entry_zone_low = fib_levels['61.8%']
        entry_zone_high = fib_levels['78.6%']
        target_zone_low = fib_levels['-61.8%']
        target_zone_high = fib_levels['-27.0%']
        
        if trend == "bullish":
            # LONG стратегия
            if entry_zone_low <= current_price <= entry_zone_high:
                signals.append("✅ Цена в ЗОНЕ ВХОДА LONG (0.618-0.786)")
                
                stop_loss = fib_levels['100.0%']
                take_profit = fib_levels['-27.0%']
                
                risk = current_price - stop_loss
                reward = take_profit - current_price
                risk_reward = reward / risk if risk > 0 else 0
                
                signals.append(f"   📍 Стоп-лосс: {stop_loss:.2f}₽")
                signals.append(f"   🎯 Тейк-профит: {take_profit:.2f}₽")
                signals.append(f"   📊 Risk/Reward: 1:{risk_reward:.2f}")
                
                if risk_reward >= 2:
                    signals.append(f"   ✅ Отличное соотношение риск/прибыль!")
                else:
                    signals.append(f"   ⚠️  Низкое соотношение риск/прибыль, лучше пропустить")
                    
            elif current_price < entry_zone_high:
                signals.append(f"⚠️  Цена ниже зоны входа — слишком глубокая коррекция")
            else:
                signals.append(f"ℹ️  Цена выше зоны входа — ждём коррекцию")
            
            if target_zone_high <= current_price <= target_zone_low:
                signals.append("🚀 Цена в ЗОНЕ ЦЕЛИ LONG — фиксируем прибыль!")
            elif current_price > target_zone_low:
                signals.append(f"📈 Цена выше зоны цели — тренд продолжается")
        
        elif trend == "bearish":
            # SHORT стратегия
            if entry_zone_high <= current_price <= entry_zone_low:
                signals.append("✅ Цена в ЗОНЕ ВХОДА SHORT (0.618-0.786)")
                
                stop_loss = fib_levels['100.0%']
                take_profit = fib_levels['-27.0%']
                
                risk = stop_loss - current_price
                reward = current_price - take_profit
                risk_reward = reward / risk if risk > 0 else 0
                
                signals.append(f"   📍 Стоп-лосс: {stop_loss:.2f}₽")
                signals.append(f"   🎯 Тейк-профит: {take_profit:.2f}₽")
                signals.append(f"   📊 Risk/Reward: 1:{risk_reward:.2f}")
                
                if risk_reward >= 2:
                    signals.append(f"   ✅ Отличное соотношение риск/прибыль!")
                else:
                    signals.append(f"   ⚠️  Низкое соотношение риск/прибыль, лучше пропустить")
                    
            elif current_price > entry_zone_low:
                signals.append(f"⚠️  Цена выше зоны входа — слишком глубокая коррекция")
            else:
                signals.append(f"ℹ️  Цена ниже зоны входа — ждём отскок")
            
            if target_zone_low <= current_price <= target_zone_high:
                signals.append("🚀 Цена в ЗОНЕ ЦЕЛИ SHORT — фиксируем прибыль!")
            elif current_price < target_zone_high:
                signals.append(f"📉 Цена ниже зоны цели — тренд продолжается")
    
    # Дополнительные сигналы
    rsi = last['RSI']
    macd = last['MACD']
    macd_signal = last['MACD_Signal']
    
    if trend == "bullish":
        if rsi < 30:
            signals.append(f"✅ RSI = {rsi:.1f} — перепроданность (подтверждение LONG)")
        elif rsi > 70:
            signals.append(f"⚠️  RSI = {rsi:.1f} — перекупленность (осторожно с LONG)")
    else:
        if rsi > 70:
            signals.append(f"✅ RSI = {rsi:.1f} — перекупленность (подтверждение SHORT)")
        elif rsi < 30:
            signals.append(f"⚠️  RSI = {rsi:.1f} — перепроданность (осторожно с SHORT)")
    
    if macd > macd_signal:
        signals.append("✅ MACD выше Signal — бычий импульс")
    else:
        signals.append("❌ MACD ниже Signal — медвежий импульс")
    
    for signal in signals:
        print(f"  {signal}")
    
    print(f"\n{'='*70}")
    if any('ЗОНЕ ВХОДА' in s for s in signals):
        strategy = "LONG" if trend == "bullish" else "SHORT"
        print(f"🎯 РЕКОМЕНДАЦИЯ: ОТКРЫТЬ {strategy}")
        print(f"   Дождись разворота цены и подтверждения от MACD/RSI")
    elif any('ЗОНЕ ЦЕЛИ' in s for s in signals):
        print(f" РЕКОМЕНДАЦИЯ: ФИКСИРОВАТЬ ПРИБЫЛЬ")
    else:
        print(f"⏳ РЕКОМЕНДАЦИЯ: ЖДАТЬ")
        print(f"   Цена не в рабочей зоне — сохраняем позицию или ждём")
    print(f"{'='*70}\n")


# === ЧАСТЬ 6: ВИЗУАЛИЗАЦИЯ ===

def plot_analysis(df: pd.DataFrame, ticker: str, timeframe: str):
    """Строим график с ценой, индикаторами и уровнями Фибоначчи."""
    print(f"📊 Строим график для {ticker} ({timeframe})...")
    
    swing_high, swing_low, fib_levels, trend = find_recent_fibonacci(df['Close'], lookback=100)
    
    fig, axes = plt.subplots(4, 1, figsize=(16, 16), sharex=True)
    
    # График 1: Цена + Bollinger Bands + Фибоначчи
    ax1 = axes[0]
    
    # Bollinger Bands
    ax1.fill_between(df.index, df['BB_Lower'], df['BB_Upper'], 
                     color='blue', alpha=0.15, label='Bollinger Bands')
    ax1.plot(df.index, df['Close'], label='Цена закрытия', color='black', linewidth=1.5)
    ax1.plot(df.index, df['BB_Middle'], label='BB Middle (SMA 20)', color='blue', linewidth=1, linestyle='--')
    ax1.plot(df.index, df['SMA_50'], label='SMA 50', color='orange', linewidth=1.5)
    
    if fib_levels:
        colors = {
            '-61.8%': 'darkred',
            '-27.0%': 'red',
            '0.0%': 'black',
            '50.0%': 'orange',
            '61.8%': 'green',
            '78.6%': 'darkgreen',
            '100.0%': 'black'
        }
        
        for level_name, level_price in fib_levels.items():
            color = colors.get(level_name, 'blue')
            linestyle = '--' if level_name in ['61.8%', '78.6%'] else ':'
            linewidth = 2 if level_name in ['61.8%', '78.6%'] else 1
            
            ax1.axhline(y=level_price, color=color, linestyle=linestyle, 
                       linewidth=linewidth, alpha=0.7,
                       label=f'Fib {level_name}: {level_price:.2f}₽')
        
        # Зона входа
        if '61.8%' in fib_levels and '78.6%' in fib_levels:
            entry_color = 'green' if trend == 'bullish' else 'red'
            entry_label = 'Зона входа LONG' if trend == 'bullish' else 'Зона входа SHORT'
            ax1.fill_between(df.index, fib_levels['61.8%'], fib_levels['78.6%'], 
                           alpha=0.2, color=entry_color, label=entry_label)
        
        # Зона цели
        if '-27.0%' in fib_levels and '-61.8%' in fib_levels:
            target_color = 'lime' if trend == 'bullish' else 'magenta'
            target_label = 'Зона цели LONG' if trend == 'bullish' else 'Зона цели SHORT'
            ax1.fill_between(df.index, fib_levels['-27.0%'], fib_levels['-61.8%'], 
                           alpha=0.2, color=target_color, label=target_label)
        
        # Свинги
        if swing_high is not None and swing_low is not None:
            recent_dates = df.index[-100:]
            ax1.plot(recent_dates[swing_high], df['Close'].iloc[-100:].values[swing_high], 
                    'rv', markersize=12, label='Swing High')
            ax1.plot(recent_dates[swing_low], df['Close'].iloc[-100:].values[swing_low], 
                    'g^', markersize=12, label='Swing Low')
    
    ax1.set_title(f'{ticker} — Цена, Bollinger Bands и Фибоначчи ({timeframe})', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Цена (₽)')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # График 2: RSI
    ax2 = axes[1]
    ax2.plot(df.index, df['RSI'], label='RSI', color='purple', linewidth=1.5)
    ax2.axhline(y=70, color='red', linestyle='--', label='Перекупленность (70)', alpha=0.7)
    ax2.axhline(y=30, color='green', linestyle='--', label='Перепроданность (30)', alpha=0.7)
    ax2.set_title('RSI (Relative Strength Index)', fontsize=14, fontweight='bold')
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # График 3: MACD
    ax3 = axes[2]
    ax3.plot(df.index, df['MACD'], label='MACD', color='blue', linewidth=1.5)
    ax3.plot(df.index, df['MACD_Signal'], label='Signal', color='red', linewidth=1)
    ax3.bar(df.index, df['MACD_Hist'], label='Histogram', color='gray', alpha=0.5)
    ax3.axhline(y=0, color='black', linewidth=0.5)
    ax3.set_title('MACD', fontsize=14, fontweight='bold')
    ax3.set_ylabel('MACD')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # График 4: Bollinger Bands Width (волатильность)
    ax4 = axes[3]
    ax4.plot(df.index, df['BB_Width'], label='BB Width', color='teal', linewidth=1.5)
    ax4.axhline(y=df['BB_Width'].tail(100).quantile(0.1), color='red', linestyle='--', 
                label='Squeeze уровень', alpha=0.7)
    ax4.set_title('Волатильность (Bollinger Bands Width)', fontsize=14, fontweight='bold')
    ax4.set_ylabel('BB Width')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # Форматирование оси X
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.tight_layout()
    plt.show()
    print("✅ График построен!\n")


# === ЧАСТЬ 7: ИТОГОВАЯ СВОДКА ===

def final_summary(df_1d, df_1h, ticker: str):
    """Итоговая сводка по обоим таймфреймам."""
    print(f"\n{'='*70}")
    print(f"📊 ИТОГОВАЯ СВОДКА: {ticker}")
    print(f"{'='*70}")
    
    last_1d = df_1d.iloc[-1]
    last_1h = df_1h.iloc[-1]
    
    swing_high_1d, swing_low_1d, fib_1d, trend_1d = find_recent_fibonacci(df_1d['Close'], lookback=100)
    swing_high_1h, swing_low_1h, fib_1h, trend_1h = find_recent_fibonacci(df_1h['Close'], lookback=100)
    
    print(f"\n📅 1D (долгосрочный, прогноз на 5-12 дней):")
    print(f"   Тренд: {trend_1d.upper()}")
    print(f"   Цена: {last_1d['Close']:.2f}₽")
    print(f"   RSI: {last_1d['RSI']:.2f}")
    print(f"   MACD: {'бычий' if last_1d['MACD'] > last_1d['MACD_Signal'] else 'медвежий'}")
    print(f"   Стратегия: {'LONG' if trend_1d == 'bullish' else 'SHORT'}")
    
    print(f"\n⏰ 1H (краткосрочный, прогноз на 1-4 дня):")
    print(f"   Тренд: {trend_1h.upper()}")
    print(f"   Цена: {last_1h['Close']:.2f}₽")
    print(f"   RSI: {last_1h['RSI']:.2f}")
    print(f"   MACD: {'бычий' if last_1h['MACD'] > last_1h['MACD_Signal'] else 'медвежий'}")
    print(f"   Стратегия: {'LONG' if trend_1h == 'bullish' else 'SHORT'}")
    
    # Финальная рекомендация
    print(f"\n{'='*70}")
    print(f"🎯 ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ:")
    print(f"{'='*70}")
    
    if trend_1d == "bullish" and trend_1h == "bullish":
        print(f"\n   ✅ СИЛЬНЫЙ БЫЧИЙ СИГНАЛ")
        print(f"   Оба таймфрейма показывают восходящий тренд.")
        print(f"   Действие: покупать на откатах, держать позицию.")
        print(f"   Стоп-лосс: ниже ближайшего Swing Low")
        print(f"   Тейк-профит: зона -27% Фибоначчи")
        
    elif trend_1d == "bearish" and trend_1h == "bearish":
        print(f"\n   ❌ СИЛЬНЫЙ МЕДВЕЖИЙ СИГНАЛ")
        print(f"   Оба таймфрейма показывают нисходящий тренд.")
        print(f"   Действие: продавать в шорт на отскоках.")
        print(f"   Стоп-лосс: выше ближайшего Swing High")
        print(f"   Тейк-профит: зона -27% Фибоначчи")
        
    elif trend_1d == "bullish" and trend_1h == "bearish":
        print(f"\n   ⚠️  ПРОТИВОРЕЧИВЫЙ СИГНАЛ")
        print(f"   Долгосрочный тренд вверх, но краткосрочный — вниз.")
        print(f"   Интерпретация: идёт коррекция в бычьем тренде.")
        print(f"   Действие: ждать завершения коррекции на 1H, затем покупать.")
        print(f"   Ищи вход в зоне 0.618-0.786 Фибоначчи на 1H.")
        
    elif trend_1d == "bearish" and trend_1h == "bullish":
        print(f"\n   ⚠️  ПРОТИВОРЕЧИВЫЙ СИГНАЛ")
        print(f"   Долгосрочный тренд вниз, но краткосрочный — вверх.")
        print(f"   Интерпретация: возможен отскок в медвежьем тренде.")
        print(f"   Действие: осторожно, не открывать LONG.")
        print(f"   Можно рассмотреть краткосрочный шорт после завершения отскока.")
    
    print(f"\n{'='*70}\n")


# === ГЛАВНЫЙ ЗАПУСК ===

if __name__ == "__main__":
    start_time = time.time()
    
    ticker = "OZON"
    
    print(f"{'='*70}")
    print(f"🚀 МУЛЬТИ-ТАЙМФРЕЙМ АНАЛИЗ: {ticker}")
    print(f"{'='*70}\n")
    
    # === 1D ТАЙМФРЕЙМ (долгосрочный анализ) ===
    print(f"{'='*70}")
    print(f" АНАЛИЗ 1D (дневной таймфрейм) — прогноз на 5-12 дней")
    print(f"{'='*70}\n")
    
    df_1d = load_data(f"data_{ticker}.csv")
    df_1d = add_indicators(df_1d)
    
    print_detailed_statistics(df_1d, ticker, "1D")
    analyze_fibonacci_strategy(df_1d, ticker, "1D")
    plot_analysis(df_1d, ticker, "1D")
    
    # === 1H ТАЙМФРЕЙМ (краткосрочный анализ) ===
    print(f"\n{'='*70}")
    print(f" АНАЛИЗ 1H (часовой таймфрейм) — прогноз на 1-4 дня")
    print(f"{'='*70}\n")
    
    df_1h = load_data(f"data_{ticker}_1h.csv")
    df_1h = add_indicators(df_1h)
    
    print_detailed_statistics(df_1h, ticker, "1H")
    analyze_fibonacci_strategy(df_1h, ticker, "1H")
    plot_analysis(df_1h, ticker, "1H")
    
    # === ИТОГОВАЯ СВОДКА ===
    final_summary(df_1d, df_1h, ticker)
    
    elapsed = time.time() - start_time
    print(f"⏱️  Время выполнения: {elapsed:.2f} секунд")
    print(f"{'='*70}\n")