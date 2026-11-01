"""
Анализатор сигналов для технического анализа.
Подсчитывает количество положительных, отрицательных и нейтральных сигналов.
"""
import pandas as pd
import numpy as np
from technical_analysis import (
    calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
)

class SignalAnalyzer:
    """Анализирует технические индикаторы и подсчитывает сигналы."""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._calculate_indicators()
    
    def _calculate_indicators(self):
        """Рассчитываем все индикаторы."""
        self.df['SMA_20'] = calculate_sma(self.df['Close'], 20)
        self.df['SMA_50'] = calculate_sma(self.df['Close'], 50)
        self.df['RSI'] = calculate_rsi(self.df['Close'], 14)
        self.df['MACD'], self.df['MACD_Signal'], self.df['MACD_Hist'] = calculate_macd(self.df['Close'])
        self.df['BB_Upper'], self.df['BB_Middle'], self.df['BB_Lower'], self.df['BB_Width'] = calculate_bollinger_bands(self.df['Close'])
    
    def analyze_signals(self) -> dict:
        """
        Анализирует последние данные и подсчитывает сигналы.
        Возвращает словарь с количеством сигналов и итоговым прогнозом.
        """
        if len(self.df) < 50:
            return {'error': 'Недостаточно данных'}
        
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        positive_signals = 0
        negative_signals = 0
        neutral_signals = 0
        signal_details = []
        
        # 1. Цена vs SMA 20
        if last['Close'] > last['SMA_20']:
            positive_signals += 1
            signal_details.append({'indicator': 'Цена > SMA 20', 'signal': 'positive', 'description': 'Краткосрочный тренд вверх'})
        elif last['Close'] < last['SMA_20']:
            negative_signals += 1
            signal_details.append({'indicator': 'Цена < SMA 20', 'signal': 'negative', 'description': 'Краткосрочный тренд вниз'})
        else:
            neutral_signals += 1
            signal_details.append({'indicator': 'Цена = SMA 20', 'signal': 'neutral', 'description': 'Нейтрально'})
        
        # 2. Цена vs SMA 50
        if last['Close'] > last['SMA_50']:
            positive_signals += 1
            signal_details.append({'indicator': 'Цена > SMA 50', 'signal': 'positive', 'description': 'Среднесрочный тренд вверх'})
        elif last['Close'] < last['SMA_50']:
            negative_signals += 1
            signal_details.append({'indicator': 'Цена < SMA 50', 'signal': 'negative', 'description': 'Среднесрочный тренд вниз'})
        else:
            neutral_signals += 1
            signal_details.append({'indicator': 'Цена = SMA 50', 'signal': 'neutral', 'description': 'Нейтрально'})
        
        # 3. RSI
        if last['RSI'] > 70:
            negative_signals += 1
            signal_details.append({'indicator': f'RSI = {last["RSI"]:.1f}', 'signal': 'negative', 'description': 'Перекупленность'})
        elif last['RSI'] < 30:
            positive_signals += 1
            signal_details.append({'indicator': f'RSI = {last["RSI"]:.1f}', 'signal': 'positive', 'description': 'Перепроданность'})
        elif last['RSI'] > 60:
            positive_signals += 1
            signal_details.append({'indicator': f'RSI = {last["RSI"]:.1f}', 'signal': 'positive', 'description': 'Умеренно бычий'})
        elif last['RSI'] < 40:
            negative_signals += 1
            signal_details.append({'indicator': f'RSI = {last["RSI"]:.1f}', 'signal': 'negative', 'description': 'Умеренно медвежий'})
        else:
            neutral_signals += 1
            signal_details.append({'indicator': f'RSI = {last["RSI"]:.1f}', 'signal': 'neutral', 'description': 'Нейтральная зона'})
        
        # 4. MACD
        if last['MACD'] > last['MACD_Signal']:
            positive_signals += 1
            signal_details.append({'indicator': 'MACD > Signal', 'signal': 'positive', 'description': 'Бычий импульс'})
        elif last['MACD'] < last['MACD_Signal']:
            negative_signals += 1
            signal_details.append({'indicator': 'MACD < Signal', 'signal': 'negative', 'description': 'Медвежий импульс'})
        else:
            neutral_signals += 1
            signal_details.append({'indicator': 'MACD = Signal', 'signal': 'neutral', 'description': 'Нейтрально'})
        
        # 5. Bollinger Bands
        bb_position = (last['Close'] - last['BB_Lower']) / (last['BB_Upper'] - last['BB_Lower']) * 100
        if bb_position > 80:
            negative_signals += 1
            signal_details.append({'indicator': f'BB Position = {bb_position:.1f}%', 'signal': 'negative', 'description': 'У верхней границы (перекупленность)'})
        elif bb_position < 20:
            positive_signals += 1
            signal_details.append({'indicator': f'BB Position = {bb_position:.1f}%', 'signal': 'positive', 'description': 'У нижней границы (перепроданность)'})
        else:
            neutral_signals += 1
            signal_details.append({'indicator': f'BB Position = {bb_position:.1f}%', 'signal': 'neutral', 'description': 'В середине канала'})
        
        # 6. Объём (если растёт)
        if 'Volume' in self.df.columns:
            avg_volume_20 = self.df['Volume'].tail(20).mean()
            if last['Volume'] > avg_volume_20 * 1.5:
                positive_signals += 1
                signal_details.append({'indicator': 'Объём выше среднего', 'signal': 'positive', 'description': 'Высокая активность'})
            elif last['Volume'] < avg_volume_20 * 0.5:
                negative_signals += 1
                signal_details.append({'indicator': 'Объём ниже среднего', 'signal': 'negative', 'description': 'Низкая активность'})
            else:
                neutral_signals += 1
                signal_details.append({'indicator': 'Объём средний', 'signal': 'neutral', 'description': 'Нормальная активность'})
        
        # Итоговый прогноз
        total_signals = positive_signals + negative_signals + neutral_signals
        bullish_score = (positive_signals - negative_signals) / total_signals * 100
        
        if bullish_score > 30:
            forecast = 'BULLISH'
            forecast_ru = 'Бычий 📈'
            color = 'green'
        elif bullish_score < -30:
            forecast = 'BEARISH'
            forecast_ru = 'Медвежий 📉'
            color = 'red'
        else:
            forecast = 'NEUTRAL'
            forecast_ru = 'Нейтральный ⚖️'
            color = 'orange'
        
        return {
            'positive': positive_signals,
            'negative': negative_signals,
            'neutral': neutral_signals,
            'total': total_signals,
            'bullish_score': bullish_score,
            'forecast': forecast,
            'forecast_ru': forecast_ru,
            'color': color,
            'details': signal_details,
            'indicators': {
                'RSI': last['RSI'],
                'MACD': last['MACD'],
                'MACD_Signal': last['MACD_Signal'],
                'BB_Upper': last['BB_Upper'],
                'BB_Lower': last['BB_Lower'],
                'SMA_20': last['SMA_20'],
                'SMA_50': last['SMA_50'],
                'Close': last['Close']
            }
        }