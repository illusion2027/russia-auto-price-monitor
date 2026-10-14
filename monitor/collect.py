import argparse
import hashlib
import json
from pathlib import Path
from .adapters import ADAPTERS
from .adapters.base import NeedsReview
from .common import ROOT, read_json, timestamp, write_json
from .publish import publish
from .state import empty_state, merge_brand
from .transport import Fetcher
from .validation import validate_offer


def persist_evidence(root, offers, documents):
    """Store only price context for HTML, avoiding page scripts/tokens/personal forms."""
    for doc in documents:
        path = root / 'data/evidence' / doc.sha256
        path.parent.mkdir(parents=True, exist_ok=True)
        if doc.content.startswith(b'%PDF'):
            path.with_suffix('.pdf').write_bytes(doc.content)
        else:
            write_json(path.with_suffix('.json'), dict(source_url=doc.url, response_sha256=doc.sha256,
                      capture='price_context_only; page scripts and irrelevant content excluded',
                      excerpts=[o['evidence_excerpt'] for o in offers if o['evidence_sha256'] == doc.sha256]))


def collect(root=ROOT, brands=None, fetcher_factory=Fetcher):
    state = read_json(root / 'data/state.json', empty_state())
    sources = read_json(root / 'data/sources.json')
    catalog = read_json(root / 'data/catalog.json')
    for source in sources:
        bid = source['brand_id']
        if brands and bid not in brands:
            continue
        fetcher, now = None, timestamp()
        try:
            fetcher = fetcher_factory(source['allowed_hosts'])
            offers, documents = ADAPTERS[bid](source).collect(fetcher, now)
            if not offers:
                raise NeedsReview('No supported validated price rows')
            # Reject the entire brand update if any parsed row is invalid.
            for offer in offers:
                validate_offer(offer, catalog, sources)
            persist_evidence(root, offers, documents)
            state = merge_brand(state, bid, offers, now)
            source['validation_status'] = 'partial_verified'
            source['last_success_at'] = now
            source['verified_models'] = sorted({o['model_id'] for o in offers})
            source['reason'] = ('H3 官网配置卡已核验；仅该配置起价，最高价和 MSRP 未核验。' if bid == 'haval' else 'T7 官网配置卡与官方 PDF 逐列一致；已核验四个配置的优惠参考价和 RRP，其他车型待核验。')
            status, reason = 'partial_success', None
        except Exception as error:
            status = 'needs_review' if isinstance(error, NeedsReview) else 'failed'
            reason = f'{type(error).__name__}: {str(error)[:400]}'
            state = merge_brand(state, bid, [], now, reason)
            state['runs'][-1]['status'] = status
        finally:
            if fetcher:
                fetcher.close()
        write_json(root / 'data/state.json', state)
        write_json(root / 'data/sources.json', sources)
        print(json.dumps(dict(brand=bid, status=status, reason=reason), ensure_ascii=False))
    publish(root)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--brands', nargs='+', choices=list(ADAPTERS))
    args = parser.parse_args()
    collect(brands=args.brands)
