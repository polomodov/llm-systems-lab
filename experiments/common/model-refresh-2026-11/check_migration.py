#!/usr/bin/env python3
"""Read-only, socket-free validation of this model migration's local evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
NATIVE = BASE.parent / 'harbor-native-2026-11'
CAMPAIGN = BASE.parent / 'campaigns/2026-11-first-comparison'
MODELS = {'anthropic': 'claude-sonnet-5-5', 'openai': 'gpt-6.1-sol'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hashes(root, values):
    for relative, expected in values.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(), 'Invalid evidence path: ' + relative)
        require(sha(path) == expected, 'Changed evidence: ' + relative)


def check():
    preserved = read(BASE / 'preservation-before.json')
    hashes(ROOT, preserved)
    lab = read(BASE / 'lab-runtime-lock.json')
    hashes(ROOT, lab['source_sha256'])
    require(lab['native_runtime_lock_sha256'] == sha(NATIVE / 'runtime-lock.json'), 'Lab/native runtime lock mismatch')
    require(lab['provider_requests'] == 0 and lab['build_network'] == 'none', 'Lab build policy changed')
    smoke = read(BASE / 'sdk-smoke-evidence.json')
    hashes(ROOT, smoke['sources_sha256'])
    require(smoke['runtime_lock_sha256'] == sha(NATIVE / 'runtime-lock.json') and smoke['lab_runtime_lock_sha256'] == sha(BASE / 'lab-runtime-lock.json'), 'Lab smoke locks stale')
    require(smoke['provider_requests'] == 0 and smoke['credentials_read'] is False, 'Lab smoke is not offline')
    expected = {('pi', 'anthropic'), ('pi', 'openai'), ('mini-swe-agent', 'openai'), ('claude-code', 'anthropic'), ('opencode', 'anthropic'), ('codex', 'openai')}
    require(len(smoke['cases']) == 6 and {(r['harness'], r['provider']) for r in smoke['cases']} == expected, 'Missing lab cases')
    for row in smoke['cases']:
        require(row['status'] == 'passed' and row['cleanup_confirmed'] and row['synthetic_usage_not_billing'] and row['provider_requests'] == 0, 'Failed lab fixture')
        require(row['model'] == MODELS[row['provider']] and row['image_id'] == lab['images'][row['harness']]['image_id'], 'Lab fixture identity mismatch')
        hashes(BASE / row['raw_directory'], row['raw_sha256'])
    spec = importlib.util.spec_from_file_location('refreshed_native_check', NATIVE / 'check_preparation.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    native_result = native.check()
    plan = read(CAMPAIGN / 'plan.json')
    require(plan['authorization'] == {'offline_preparation': True, 'paid_runs': False, 'api_activation': False}, 'Campaign execution policy changed')
    require(len(plan['slots']) == 42 and all(s['status'] == 'not_started' and s['run_id'] is None for s in plan['slots']), 'Campaign slots were started or changed')
    for cohort in plan['cohorts']:
        require(cohort['model_id'] == MODELS[cohort['provider']], 'Campaign model mismatch')
    for name, row in plan['harnesses'].items():
        require(row['image_id'] == lab['images'][name]['image_id'] and row['version'] == lab['images'][name]['version'], 'Campaign pin mismatch')
    budget = read(BASE / 'pilot-budget.json')
    require(not budget['execution_authorized'] and budget['campaign_pilots']['total_target'] == 12 and budget['harbor_native_pilots']['total_target'] == 12 and budget['combined_proposed_pilots']['total_target'] == 24, 'Budget changed')
    require(plan['pilot_budget']['total_target_usd'] == 12, 'Campaign budget mismatch')
    return {'ok': True, 'offline_only': True, 'lab_fixture_cases': 6, **native_result, 'preserved_files': len(preserved), 'paid_runs': 0}


def main():
    def no_connections(event, args):
        if event == 'socket.connect':
            raise RuntimeError('Sockets are disabled during migration validation')
    sys.addaudithook(no_connections)
    try:
        print(json.dumps(check(), separators=(',', ':')))
        return 0
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}, separators=(',', ':')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
