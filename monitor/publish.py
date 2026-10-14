"""Generate client JSON from the single authoritative, Git-persisted state."""
import argparse
from .common import ROOT, read_json, timestamp, write_json
from .state import current_view, empty_state


def publish(root=ROOT):
    catalog = read_json(root / 'data/catalog.json')
    sources = read_json(root / 'data/sources.json')
    state = read_json(root / 'data/state.json', empty_state())
    current = current_view(state, catalog)
    for source in sources:
        last = next((r for r in reversed(state['runs']) if r['brand_id'] == source['brand_id']), None)
        source['last_run'] = last
        source['verified_models'] = [m['model_id'] for m in current if m['brand_id'] == source['brand_id'] and m['status'] == 'verified']
        source['validation_status'] = 'partial_verified' if source['verified_models'] else 'pending_validation'
        if last and last['reason']:
            source['reason'] = last['reason']
    target = root / 'public/data'
    write_json(target / 'current.json', dict(schema_version=1, generated_at=state['generated_at'], built_at=timestamp(),
                                           brands=catalog['brands'], models=current, sources=sources,
                                           catalog_note=catalog['catalog_note']))
    write_json(target / 'history.json', dict(schema_version=1, observations=state['observations'], changes=state['changes']))
    write_json(target / 'runs.json', state['runs'][-100:])
    print(f'Published {len(current)} catalog models; {sum(m["status"] == "verified" for m in current)} with current verified evidence')


if __name__ == '__main__':
    publish()
