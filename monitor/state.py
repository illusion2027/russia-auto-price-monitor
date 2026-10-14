from copy import deepcopy
from datetime import datetime, timezone
from .common import active_status, comparison_key, series_key, market_day


def empty_state():
    return dict(schema_version=1, generated_at=None, offers=[], observations=[], changes=[], runs=[])


def merge_brand(state, brand_id, offers, now, error=None, run_status='partial_success'):
    """Brand transaction: all input is validated before calling. Never invent verification times."""
    result = deepcopy(state)
    previous = [o for o in result['offers'] if o['brand_id'] == brand_id]
    other = [o for o in result['offers'] if o['brand_id'] != brand_id]
    replacements = {series_key(o): o for o in offers}
    merged = []
    for old in previous:
        new = replacements.pop(series_key(old), None)
        if new:
            # A newly validated official quote can refresh a manually seeded row.
            merged.append(new)
        else:
            retained = deepcopy(old)
            if retained['source_type'] != 'manual_verified':
                retained['status'] = 'stale'
                retained['failure_reason'] = error or 'This trim was not covered by the latest validated parse'
                retained['last_success_at'] = old.get('last_success_at', old['verified_at'])
            merged.append(retained)
    merged += list(replacements.values())
    old_by_series = {series_key(o): o for o in previous}
    for offer in offers:
        if offer not in merged:
            continue
        offer['last_success_at'] = offer['verified_at']
        offer['failure_reason'] = None
        old = old_by_series.get(series_key(offer))
        if old is None:
            # Newly observed/replaced trims change the model's observed scope.
            old = next((o for o in previous if o['model_id'] == offer['model_id'] and o['price_kind'] == offer['price_kind']), None)
        changed_scope = old and comparison_key(old) != comparison_key(offer)
        changed_price = old and old['price_rub'] != offer['price_rub']
        if not old or changed_scope or changed_price:
            delta = offer['price_rub'] - old['price_rub'] if old and not changed_scope else None
            result['changes'].append(dict(at=now, model_id=offer['model_id'],
                                         series_key=series_key(offer), comparison_key=comparison_key(offer),
                                         kind='scope_change' if changed_scope else ('price_change' if old else 'baseline'),
                                         delta_rub=delta, delta_percent=round(delta / old['price_rub'] * 100, 4) if delta is not None else None,
                                         previous_offer=deepcopy(old), offer=deepcopy(offer)))
        observation = dict(at=now, day=market_day(datetime.fromisoformat(now.replace('Z', '+00:00'))), model_id=offer['model_id'],
                           series_key=series_key(offer), comparison_key=comparison_key(offer), offer=deepcopy(offer))
        # Keep at most one same-price/same-scope observation per UTC day.
        if not any(o['day'] == observation['day'] and o['comparison_key'] == observation['comparison_key']
                   and o['offer']['price_rub'] == offer['price_rub'] for o in result['observations']):
            result['observations'].append(observation)
    result['offers'] = other + merged
    result['generated_at'] = now
    result['runs'].append(dict(at=now, brand_id=brand_id, status=run_status if offers else ('failed' if error else 'needs_review'),
                               offers_count=len(offers), reason=error))
    result['runs'] = result['runs'][-450:]
    return result


def current_view(state, catalog, now=None):
    now = now or datetime.now(timezone.utc)
    result = []
    for model in catalog['models']:
        offers = [dict(o, status=active_status(o, now)) for o in state['offers'] if o['model_id'] == model['model_id']]
        valid = [o for o in offers if o['status'] == 'verified']
        promo = [o for o in valid if o['price_kind'] == 'official_promotional_reference']
        msrp = [o for o in valid if o['price_kind'] == 'msrp']
        def bounds(rows):
            return dict(min_rub=min((o['price_rub'] for o in rows), default=None),
                        # Starting prices establish no upper model bound.
                        max_rub=max((o['price_rub'] for o in rows), default=None) if rows and all(o['price_basis'] == 'exact_trim' for o in rows) else None,
                        coverage='observed_trims_only', min_offer=min(rows, key=lambda o: o['price_rub']) if rows else None,
                        max_offer=max(rows, key=lambda o: o['price_rub']) if rows and all(o['price_basis'] == 'exact_trim' for o in rows) else None)
        result.append(dict(**model, status='verified' if valid else ('stale' if any(o['status'] == 'stale' for o in offers) else ('expired' if any(o['status'] == 'expired' for o in offers) else 'needs_review')),
                           promo=bounds(promo), msrp=bounds(msrp), offers=offers))
    return result
