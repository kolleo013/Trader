import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.ensemble import GradientBoostingClassifier
import joblib
import os

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
    
    def __init__(self, ticker: str, forecast_hours: int = 8):
        self.ticker = ticker
        self.forecast_hours = forecast_hours
        self.model = None
        self.model_type = MODEL_TYPE
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(project_root, 'models')
        os.makedirs(models_dir, exist_ok=True)  # Создаём папку если нет
        self.model_path = os.path.join(models_dir, f'model_{ticker}_{MODEL_TYPE}.pkl')
        self.feature_names = None
    
    def prepare_training_data(self, df: pd.DataFrame, features: pd.DataFrame) -> tuple:
        """
        Создаём обучающий набор с адаптивным порогом.
        """
        print(f"\n🔧 Готовим данные для обучения...")
        print(f"   Прогноз на {self.forecast_hours} часов вперёд")
        
        # Создаём целевую переменную
        future_prices = df['Close'].shift(-self.forecast_hours)
        
        # АДАПТИВНЫЙ ПОРОГ: начинаем с 0.5%, если классов мало — снижаем
        threshold = 0.005  # 0.5% — реалистично для 4-8 часов
        
        target = (future_prices > df['Close'] * (1 + threshold)).astype(int)
        
        # Объединяем признаки и метки
        data = features.copy()
        data['target'] = target
        
        # Удаляем последние строки (нет future_price) и NaN
        data = data.dropna()
        
        print(f"   Всего примеров: {len(data)}")
        print(f"   Покупок (1): {data['target'].sum()} ({data['target'].mean()*100:.1f}%)")
        print(f"   Не покупок (0): {len(data) - data['target'].sum()}")
        
        # ПРОВЕРКА: если классов меньше 2, снижаем порог
        if data['target'].sum() == 0 or data['target'].sum() == len(data):
            print(f"\n⚠️  Все примеры одного класса! Снижаем порог...")
            
            # Пробуем порог 0.3%
            threshold = 0.003
            target = (future_prices > df['Close'] * (1 + threshold)).astype(int)
            data['target'] = target
            data = data.dropna()
            
            print(f"   Новый порог: {threshold*100:.1f}%")
            print(f"   Покупок (1): {data['target'].sum()} ({data['target'].mean()*100:.1f}%)")
            print(f"   Не покупок (0): {len(data) - data['target'].sum()}")
            
            # Если всё ещё один класс — используем просто "выросла/упала"
            if data['target'].sum() == 0 or data['target'].sum() == len(data):
                print(f"\n⚠️  Всё ещё один класс! Используем бинарную классификацию...")
                target = (future_prices > df['Close']).astype(int)
                data['target'] = target
                data = data.dropna()
                
                print(f"   Покупок (1): {data['target'].sum()} ({data['target'].mean()*100:.1f}%)")
                print(f"   Не покупок (0): {len(data) - data['target'].sum()}")
        
        X = data.drop('target', axis=1)
        y = data['target']
        
        return X, y
    
    def train(self, features: pd.DataFrame, target: pd.Series, test_size: float = 0.2):
        """Обучаем модель с балансировкой классов."""
        print(f"\n🎓 Обучаем модель ({self.model_type}) для {self.ticker}...")
    
        # Разделяем данные
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=test_size, shuffle=False
        )
    
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
                use_label_encoder=False,
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
    
        print(f"\n✅ Модель обучена!")
        print(f"   Точность: {accuracy*100:.2f}%")
        print(f"\n📊 Отчёт:")
        print(classification_report(y_test, y_pred, target_names=['Не покупать', 'Покупать'], zero_division=0))
    
        # Важность признаков
        print(f"\n Топ-5 важных признаков:")
        importance = self.model.feature_importances_
        self.feature_names = features.columns
        sorted_idx = np.argsort(importance)[::-1]
    
        for i in sorted_idx[:5]:
            print(f"   {self.feature_names[i]}: {importance[i]*100:.2f}%")
    
        # Сохраняем
        self.save()
    
        return accuracy
    
    def predict(self, current_features: pd.DataFrame) -> dict:
        """Делаем прогноз на текущих данных."""
        if self.model is None:
            if not self.load():
                return {'error': 'Модель не обучена'}
        
        # Берём последние признаки
        features_array = current_features.iloc[-1:].values
        
        # Предсказываем
        probability = self.model.predict_proba(features_array)[0]
        prediction = self.model.predict(features_array)[0]
        
        return {
            'ticker': self.ticker,
            'prediction': 'BUY' if prediction == 1 else 'HOLD',
            'probability_buy': float(probability[1]) * 100,
            'probability_hold': float(probability[0]) * 100,
            'confidence': float(max(probability)),
            'forecast_hours': self.forecast_hours,
            'model_type': self.model_type
        }
    
    def save(self):
        """Сохраняем модель."""
        if self.model:
            joblib.dump(self.model, self.model_path)
            print(f"💾 Модель сохранена: {self.model_path}")
    
    def load(self):
        """Загружаем модель с обработкой ошибок."""
        if os.path.exists(self.model_path):
            try:
                # Используем threading для безопасной загрузки
                import threading
                lock = threading.Lock()
                with lock:
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
        
        return prediction['confidence'] >= min_confidence