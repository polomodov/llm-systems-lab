"""Data-only subscription pilot policy. No provider/credential reads or launches."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def require(condition, message):
    if not condition: raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def finite(value, lower=0, upper=100):
    require(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and lower <= value <= upper,
            'Invalid quota number')
    return value


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timestamp requires a timezone')
    return result.timestamp()


def native_config(*, offline):
    # No host config/keyring discovery or API-key fallback. The offline-only
    # override cannot be used as a claim about the real subscription endpoint.
    text = '''forced_login_method = "chatgpt"
cli_auth_credentials_store = "file"
model = "gpt-6.1-sol"
model_reasoning_effort = "medium"
web_search = "disabled"
[agents]
enabled = false
[features]
apps = false
plugins = false
[analytics]
enabled = false
[otel]
exporter = "none"
trace_exporter = "none"
metrics_exporter = "none"
'''
    if offline:
        text = 'chatgpt_base_url = "https://127.0.0.1:8768/backend-api"\nmodel_provider = "subscription-fixture"\n' + text
        text += '''[model_providers.subscription-fixture]
name = "Offline subscription fixture"
base_url = "https://127.0.0.1:8768/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
request_max_retries = 0
stream_max_retries = 0
''' 
    return text


def snapshot(document):
    """Validate a coordinator envelope around the native full RPC response.

    account_scope is a local non-secret authorization alias, not an identity
    authenticated by quota percentages. Raw native responses are hash-bound.
    """
    require(document.get('kind') == 'subscription-quota-snapshot-v1' and isinstance(document.get('synthetic'), bool), 'Wrong quota snapshot class')
    require(isinstance(document.get('account_scope'), str) and document['account_scope'], 'Missing account scope alias')
    require(document.get('auth_mode') == 'chatgpt' and document.get('method') == 'account/rateLimits/read', 'Subscription auth/full quota RPC required')
    timestamp(document['observed_at'])
    result = document['result']
    require(isinstance(result, dict) and 'error' not in result, 'Quota RPC failed')
    buckets = result.get('rateLimitsByLimitId')
    require(isinstance(result.get('accountId'), str) and result['accountId'], 'Backend account identity unavailable')
    if buckets is None:
        single = result.get('rateLimits')
        require(isinstance(single, dict) and single.get('limitId'), 'Quota buckets unavailable')
        buckets = {single['limitId']: single}
    require(isinstance(buckets, dict) and buckets, 'Quota buckets unavailable')
    measured = {}
    for key, bucket in buckets.items():
        require(isinstance(key, str) and key and bucket.get('limitId') == key, 'Unbound quota bucket')
        windows = {}
        for name in ['primary', 'secondary']:
            window = bucket.get(name)
            require(isinstance(window, dict), 'Both quota windows must be observable')
            finite(window['usedPercent'])
            finite(window['windowDurationMins'], 1, 525600)
            require(isinstance(window['resetsAt'], int) and not isinstance(window['resetsAt'], bool) and window['resetsAt'] > timestamp(document['observed_at']), 'Expired/invalid quota reset')
            windows[name] = window
        measured[key] = {'windows': windows, 'credits': bucket.get('credits'),
                         'limit_reached': bucket.get('rateLimitReachedType'), 'plan_type': bucket.get('planType')}
    return measured


def admission(before, *, now, account_scope, account_id, allow_synthetic=False):
    """A quota check never authorizes consumption. Unknown/credit-backed stops."""
    try:
        require(before['synthetic'] is allow_synthetic, 'Synthetic/live quota mismatch')
        require(before['account_scope'] == account_scope, 'Wrong subscription account scope')
        age = timestamp(now) - timestamp(before['observed_at'])
        require(0 <= age <= 60, 'Quota snapshot is stale or from the future')
        buckets = snapshot(before)
        require(before['result']['accountId'] == account_id, 'Backend account differs from approved scope')
        require(before['result'].get('ordinaryUsageAllowed') is True, 'Backend included-usage permission is unknown or denied')
        for bucket in buckets.values():
            require(bucket['limit_reached'] is None, 'Quota limit reached')
            credits = bucket['credits']
            require(isinstance(credits, dict) and credits.get('hasCredits') is False and credits.get('unlimited') is False,
                    'Credit-backed or unknown funding requires review')
            for window in bucket['windows'].values():
                require(window['resetsAt'] > timestamp(now), 'Quota window expired')
                require(100 - window['usedPercent'] >= read(BASE / 'plan.json')['limits']['minimum_remaining_percent'], 'Insufficient included allowance')
        return {'quota_ready': True, 'execution_authorized': False}
    except (ValueError, KeyError, TypeError) as error:
        return {'quota_ready': False, 'execution_authorized': False, 'reason': str(error)}


def reconcile(before, after):
    """Rounded shared-account deltas are observations, never exact run costs."""
    report = {'kind': 'subscription-quota-reconciliation-v1', 'synthetic': before.get('synthetic'),
              'account_scope': before.get('account_scope'), 'source': 'native account/rateLimits/read', 'cost_usd': None, 'exact_run_quota_consumption': None,
              'attribution': 'shared_account_observation', 'automatic_next_attempt': False, 'deltas': {}, 'issues': []}
    try:
        require(before['account_scope'] == after['account_scope'] and before['synthetic'] is after['synthetic'], 'Quota account/class changed')
        require(timestamp(before['observed_at']) <= timestamp(after['observed_at']), 'Quota observations out of order')
        first, last = snapshot(before), snapshot(after)
        require(after['result'].get('ordinaryUsageAllowed') is True, 'Post-run included-usage permission is unknown or denied')
        require(all(isinstance(bucket['credits'], dict) and bucket['credits'].get('hasCredits') is False and bucket['credits'].get('unlimited') is False for bucket in last.values()), 'Post-run funding is credit-backed or unknown')
        require(before['result']['accountId'] == after['result']['accountId'], 'Backend account identity changed')
        require(first.keys() == last.keys(), 'Quota bucket set changed')
        for key in first:
            require(first[key]['plan_type'] == last[key]['plan_type'], 'Subscription plan changed')
            for name in first[key]['windows']:
                a, b = first[key]['windows'][name], last[key]['windows'][name]
                require(a['resetsAt'] == b['resetsAt'] and a['windowDurationMins'] == b['windowDurationMins'], 'Quota reset/window changed')
                delta = b['usedPercent'] - a['usedPercent']
                require(delta >= 0, 'Quota decreased; cannot attribute across reset or concurrent adjustments')
                report['deltas'][key + '/' + name] = delta
        report['above_proposed_target'] = any(x > read(BASE / 'plan.json')['limits']['max_observed_delta_percentage_points'] for x in report['deltas'].values())
    except (ValueError, KeyError, TypeError) as error:
        report['deltas'] = {}; report['issues'].append(str(error))
    return report


def validate_record(record):
    require(record.get('kind') == 'subscription-pilot-run-v1' and record.get('funding') == 'chatgpt_subscription', 'Separate subscription record required')
    require(record.get('cost_usd') is None and record.get('exact_run_quota_consumption') is None, 'Subscription cost/consumption must not be fabricated')
    require(record.get('status') in ['prepared', 'running', 'completed', 'aborted'], 'Unknown subscription lifecycle')
    require(record.get('execution_authorized') is False, 'This preparation does not implement live authorization')
    if record['status'] == 'prepared':
        require(record.get('started_at') is None and record.get('verdict') is None and record.get('observed_model') is None, 'Prepared record cannot contain outcomes')
    if record.get('synthetic'):
        require(record.get('observed_model') is None and record.get('live_qualification') == 'unverified', 'Synthetic model cannot qualify live subscription')
    return True
