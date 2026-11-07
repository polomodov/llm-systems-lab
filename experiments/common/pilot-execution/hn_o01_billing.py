"""Offline reconciliation of operator-obtained OpenAI exports; never fetches APIs.

Provider cost buckets are not request-level receipts. Attribution therefore
requires an exclusive project/key for the complete UTC billing bucket, two
identical settled snapshots, and a named independent operator assertion.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from pathlib import Path

from common import BASE, ROOT, operator_document, operator_file, read, require, sha, write
import hn_o01 as capture


def pages(rows, object_name):
    require(isinstance(rows, list) and rows, 'Missing provider export pages')
    buckets, seen, cursors = [], set(), set()
    for index, page in enumerate(rows):
        require(page.get('object') == 'page' and isinstance(page.get('has_more'), bool), 'Invalid provider page')
        more = index < len(rows) - 1
        require(page['has_more'] is more, 'Export pagination is incomplete')
        cursor = page.get('next_page')
        require((isinstance(cursor, str) and cursor and cursor not in cursors) if more else cursor is None,
                'Invalid or repeated pagination cursor')
        if more: cursors.add(cursor)
        require(isinstance(page.get('data'), list), 'Missing provider buckets')
        for bucket in page['data']:
            key = (bucket.get('start_time'), bucket.get('end_time'))
            require(key not in seen and all(isinstance(t, int) and not isinstance(t, bool) for t in key) and key[0] < key[1],
                    'Duplicate or invalid provider bucket')
            seen.add(key)
            require(bucket.get('object') == 'bucket' and isinstance(bucket.get('results'), list), 'Invalid provider bucket')
            require(all(row.get('object') == object_name for row in bucket['results']), 'Wrong provider result type')
            buckets.append(bucket)
    return buckets


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def reconcile(record, collection, seal, export):
    """Validate actual exported numbers and explicit operational attestations.

    This checks arithmetic/provenance, not the authenticity of a manually
    supplied provider document or independent operator identity.
    """
    require(export.get('kind') == 'hn-o01-provider-billing-export-v1' and export.get('synthetic') is False,
            'Only a real provider billing export can finalize a live attempt')
    require(export.get('run_id') == record['run_id'], 'Billing export run mismatch')
    report = read(collection / 'hn-o01-measurements.json')
    require(report['offline'] is False and report['synthetic'] is False, 'Offline telemetry cannot become paid billing')
    require(seal['run_id'] == record['run_id'] and seal['offline'] is False and
            seal['files'] == capture.inventory(collection), 'Billing collection seal changed')
    capture.observations(collection, record, offline=False)
    claim = read(collection.parent / 'execution-claim.json')['permit']
    scope = export['scope']
    project, key = scope.get('project_id'), scope.get('api_key_id')
    require(isinstance(project, str) and project and project == claim['billing_project'] and
            isinstance(key, str) and key and key == claim['billing_api_key_id'], 'Wrong project or missing key ID')
    require(scope.get('exclusive_for_entire_bucket') is True and scope.get('other_activity') is False,
            'Shared project/key usage is not attributable to one Trial')
    require(export.get('collection_seal_sha256') == sha(collection.parent / 'collection-seal.json') and
            export.get('inputs_sha256') == record['inputs']['manifest_sha256'] and
            export.get('response_set_sha256') == report['response_set_sha256'], 'Billing is not bound to this collection/response set')
    review = export['review']
    require(review.get('status') == 'settled' and review.get('reviewer') and review.get('basis') and
            review.get('all_retries_included') is True, 'Named finality/retry review is required')
    start, end = scope['start_time'], scope['end_time']
    require(isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool) and
            start % 86400 == 0 and end - start == 86400, 'Use one complete UTC-day cost bucket')
    controller = read(collection / 'controller.json')
    started = capture.stamp(read(collection.parent / 'start-receipt.json')['started_at']).timestamp()
    finished = capture.stamp(controller['finished_at']).timestamp()
    require(start <= started <= finished < end, 'Trial crosses or escapes its isolated billing bucket')
    snapshots = export['snapshots']
    require(isinstance(snapshots, list) and len(snapshots) == 2, 'Two independently obtained provider snapshots are required')
    totals = []
    previous = None
    for snapshot in snapshots:
        fetched = capture.stamp(snapshot['retrieved_at']).timestamp()
        require(fetched >= end and (previous is None or fetched > previous), 'Snapshots must follow bucket close and each other')
        previous = fetched
        query = snapshot['query']
        require(query == {'start_time': start, 'end_time': end, 'project_ids': [project], 'api_key_ids': [key],
                           'usage_group_by': ['project_id', 'api_key_id', 'model'],
                           'cost_group_by': ['project_id', 'api_key_id', 'line_item']}, 'Export query scope/grouping differs')
        usage = pages(snapshot['usage_pages'], 'organization.usage.completions.result')
        costs = pages(snapshot['cost_pages'], 'organization.costs.result')
        require(len(usage) == len(costs) == 1 and
                all(row['start_time'] == start and row['end_time'] == end for row in usage + costs), 'Provider buckets differ from the reviewed UTC day')
        measured = {'input_tokens': 0, 'output_tokens': 0, 'num_model_requests': 0}
        require(usage[0]['results'], 'Empty usage export is unknown, not zero')
        for row in usage[0]['results']:
            require(row.get('project_id') == project and row.get('api_key_id') == key and row.get('model') == record['model']['id'],
                    'Provider usage has mixed project/key/model attribution')
            for field in measured:
                measured[field] += capture.number(row[field])
        require(measured == {'input_tokens': report['values']['tokens_in'], 'output_tokens': report['values']['tokens_out'],
                             'num_model_requests': len(report['response_ids'])}, 'Provider/native usage differs; investigate retries or missing responses')
        require(costs[0]['results'], 'Empty cost export is unknown, not a settled zero')
        amount, items = Decimal(0), set()
        for row in costs[0]['results']:
            require(row.get('project_id') == project and row.get('api_key_id') == key, 'Costs lack project/key attribution')
            item = row.get('line_item')
            require(isinstance(item, str) and item and item not in items, 'Missing or duplicate cost line item')
            items.add(item)
            require(row['amount'].get('currency') == 'usd' and not isinstance(row['amount']['value'], bool), 'Expected USD provider costs')
            try: value = Decimal(str(row['amount']['value']))
            except InvalidOperation as error: raise ValueError('Invalid provider amount') from error
            require(value.is_finite() and value >= 0, 'Invalid/negative provider cost')
            amount += value
        totals.append({'amount': str(amount), 'usage': measured, 'cost_pages': snapshot['cost_pages'], 'usage_pages': snapshot['usage_pages']})
    require(totals[0] == totals[1], 'Provider snapshots are still changing; billing is unsettled')
    require(capture.stamp(review['reviewed_at']).timestamp() >= previous, 'Finality review predates the final snapshot')
    cost = float(Decimal(totals[-1]['amount']))
    capture.number(cost, integer=False)
    return {'status': 'settled', 'run_id': record['run_id'], 'provider': 'openai', 'project': project,
            'api_key_id': key, 'cost_usd': cost, 'synthetic': False,
            'collection_seal_sha256': export['collection_seal_sha256'],
            'inputs_sha256': export['inputs_sha256'], 'response_set_sha256': report['response_set_sha256'],
            'reconciler_sha256': sha(Path(__file__)), 'provider_export_content_sha256': digest(export),
            'attribution': 'Exclusive project/key for entire UTC bucket; complete matching usage/cost pages; two stable snapshots; reviewer=' + review['reviewer'],
            'finality_basis': review['basis'], 'reviewed_at': review['reviewed_at'],
            'over_target': cost > record['loop']['budget_usd']}


def verify_receipt(record, collection, seal, receipt, provider_export):
    expected = reconcile(record, collection, seal, provider_export)
    require(all(receipt.get(key) == value for key, value in expected.items()), 'Reconciliation receipt does not match provider evidence')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', dest='export_name', required=True, help='Plain operator staging filename')
    parser.add_argument('--out', required=True, help='New plain operator staging filename')
    args = parser.parse_args()
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*', args.run_id) is not None, 'Exact run ID required')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', args.out) is not None, 'Output must be a plain staging filename')
    bundle = ROOT / 'results/runs' / args.run_id
    record = read(bundle / 'run.json')
    require(record['status'] == 'running' and read(bundle / 'inputs/pilot-slot.json')['slot_id'] == 'HN-O01', 'Only collected HN-O01 may be reconciled')
    path, export = operator_document(args.export_name)
    receipt = reconcile(record, bundle / 'trace/collection', read(bundle / 'trace/collection-seal.json'), export)
    receipt.update(evidence_file=args.export_name, evidence_sha256=sha(path))
    # The directory has been validated by operator_document; exclusive output
    # creation refuses existing files/symlinks. No secret-bearing input is loaded.
    write(path.parent / args.out, receipt)
    print(json.dumps({'status': receipt['status'], 'over_target': receipt['over_target'], 'automatic_next_trial': False}))


if __name__ == '__main__':
    main()
