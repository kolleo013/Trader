# backend/news_analyzer.py
import feedparser
import re
import time
from datetime import datetime, timezone
import requests

ALL_TICKERS = ['SBER', 'GAZP', 'OZON', 'YNDX', 'TCSG', 'LKOH', 'NVTK', 'MGNT', 'FLOT', 
               'HYDR', 'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX', 'VTBR', 'ROSN', 'GMKN', 'ALRS']

# Расширенный словарь для анализа тональности на русском (финансовый)
POSITIVE_WORDS = [
    'рост', 'увелич', 'прибыл', 'успех', 'позитив', 'превысил', 'ожида', 
    'покуп', 'инвест', 'дивиденд', 'рекоменд', 'повыш', 'выгод', 'доход',
    'рекорд', 'максимум', 'оптимизм', 'улучш', 'развит', 'партнёрств',
    'контракт', 'сделк', 'поглощ', 'слиян', 'дивидендн', 'сплит',
    'профицит', 'избыток', 'преми', 'бонус', 'награ', 'лидер',
    'прорыв', 'инноваци', 'технолог', 'цифровиз', 'модерниз',
    'выручк', 'прибыльн', 'рентабель', 'эффектив', 'оптим',
    'поддержк', 'стимул', 'льгот', 'субсид', 'грант',
    'восстанов', 'оживлен', 'подъем', 'бум', 'активн',
    'покупк', 'покупа', 'спрос', 'потреб', 'интерес'
]

NEGATIVE_WORDS = [
    'пад', 'сниз', 'убыт', 'проблем', 'негатив', 'риск', 'потерь', 
    'прода', 'кризис', 'санкц', 'огранич', 'запрет', 'штраф', 'суд',
    'долг', 'кредит', 'инфляц', 'дефолт', 'банкрот', 'ликвид',
    'обвал', 'крах', 'паден', 'снижен', 'уменьш', 'сокращ',
    'увольн', 'сокращен', 'оптимизац', 'реструктуриз',
    'конфликт', 'войн', 'угроз', 'давлен', 'претенз', 'иск',
    'авар', 'пожар', 'катастроф', 'чс', 'чрезвычайн',
    'мошен', 'коррупц', 'скандал', 'расследован', 'обвин',
    'регресс', 'ухудш', 'кризисн', 'рецесс', 'спад', 'застой',
    'продаж', 'распродаж', 'отток', 'отказ', 'отзыв'
]

# RSS источники (несколько для надёжности)
RSS_FEEDS = [
    "https://smartlab.ru/rss/news.xml",
    "https://smartlab.ru/rss/companies/news.xml",
    "https://lenta.ru/rss/news",
    "https://ria.ru/export/rss2/archive/index.xml",
    "https://www.rbc.ru/v10/rss/main.rbc.ru/news/index.rss",
    "https://www.interfax.ru/rss.asp",
    "https://www.kommersant.ru/RSS/news.xml",
    "https://www.vedomosti.ru/rss/index.xml",
    "https://finam.ru/rss/news",
    "https://www.investing.com/rss/news.rss",
    "https://www.bloomberg.com/feeds/bbiz",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^N225&region=US&lang=en-US",
]

def analyze_sentiment_local(text):
    """Локальный анализ тональности через словарь — работает без интернета к AI"""
    text_lower = text.lower()
    
    pos_score = 0
    neg_score = 0
    
    for word in POSITIVE_WORDS:
        if word in text_lower:
            pos_score += 1
    
    for word in NEGATIVE_WORDS:
        if word in text_lower:
            neg_score += 1
    
    total = pos_score + neg_score
    if total == 0:
        return 0.0
    
    # Нормализуем от -1 до 1
    raw_score = (pos_score - neg_score) / total
    # Усиливаем сильные сигналы
    if abs(raw_score) > 0.5:
        return round(raw_score * 1.2, 2)
    return round(raw_score, 2)

def find_tickers_in_text(text):
    """Ищет тикеры в тексте"""
    text_upper = text.upper()
    found_tickers = []
    for ticker in ALL_TICKERS:
        # Ищем тикер как отдельное слово или в контексте
        if re.search(r'\b' + ticker + r'\b', text_upper):
            found_tickers.append(ticker)
        # Также ищем русские названия (упрощенно)
    return found_tickers

def parse_time_ago(published_str):
    """Парсит время публикации в читаемый формат"""
    if not published_str:
        return "Недавно"
    
    now = datetime.now(timezone.utc)
    
    # Пробуем разные форматы
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%d %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            pub_time = datetime.strptime(published_str, fmt)
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=timezone.utc)
            diff = now - pub_time
            seconds = diff.total_seconds()
            
            if seconds < 60:
                return "Только что"
            elif seconds < 3600:
                return f"{int(seconds / 60)} мин назад"
            elif seconds < 86400:
                return f"{int(seconds / 3600)} ч назад"
            else:
                return f"{int(seconds / 86400)} дн назад"
        except:
            continue
    
    return "Недавно"

def fetch_news_from_feed(url, max_entries=50):
    """Парсит один RSS фид"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        feed = feedparser.parse(response.content)
        entries = []
        
        for entry in feed.entries[:max_entries]:
            title = entry.get('title', '').strip()
            description = entry.get('description', entry.get('summary', '')).strip()
            link = entry.get('link', '')
            published = entry.get('published', entry.get('updated', ''))
            
            if not title:
                continue
            
            entries.append({
                'title': title,
                'description': description,
                'link': link,
                'published': published
            })
        
        return entries
    except Exception as e:
        print(f"⚠️  Ошибка парсинга {url}: {e}")
        return []

def fetch_all_news(limit=150):
    """Парсит новости из всех источников"""
    all_entries = []
    
    for url in RSS_FEEDS:
        print(f"📡 Парсинг {url}...")
        entries = fetch_news_from_feed(url, max_entries=30)
        all_entries.extend(entries)
        print(f"   ✅ Получено {len(entries)} новостей")
    
    # Убираем дубликаты по заголовкам
    seen_titles = set()
    unique_entries = []
    for entry in all_entries:
        title = entry.get('title', '')
        # Нормализуем заголовок для сравнения
        normalized = title.lower().strip()
        if normalized and normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_entries.append(entry)
    
    print(f"📊 Всего уникальных новостей: {len(unique_entries)}")
    
    # Берем нужное количество
    entries = unique_entries[:limit]
    
    news_list = []
    for i, entry in enumerate(entries):
        title = entry.get('title', '')
        description = entry.get('description', '')
        link = entry.get('link', '')
        published = entry.get('published', '')
        
        full_text = f"{title}. {description}"
        sentiment_score = analyze_sentiment_local(full_text)
        
        if sentiment_score <= -0.3:
            sentiment_label = 'negative'
            sentiment_text = 'Негатив'
        elif sentiment_score >= 0.3:
            sentiment_label = 'positive'
            sentiment_text = 'Позитив'
        else:
            sentiment_label = 'neutral'
            sentiment_text = 'Нейтрально'
            
        affected_tickers = find_tickers_in_text(full_text)
        time_ago = parse_time_ago(published)
        
        # Определяем источник по URL
        source = 'Неизвестно'
        if 'smartlab' in link: source = 'Smartlab'
        elif 'lenta' in link: source = 'Lenta.ru'
        elif 'ria' in link: source = 'РИА'
        elif 'rbc' in link: source = 'РБК'
        elif 'interfax' in link: source = 'Интерфакс'
        elif 'kommersant' in link: source = 'Коммерсантъ'
        elif 'vedomosti' in link: source = 'Ведомости'
        elif 'finam' in link: source = 'Финам'
        elif 'investing' in link: source = 'Investing.com'
        elif 'bloomberg' in link: source = 'Bloomberg'
        elif 'yahoo' in link: source = 'Yahoo Finance'
        
        news_list.append({
            'title': title,
            'description': description[:200] + '...' if len(description) > 200 else description,
            'link': link,
            'sentiment': sentiment_label,
            'sentiment_text': sentiment_text,
            'sentiment_score': sentiment_score,
            'affects': affected_tickers,
            'time_ago': time_ago,
            'source': source
        })
        
        if (i + 1) % 20 == 0:
            print(f"📊 Обработано {i + 1}/{len(entries)} новостей")
    
    return news_list