"""Read-only local evidence validation; no Docker, provider or hidden checks."""
import json
from pathlib import Path
import sys

from common import BASE, ROOT, NATIVE, load, read, require, sha


def hashes(root, mapping):
    require(mapping, 'Evidence hash inventory is empty')
    for relative, expected in mapping.items():
        path = root / relative
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'Evidence path escapes its root')
        require(sha(path) == expected, 'Evidence changed: ' + relative)


def check():
    checkpoint = next(name for name in ['hn-o01-review-evidence.json', 'hn-o01-evidence.json', 'review-evidence.json', 'offline-evidence.json'] if (BASE / name).exists())
    evidence = read(BASE / checkpoint)
    if checkpoint == 'hn-o01-review-evidence.json':
        require(sha(BASE / 'hn-o01-evidence.json') == evidence['previous_checkpoint_sha256'], 'Original HN-O01 checkpoint changed')
    require(sha(BASE / 'preservation.json') == evidence['preservation_sha256'], 'Preservation manifest changed')
    require(len(read(BASE / 'preservation.json')) == evidence['preserved_files'], 'Preservation scope changed')
    hashes(ROOT, read(BASE / 'preservation.json'))
    hashes(ROOT, evidence['source_sha256'])
    hashes(BASE, evidence['log_sha256'])
    a = load('execution_evidence_accounting', NATIVE / 'accounting.py')
    summary = BASE / evidence['harbor']['summary']
    require(sha(summary) == evidence['harbor']['summary_sha256'], 'Trial summary changed')
    trial = read(summary)
    require(trial['offline'] and trial['paid_runs'] == 0 and trial['provider_requests'] == 0, 'Not an offline control')
    hashes(ROOT, trial['source_sha256'])
    bundle = summary.parent / 'lab/results/runs' / trial['run_id']
    require(a.inventory(bundle) == trial['files'], 'Scratch record/raw Trial evidence changed')
    record = read(bundle / 'run.json')
    a.core_check(summary.parent / 'lab', record)
    require(record['status'] == 'completed' and record['verdict']['result'] == 'pass', 'Full Trial did not pass')
    require(record['sandbox']['network'] == 'off' and record['model']['observed_id'] is None and record['loop']['cost_usd'] is None,
            'Synthetic identity/billing was promoted or offline condition mislabeled')
    accounting = read(bundle / 'trace/accounting.json')
    require(accounting['qualification'] == 'inconclusive' and accounting['cost_status'] == 'unknown' and accounting['atif_valid'],
            'Offline qualification/accounting scope changed')
    controller = read(bundle / 'trace/collection/controller.json')
    for relative, expected in controller['source_sha256'].items():
        require(sha(bundle / 'trace/collection/coordinator-sources' / Path(relative).name) == expected, 'Coordinator source snapshot differs')
    require(controller['cleanup_complete'] and controller['sources_stable'] and controller['hooks'] and controller['sidecars'],
            'Source/boundary/cleanup evidence incomplete')
    if 'hn_o01' in evidence:
        import hn_o01
        hashes(BASE, evidence['hn_o01']['pinned_source_sha256'])
        collection = bundle / 'trace/collection'
        measured = read(collection / 'hn-o01-measurements.json')
        require(measured['synthetic'] is True and measured['offline'] is True and measured['identity_coverage_complete'], 'Missing offline identity coverage')
        unavailable = sorted(key for key, value in measured['values'].items() if value is None)
        expected_unavailable = evidence['hn_o01'].get('unavailable_metrics', [])
        require(unavailable == expected_unavailable and all(key in measured['unavailable'] for key in unavailable), 'Unexpected native measurement coverage')
        if expected_unavailable:
            require(measured['issues'] == ['Permission telemetry is absent, incomplete or unbound'], 'Unexpected telemetry problem')
        else:
            require(not measured['issues'], 'Incomplete native measurement coverage')
        require(hn_o01.observations(collection, record, offline=True)['metrics'] == {}, 'Synthetic metrics were promoted')
        if 'permissions.asked' in expected_unavailable:
            require('permissions.asked' not in hn_o01.observations(collection, record, offline=True)['metrics'], 'Unknown permission count was promoted')
        require(measured['observed_model'] == record['model']['id'], 'Fixture response model mismatch')
    evaluator_summary = BASE / evidence['evaluation']['summary']
    require(sha(evaluator_summary) == evidence['evaluation']['summary_sha256'], 'Evaluator summary changed')
    evaluator = read(evaluator_summary)
    require(evaluator['actual_hidden_checks_read'] is False and evaluator['provider_requests'] == 0 and evaluator['paid_runs'] == 0,
            'Evaluator probe scope changed')
    hashes(BASE, evaluator['source_sha256'])
    require([case['task_label'] for case in evaluator['cases']] == ['T002-repo-janitor', 'T004-feature-from-spec'], 'Missing task-labeled evaluator probes')
    for case in evaluator['cases']:
        receipt = BASE / case['receipt']
        require(sha(receipt) == case['receipt_sha256'], 'Evaluator receipt changed')
        result = read(receipt)
        require(result['result'] is None and result['source_unchanged'] and result['infrastructure_failure'] is None,
                'Probe manufactured a verdict or failed')
        for stream in ['stdout', 'stderr']:
            require(sha(receipt.parent / (stream + '.txt')) == result[stream + '_sha256'], 'Evaluator raw log changed')
    return {'ok': True, 'full_native_trials': 1, 'independent_evaluator_probes': 2,
            'paid_runs': 0, 'provider_requests': 0, 'actual_hidden_checks_read': False,
            'preserved_files': len(read(BASE / 'preservation.json'))}


if __name__ == '__main__':
    def no_connections(event, args):
        if event == 'socket.connect':
            raise RuntimeError('Sockets are disabled during evidence validation')
    sys.addaudithook(no_connections)
    try:
        print(json.dumps(check(), separators=(',', ':')))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        raise SystemExit(1)
