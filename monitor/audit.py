import argparse
import os
from pathlib import Path
import jsonschema
from .common import ROOT, read_json
from .state import empty_state


def audit(root=ROOT, summary=False):
    state = read_json(root / 'data/state.json', empty_state())
    catalog = read_json(root / 'data/catalog.json')
    ids = {m['model_id'] for m in catalog['models']}
    assert len(ids) == len(catalog['models']), 'Duplicate model IDs'
    schema = read_json(root / 'data/offer.schema.json')
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for offer in state['offers']:
        validator.validate(offer)
        assert offer['model_id'] in ids
        assert list((root / 'data/evidence').glob(offer['evidence_sha256'] + '.*')), 'Missing retained price evidence'
    current = read_json(root / 'public/data/current.json')
    history = read_json(root / 'public/data/history.json')
    for name, value in [('current', current), ('history', history)]:
        jsonschema.Draft202012Validator(read_json(root / f'data/{name}.schema.json'), format_checker=jsonschema.FormatChecker()).validate(value)
    for model in current['models']:
        for offer in model['offers']:
            validator.validate(offer)
        for kind in ['promo', 'msrp']:
            bounds = model[kind]
            if bounds['min_offer']:
                assert bounds['min_rub'] == bounds['min_offer']['price_rub']
                assert bounds['min_offer']['status'] == 'verified'
            if bounds['max_offer']:
                assert bounds['max_rub'] == bounds['max_offer']['price_rub']
    for observation in history['observations']:
        validator.validate(observation['offer'])
    for change in history['changes']:
        validator.validate(change['offer'])
        if change['previous_offer']:
            validator.validate(change['previous_offer'])
    assert current['schema_version'] == history['schema_version'] == 1
    assert set(m['model_id'] for m in current['models']) == ids
    for event in state['changes']:
        if event['kind'] == 'scope_change':
            assert event['delta_rub'] is None and event['delta_percent'] is None
    report = ['| Brand | Last run | Current verified models | Reason |', '|---|---|---:|---|']
    for source in current['sources']:
        run = source['last_run'] or {}
        report.append(f"| {source['brand_id']} | {run.get('status', 'not_run')} | {len(source['verified_models'])} | {source['reason'].replace('|', '/')} |")
    text = '\n'.join(report) + '\n'
    print(text)
    if summary and os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as stream:
            stream.write(text)
    return text


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', action='store_true')
    audit(summary=parser.parse_args().summary)
