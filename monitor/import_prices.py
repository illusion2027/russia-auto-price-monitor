"""Audited manual import; no default/demo prices are supplied."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from .collect import persist_evidence
from .common import ROOT, read_json, timestamp, write_json
from .publish import publish
from .state import empty_state, merge_brand
from .transport import Document
from .validation import validate_offer


def import_prices(file, evidence, reviewer, reviewed=False, root=ROOT):
    if not reviewed or not reviewer.strip():
        raise ValueError('An identified human reviewer must attest to source, amount, years and conditions with --reviewed')
    file, evidence = Path(file), Path(evidence)
    if file.suffix.lower() == '.csv':
        with file.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for field in ['model_year', 'production_year', 'price_rub']:
                row[field] = int(row[field]) if row[field] else None
            row['confidence'] = float(row['confidence'])
            row['condition_labels'] = json.loads(row['condition_labels'])
            for field in ['effective_date', 'valid_until']:
                row[field] = row[field] or None
    else:
        rows = read_json(file)
    if not isinstance(rows, list) or not rows:
        raise ValueError('Import must be a nonempty offer array')
    content = evidence.read_bytes()
    if not content:
        raise ValueError('Evidence file cannot be empty')
    sha = hashlib.sha256(content).hexdigest()
    now = timestamp()
    # Validate all rows before modifying state or writing snapshots.
    for row in rows:
        row['source_type'] = 'manual_verified'
        row['evidence_sha256'] = sha
        validate_offer(row)
    state = read_json(root / 'data/state.json', empty_state())
    for bid in sorted(set(o['brand_id'] for o in rows)):
        state = merge_brand(state, bid, [o for o in rows if o['brand_id'] == bid], now, run_status='manual_verified')
        state['runs'][-1]['reviewer'] = reviewer
    # Manual input may contain private material. Persist only approved price excerpts,
    # source identifiers, original-file digest, and reviewer attestation.
    write_json(root / 'data/evidence' / f'{sha}.json', dict(source_urls=sorted(set(o['source_url'] for o in rows)),
               original_evidence_sha256=sha, reviewer=reviewer, reviewed_at=now,
               excerpts=[o['evidence_excerpt'] for o in rows], capture='reviewed price excerpts only'))
    write_json(root / 'data/state.json', state)
    publish(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--reviewer', required=True)
    parser.add_argument('--reviewed', action='store_true')
    args = parser.parse_args()
    import_prices(args.file, args.evidence, args.reviewer, args.reviewed)
