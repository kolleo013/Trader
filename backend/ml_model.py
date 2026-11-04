import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, precision_score, recall_score, brier_score_loss
from sklearn.ensemble import GradientBoostingClassifier
import joblib
import os
import json

# === УМНЫЙ ИМПОРТ ===

MODEL_TYPE = None
ModelClass = None

try:
    from xgboost import XGBClassifier
    MODEL_TYPE = 'xgboost'
    ModelClass = XGBClassifier
    print("✅ Используем XGBoost")
except Exception as e:
    print(f"️  XGBoost не работает: {str(e)[:50]}...")
    
    try:
        from lightgbm import LGBMClassifier
        MODEL_TYPE = 'lightgbm'
        ModelClass = LGBMClassifier
        print("✅ Используем LightGBM")
    except Exception as e2:
        print(f"⚠️  LightGBM тоже не работает...")
        MODEL_TYPE = 'sklearn'
        ModelClass = GradientBoostingClassifier
        print("️  Используем sklearn GradientBoosting")


class TradingAI:
    """
    ИИ-модель для трейдинга.
    Обучается на исторических данных, предсказывает движение цены.
    """
    
    def __init__(self, ticker: str, forecast_hours: int = 8, timeframe: str = '1h'):
        if forecast_hours < 1 or timeframe not in ('1d', '1h'):
            raise ValueError("Invalid prediction horizon/timeframe")
        self.timeframe = timeframe
        self.ticker = ticker
        self.forecast_hours = forecast_hours
        self.model = None
        self.model_type = MODEL_TYPE
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.environ.get('TRADER_MODELS_DIR', os.path.join(project_root, '.runtime', 'models'))
        os.makedirs(models_dir, exist_ok=True)  # Создаём папку если нет
        self.model_path = os.path.join(models_dir, f'model_{ticker}_{timeframe}_{forecast_hours}_{MODEL_TYPE}.pkl')
        self.feature_names = None
    
    def prepare_training_data(self, df: pd.DataFrame, features: pd.DataFrame) -> tuple:
        """
        Создаём метки роста более 0.5% через заданное число свечей.
        """
        print(f"\n🔧 Готовим данные для обучения...")
        print(f"   Прогноз на {self.forecast_hours} свечей вперёд")
        
        # Создаём целевую переменную
        future_prices = df['Close'].shift(-self.forecast_hours)
        
        # Fixed threshold: selecting it from all labels would leak test information.
        threshold = 0.005  # 0.5% — реалистично для 4-8 часов
        
        target = (future_prices > df['Close'] * (1 + threshold)).astype(int)
        
        # Объединяем признаки и метки
        data = features.copy()
        data['target'] = target.where(future_prices.notna())
        
        # Удаляем последние строки (нет future_price) и NaN
        data = data.dropna()
        
        print(f"   Всего примеров: {len(data)}")
        print(f"   Покупок (1): {data['target'].sum()} ({data['target'].mean()*100:.1f}%)")
        print(f"   Не покупок (0): {len(data) - data['target'].sum()}")
        
        X = data.drop('target', axis=1)
        y = data['target'].astype(int)
        
        return X, y
    
    def train(self, features: pd.DataFrame, target: pd.Series, test_size: float = 0.2):
        """Обучаем модель с балансировкой классов."""
        print(f"\n🎓 Обучаем модель ({self.model_type}) для {self.ticker}...")
    
        # Разделяем данные
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=test_size, shuffle=False
        )
    
        # Purge labels whose forward horizon overlaps the test period.
        X_train = X_train.iloc[:-self.forecast_hours]
        y_train = y_train.iloc[:-self.forecast_hours]
        if len(X_train) < 20 or y_train.nunique() < 2:
            raise ValueError("Недостаточно обучающих данных после разделения по времени")

        print(f"   Тренировочных: {len(X_train)}")
        print(f"   Тестовых: {len(X_test)}")
    
        # Считаем баланс классов
        class_counts = y_train.value_counts()
        print(f"   Баланс классов в train: {dict(class_counts)}")
    
        # Создаём модель с балансировкой
        if self.model_type == 'xgboost':
            # scale_pos_weight = количество_negативных / количество_позитивных
            scale_pos_weight = class_counts.get(0, 1) / class_counts.get(1, 1)
            self.model = ModelClass(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                min_child_weight=3,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='logloss',
                scale_pos_weight=scale_pos_weight  # БАЛАНСИРОВКА
            )
        elif self.model_type == 'lightgbm':
            self.model = ModelClass(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1,
                is_unbalance=True  # БАЛАНСИРОВКА
            )
        else:  # sklearn
            self.model = ModelClass(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            )
    
        # Обучаем
        self.model.fit(X_train, y_train)
    
        # Оцениваем
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        probabilities = self.model.predict_proba(X_test)[:, 1]
        self.validation = {'accuracy': float(accuracy),
                           'precision_buy': float(precision_score(y_test, y_pred, zero_division=0)),
                           'recall_buy': float(recall_score(y_test, y_pred, zero_division=0)),
                           'brier_score': float(brier_score_loss(y_test, probabilities)),
                           'test_samples': len(X_test), 'purge_bars': self.forecast_hours}

    
        print(f"\n✅ Модель обучена!")
        print(f"   Точность: {accuracy*100:.2f}%")
        print(f"\n📊 Отчёт:")
        print(classification_report(y_test, y_pred, labels=[0, 1], target_names=['Не покупать', 'Покупать'], zero_division=0))
    
        # Важность признаков
        print(f"\n Топ-5 важных признаков:")
        importance = self.model.feature_importances_
        self.feature_names = features.columns
        sorted_idx = np.argsort(importance)[::-1]
    
        for i in sorted_idx[:5]:
            print(f"   {self.feature_names[i]}: {importance[i]*100:.2f}%")
    
        self.validation['train_end'] = str(X_train.index[-1])
        self.validation['test_start'] = str(X_test.index[0])
        self.validation['test_end'] = str(X_test.index[-1])

        # Сохраняем
        self.save()
    
        return accuracy
    
    def predict(self, current_features: pd.DataFrame) -> dict:
        """Делаем прогноз на текущих данных."""
        if current_features.empty:
            raise ValueError('Нет признаков для прогноза')
        if self.model is None:
            if not self.load():
                return {'error': 'Модель не обучена'}
        
        # Берём последние признаки
        if self.feature_names is None or list(current_features.columns) != list(self.feature_names):
            raise ValueError("Несовместимые признаки модели")
        features_array = current_features.iloc[-1:]
        
        # Предсказываем
        probability = self.model.predict_proba(features_array)[0]
        prediction = self.model.predict(features_array)[0]
        
        return {
            'ticker': self.ticker,
            'prediction': 'BUY' if prediction == 1 else 'HOLD',
            'buy_probability': float(probability[1]) * 100,
            'hold_probability': float(probability[0]) * 100,
            'confidence': float(max(probability)) * 100,
            'source': 'model',
            'calibrated': False,
            'forecast_bars': self.forecast_hours,
            'timeframe': self.timeframe,
            'model_type': self.model_type
        }
    
    def save(self):
        """Сохраняем модель."""
        if self.model:
            joblib.dump(self.model, self.model_path)
            with open(self.model_path + ".json", "w") as handle:
                json.dump({"features": list(self.feature_names), "timeframe": self.timeframe, "horizon": self.forecast_hours, "threshold": 0.005, "validation": getattr(self, "validation", {})}, handle)
            print(f"💾 Модель сохранена: {self.model_path}")
    
    def load(self):
        """Загружаем модель с обработкой ошибок."""
        if os.path.exists(self.model_path) and os.path.exists(self.model_path + ".json"):
            try:
                with open(self.model_path + ".json") as handle:
                    metadata = json.load(handle)
                if metadata["timeframe"] != self.timeframe or metadata["horizon"] != self.forecast_hours:
                    return False
                self.feature_names = metadata["features"]
                self.model = joblib.load(self.model_path)
                print(f"✅ Модель загружена: {self.model_path}")
                return True
            except Exception as e:
                print(f"⚠️  Ошибка загрузки модели: {e}")
                return False
        return False
    
    def should_trade(self, prediction: dict, min_confidence: float = 0.65) -> bool:
        """Решаем, стоит ли торговать на основе прогноза."""
        if prediction.get('error'):
            return False
        
        return prediction.get('source') == 'model' and prediction['confidence'] >= min_confidence * 100