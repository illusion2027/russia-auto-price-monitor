import hashlib
import json
import os
import re
import unicodedata
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def market_day(now=None):
    """Official Russian offers use Moscow calendar dates; audit timestamps stay UTC."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone(timedelta(hours=3))).date().isoformat()


def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def normalize(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', str(text)).casefold())


def parse_amount(raw):
    """Whole RUB amount only; reject monthly payments, percentages and ranges."""
    raw = unicodedata.normalize('NFKC', str(raw)).strip()
    if not re.fullmatch(r'(?:от\s+)?\d{1,3}(?:[\s\u00a0\u202f]\d{3}){1,3}(?:[,.]00)?\s*(?:₽|руб(?:лей|\.)?|RUB)?\*?', raw, re.I) and not re.fullmatch(r'\d{6,8}', raw):
        raise ValueError(f'Not a whole vehicle price: {raw!r}')
    cleaned = re.sub(r'[,.]00(?=\s*(?:₽|руб|RUB|$))', '', raw)
    amount = int(''.join(re.findall(r'\d', cleaned)))
    if not 300_000 <= amount <= 100_000_000:
        raise ValueError('Vehicle price outside safety bounds')
    return amount


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def comparison_key(offer):
    # Validity period is included: a renewed promotion is a changed scope.
    fields = ['brand_id', 'model_id', 'model_year', 'production_year', 'trim',
              'price_kind', 'conditions', 'region', 'effective_date', 'valid_until', 'price_basis']
    return digest({k: offer.get(k) for k in fields})


def series_key(offer):
    return digest({k: offer.get(k) for k in ['model_id', 'trim', 'price_kind']})


def active_status(offer, now=None):
    now = now or datetime.now(timezone.utc)
    today = market_day(now)
    if offer.get('valid_until') and offer['valid_until'] < today:
        return 'expired'
    if offer.get('effective_date') and offer['effective_date'] > today:
        return 'needs_review'
    if (now - datetime.fromisoformat(offer['verified_at'].replace('Z', '+00:00'))).total_seconds() > 3 * 86400:
        return 'stale'
    return offer.get('status', 'needs_review')


def extract_conditions(text):
    labels = []
    for pattern, label in [(r'трейд[\s-]*ин', '置换 / Trade-in'), (r'кредит', '贷款'),
                           (r'субсиди', '补贴'), (r'не является офертой', '非合同报价')]:
        if re.search(pattern, text, re.I):
            labels.append(label)
    return labels
