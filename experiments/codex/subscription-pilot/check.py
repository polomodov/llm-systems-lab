"""Read-only subscription preparation/evidence validation; no sockets/auth reads."""
import json
from pathlib import Path
import sys
from subscription_pilot import BASE, ROOT, admission, read, reconcile, require, sha, validate_record


def hashes(root, mapping):
    require(mapping, 'Empty preservation/evidence inventory')
    for name, expected in mapping.items():
        path = root / name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'Evidence path escape')
        require(sha(path) == expected, 'Preserved/evidence bytes changed: ' + name)


def check():
    preservation = read(BASE / 'preservation.json')
    manifest = ROOT / preservation['prior_manifest']
    require(sha(manifest) == preservation['prior_manifest_sha256'], 'Prior preservation manifest changed')
    hashes(ROOT, read(manifest)); hashes(ROOT, preservation['additional_sha256'])
    # The only old document change is the required appended component ledger row.
    current_ledger = (ROOT / 'docs/harness-ledger.md').read_text()
    restored = '\n'.join(line for line in current_ledger.split('\n') if not line.startswith('| L045 |'))
    import hashlib
    require(hashlib.sha256(restored.encode()).hexdigest() == preservation['prior_ledger_sha256'], 'Existing ledger content changed')
    plan = read(BASE / 'plan.json'); prepared = read(BASE / 'prepared-run.json')
    validate_record(prepared)
    hashes(BASE, prepared['source_sha256']); hashes(ROOT, prepared['inputs_sha256'])
    require(prepared['status'] == 'prepared' and prepared['synthetic'] is False, 'Live subscription slot was started')
    require(prepared['plan_sha256'] == sha(BASE / 'plan.json') and prepared['condition'] == plan['condition'], 'Prepared plan binding differs')
    require(plan['execution_authorized'] is False and plan['live_launcher_implemented'] is False and read(BASE / 'authorization.example.json')['allow_real'] is False, 'Real execution must remain disabled')
    require(plan['condition']['version'] == read(ROOT / 'experiments/codex/harness.json')['version'], 'Codex pin differs')
    lock = read(ROOT / 'experiments/common/harbor-native-2026-11/runtime-lock.json')
    require(plan['condition']['image_id'] == lock['images']['codex']['image_id'] and plan['condition']['verifier_image_id'] == lock['verifier']['image_id'], 'Immutable images changed')
    evidence = read(BASE / 'offline-evidence.json')
    hashes(BASE, evidence['source_sha256']); hashes(BASE, evidence['log_sha256'])
    summary = BASE / evidence['summary']; require(sha(summary) == evidence['summary_sha256'], 'Offline summary changed')
    control = read(summary); require(control['synthetic'] and control['paid_runs'] == 0 and control['provider_requests'] == 0 and not control['real_credentials_read'] and not control['real_subscription_allowance_consumed'], 'Offline evidence class changed')
    hashes(summary.parent, control['files']); hashes(BASE, control['source_sha256'])
    record = read(summary.parent / control['record']); validate_record(record)
    require(record['status'] == 'completed' and record['verdict'] == 'pass' and record['cleanup_complete'], 'Offline lifecycle failed')
    before, after = [read(summary.parent / ('raw/quota-' + part + '.json')) for part in ['before', 'after']]
    require(admission(before, now=before['observed_at'], account_scope='offline-subscription-fixture', account_id='subscription-fixture-account', allow_synthetic=True)['quota_ready'], 'Native synthetic quota probe failed')
    require(not admission(before, now=before['observed_at'], account_scope='offline-subscription-fixture', account_id='subscription-fixture-account')['quota_ready'], 'Synthetic quota promoted')
    require(reconcile(before, after) == read(summary.parent / 'quota-reconciliation.json') and not read(summary.parent / 'quota-reconciliation.json')['issues'], 'Quota reconciliation changed')
    require(read(summary.parent / 'raw/api-fallback-rejection.json') == {'rejected': True, 'backend_requests': 0}, 'Native API fallback rejection missing')
    isolation = read(summary.parent / 'raw/isolation.json')
    require(isolation['credential_mode'] == 0o600 and isolation['uid'] == 1000 and not isolation['host_auth_reused'] and not isolation['api_env_present'] and all(request['authenticated_with_fixture'] for request in isolation['requests']), 'Native auth isolation evidence failed')
    require(not any(path.name in ['auth.json', 'fixture-key.pem'] for path in summary.parent.rglob('*')), 'Private credential material retained')
    return {'ok': True, 'prepared_slots': 1, 'native_offline_controls': 1, 'paid_runs': 0, 'real_subscription_runs': 0,
            'preserved_files': len(set(read(manifest)) | set(preservation['additional_sha256'])), 'live_execution_authorized': False}


if __name__ == '__main__':
    def no_connect(event, args):
        if event == 'socket.connect': raise RuntimeError('Sockets forbidden during read-only validation')
    sys.addaudithook(no_connect)
    print(json.dumps(check()))
