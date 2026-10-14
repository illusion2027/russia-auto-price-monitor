from datetime import date, datetime, timezone
from urllib.parse import urlparse
import jsonschema
from .common import ROOT, market_day, parse_amount, read_json


def validate_offer(offer, catalog=None, sources=None):
    jsonschema.Draft202012Validator(read_json(ROOT / 'data/offer.schema.json'),
                                   format_checker=jsonschema.FormatChecker()).validate(offer)
    catalog = catalog or read_json(ROOT / 'data/catalog.json')
    sources = sources or read_json(ROOT / 'data/sources.json')
    model = next((m for m in catalog['models'] if m['model_id'] == offer['model_id']), None)
    if not model or model['brand_id'] != offer['brand_id'] or model['body_type'] not in ('suv', 'sedan', 'mpv', 'hatchback'):
        raise ValueError('Unknown model, brand mismatch or excluded body type')
    source = next(s for s in sources if s['brand_id'] == offer['brand_id'])
    parsed = urlparse(offer['source_url'])
    if parsed.scheme != 'https' or parsed.hostname not in source['allowed_hosts'] or parsed.username or parsed.port not in (None, 443):
        raise ValueError('Source must be an allowlisted official HTTPS URL')
    if offer['price_kind'] not in ('official_promotional_reference', 'msrp'):
        raise ValueError('Dealer/transaction records require a future dedicated evidence validator')
    if offer['price_rub'] != parse_amount(offer['raw_price']):
        raise ValueError('Raw amount disagrees with normalized amount')
    if offer['confidence'] < 0.95 or not offer['conditions'].strip() or len(offer['evidence_excerpt']) < 40:
        raise ValueError('Insufficient conditions/evidence/confidence')
    if offer['status'] != 'verified':
        raise ValueError('A newly accepted quote must pass verification, not import stale/unreviewed status')
    if not offer['production_year'] and not offer['model_year']:
        raise ValueError('At least production year or model year must be evidenced')
    verified = datetime.fromisoformat(offer['verified_at'].replace('Z', '+00:00'))
    if verified > datetime.now(timezone.utc):
        raise ValueError('Future verification timestamp')
    if offer['valid_until'] and offer['effective_date'] and offer['valid_until'] < offer['effective_date']:
        raise ValueError('Reversed validity interval')
    if offer['valid_until'] and offer['valid_until'] < market_day():
        raise ValueError('Expired quote cannot be newly verified')
    if offer['effective_date'] and offer['effective_date'] > market_day():
        raise ValueError('Future quote cannot be current')
    return offer
