# backend/news_analyzer.py
import feedparser
import re
import time
from datetime import datetime, timezone
import requests

ALL_TICKERS = ['SBER', 'GAZP', 'OZON', 'YDEX', 'T', 'LKOH', 'NVTK', 'MGNT', 'FLOT',
               'HYDR', 'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX', 'VTBR', 'ROSN', 'GMKN', 'ALRS']

# Маппинг тикеров по отраслям
SECTOR_MAPPING = {
    'БАНКИ': ['SBER', 'T', 'VTBR'],
    'НЕФТЬ_ГАЗ': ['GAZP', 'LKOH', 'NVTK', 'ROSN', 'SNGS'],
    'IT': ['YDEX', 'OZON'],
    'МЕТАЛЛУРГИЯ': ['CHMF', 'GMKN', 'ALRS', 'PLZL'],
    'РИТЕЙЛ': ['MGNT'],
    'ТЕЛЕКОМ': ['MTSS'],
    'ТРАНСПОРТ': ['FLOT'],
    'ЭНЕРГЕТИКА': ['HYDR'],
    'ФИНАНСЫ': ['MOEX']
}

# Обратный маппинг: тикер -> отрасль
TICKER_TO_SECTOR = {}
for sector, tickers in SECTOR_MAPPING.items():
    for t in tickers:
        TICKER_TO_SECTOR[t] = sector

# Ключевые слова для общих рыночных новостей
GENERAL_MARKET_KEYWORDS = [
    'ключевая ставка', 'цб рф', 'центральный банк', 'инфляция', 'рубль', 'доллар', 'евро',
    'фондовый рынок', 'индекс мосбиржи', 'imoex', 'rts', 'геополитика', 'санкции', 'налоги',
    'дивидендный сезон', 'отчетность', 'минфин', 'правительство рф'
]

POSITIVE_WORDS = [
    'рост', 'увелич', 'прибыл', 'успех', 'позитив', 'превысил', 'ожида',
    'покуп', 'инвест', 'дивиденд', 'рекоменд', 'повыш', 'выгод', 'доход',
    'рекорд', 'максимум', 'оптимизм', 'улучш', 'развит', 'партнёрств',
    'контракт', 'сделк', 'поглощ', 'слиян', 'профицит', 'избыток', 'преми',
    'бонус', 'награ', 'лидер', 'прорыв', 'инноваци', 'технолог', 'цифровиз',
    'модерниз', 'выручк', 'прибыльн', 'рентабель', 'эффектив', 'оптим',
    'поддержк', 'стимул', 'льгот', 'субсид', 'грант', 'восстанов', 'оживлен',
    'подъем', 'бум', 'активн', 'покупк', 'покупа', 'спрос', 'потреб', 'интерес'
]

NEGATIVE_WORDS = [
    'пад', 'сниз', 'убыт', 'проблем', 'негатив', 'риск', 'потерь',
    'прода', 'кризис', 'санкц', 'огранич', 'запрет', 'штраф', 'суд',
    'долг', 'кредит', 'инфляц', 'дефолт', 'банкрот', 'ликвид',
    'обвал', 'крах', 'паден', 'снижен', 'уменьш', 'сокращ',
    'увольн', 'сокращен', 'оптимизац', 'реструктуриз', 'конфликт',
    'войн', 'угроз', 'давлен', 'претенз', 'иск', 'авар', 'пожар',
    'катастроф', 'чс', 'чрезвычайн', 'мошен', 'коррупц', 'скандал',
    'расследован', 'обвин', 'регресс', 'ухудш', 'кризисн', 'рецесс',
    'спад', 'застой', 'продаж', 'распродаж', 'отток', 'отказ', 'отзыв'
]

RSS_FEEDS = [
    "https://smartlab.ru/rss/news.xml",
    "https://smartlab.ru/rss/companies/news.xml",
    "https://lenta.ru/rss/news",
    "https://ria.ru/export/rss2/archive/index.xml",
    "https://www.rbc.ru/v10/rss/main.rbc.ru/news/index.rss",
    "https://www.interfax.ru/rss.asp",
    "https://finam.ru/rss/news",
]

# Deliberately conservative rules, not a calibrated NLP model.
COMPANY_ALIASES = {
    'SBER': ['сбербанк', 'сбербанка', 'сбербанку', 'сбер'], 'GAZP': ['газпром'], 'OZON': ['озон', 'ozon'],
    'YDEX': ['яндекс', 'яндекса', 'яндексу', 'yandex', 'yndx'], 'T': ['т-банк', 'тинькофф', 'tcs', 'tcsg'],
    'LKOH': ['лукойл'], 'NVTK': ['новатэк'], 'MGNT': ['магнит'],
    'FLOT': ['совкомфлот'], 'HYDR': ['русгидро'], 'SNGS': ['сургутнефтегаз'],
    'CHMF': ['северсталь'], 'MTSS': ['мтс'], 'PLZL': ['полюс'], 'MOEX': ['мосбиржа', 'московская биржа'],
    'VTBR': ['втб'], 'ROSN': ['роснефть'], 'GMKN': ['норникель'], 'ALRS': ['алроса']
}
# Expressions are removed after matching to avoid counting them twice.
EVENT_RULES = [
    (r'не\s+(?:буд\w*\s+)?(?:выплат\w*|плат\w*)\s+дивиденд\w*', -1),
    (r'(?:отмен\w*|отказ\w*|сокращ\w*|снижен\w*)\s+(?:от\s+)?(?:выплат\w*\s+)?дивиденд\w*', -1),
    (r'(?:рост|увелич\w*)\s+убыт\w*', -1),
    (r'(?:снижен\w*|сокращ\w*)\s+(?:чист\w*\s+)?долг\w*', 1),
    (r'(?:снижен\w*|сокращ\w*|паден\w*)\s+(?:чист\w*\s+)?прибыл\w*', -1),
    (r'(?:рост|увелич\w*)\s+(?:чист\w*\s+)?прибыл\w*', 1),
    (r'не\s+(?:выраст\w*|увелич\w*)', -1),
]

def plain_text(text):
    import html
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', text))).strip()


def analyze_sentiment_local(text):
    text_lower = plain_text(text).lower()
    votes = []
    for pattern, weight in EVENT_RULES:
        matches = re.findall(pattern, text_lower)
        votes.extend([weight] * len(matches))
        text_lower = re.sub(pattern, ' ', text_lower)
    # Negation scopes and word boundaries reduce substring false positives.
    for token in re.findall(r'[а-яёa-z]+', text_lower):
        positive = any(token.startswith(w) for w in POSITIVE_WORDS)
        negative = any(token.startswith(w) for w in NEGATIVE_WORDS)
        if positive != negative:
            votes.append(1 if positive else -1)
    return round(sum(votes) / len(votes), 2) if votes else 0.0


def find_tickers_in_text(text):
    text_upper = text.upper()
    text_lower = text.lower()
    found = []
    found_sectors = set()

    # 1. Ищем конкретные тикеры
    for ticker in ALL_TICKERS:
        if re.search(r'\b' + ticker + r'\b', text_upper):
            found.append(ticker)
            sector = TICKER_TO_SECTOR.get(ticker)
            if sector:
                found_sectors.add(sector)

    for ticker, aliases in COMPANY_ALIASES.items():
        if any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text_lower) for alias in aliases):
            found.append(ticker)
            if ticker in TICKER_TO_SECTOR:
                found_sectors.add(TICKER_TO_SECTOR[ticker])

    # 2. Проверяем на общие рыночные новости
    if any(keyword in text_lower for keyword in GENERAL_MARKET_KEYWORDS):
        found.append('ALL')

    # 3. Добавляем найденные отрасли
    found.extend(list(found_sectors))

    # Удаляем дубликаты с сохранением порядка
    seen = set()
    result = []
    for item in found:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result

def parse_time_ago(published_str):
    if not published_str:
        return "Недавно"
    now = datetime.now(timezone.utc)
    formats = ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S']
    for fmt in formats:
        try:
            pub_time = datetime.strptime(published_str, fmt)
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=timezone.utc)
            diff = now - pub_time
            seconds = diff.total_seconds()
            if seconds < 60: return "Только что"
            elif seconds < 3600: return f"{int(seconds / 60)} мин назад"
            elif seconds < 86400: return f"{int(seconds / 3600)} ч назад"
            else: return f"{int(seconds / 86400)} дн назад"
        except:
            continue
    return "Недавно"

def fetch_news_from_feed(url, max_entries=50):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        feed = feedparser.parse(response.content)
        entries = []
        for entry in feed.entries[:max_entries]:
            title = plain_text(entry.get('title', ''))
            description = plain_text(entry.get('description', entry.get('summary', '')))
            link = entry.get('link', '')
            published = entry.get('published', entry.get('updated', ''))
            if title:
                entries.append({'title': title, 'description': description, 'link': link, 'published': published})
        return entries
    except Exception as e:
        print(f"⚠️  Ошибка парсинга {url}: {e}")
        return []

def fetch_all_news(limit=150):
    all_entries = []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        for entries in executor.map(fetch_news_from_feed, RSS_FEEDS):
            all_entries.extend(entries)

    seen_titles = set()
    unique_entries = []
    for entry in all_entries:
        normalized = entry.get('title', '').lower().strip()
        if normalized and normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_entries.append(entry)

    def timestamp(entry):
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(entry.get('published', ''))
            return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
        except (ValueError, TypeError, OverflowError):
            return 0
    entries = sorted(unique_entries, key=timestamp, reverse=True)[:limit]
    news_list = []

    for i, entry in enumerate(entries):
        title = entry.get('title', '')
        description = entry.get('description', '')
        link = entry.get('link', '')
        published = entry.get('published', '')

        full_text = f"{title}. {description}"
        sentiment_score = analyze_sentiment_local(full_text)

        if sentiment_score <= -0.3:
            sentiment_label, sentiment_text = 'negative', 'Негатив'
        elif sentiment_score >= 0.3:
            sentiment_label, sentiment_text = 'positive', 'Позитив'
        else:
            sentiment_label, sentiment_text = 'neutral', 'Нейтрально'

        affected = find_tickers_in_text(full_text)
        time_ago = parse_time_ago(published)

        source = 'Неизвестно'
        if 'smartlab' in link: source = 'Smartlab'
        elif 'lenta' in link: source = 'Lenta.ru'
        elif 'ria' in link: source = 'РИА'
        elif 'rbc' in link: source = 'РБК'
        elif 'interfax' in link: source = 'Интерфакс'
        elif 'finam' in link: source = 'Финам'

        news_list.append({
            'title': title,
            'description': description[:200] + '...' if len(description) > 200 else description,
            'link': link,
            'sentiment': sentiment_label,
            'sentiment_text': sentiment_text,
            'sentiment_score': sentiment_score,
            'affects': affected,
            'time_ago': time_ago,
            'published_at': published,
            'analysis_method': 'rules',
            'source': source
        })

    return news_list
