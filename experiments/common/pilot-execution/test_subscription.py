"""Separate subscription policy; synthetic documents only, no auth/network reads."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[2] / 'codex/subscription-pilot/subscription_pilot.py'
spec = importlib.util.spec_from_file_location('subscription_policy_tests', path)
pilot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)


def quota():
    bucket = {'limitId': 'codex', 'planType': 'pro', 'rateLimitReachedType': None,
        'credits': {'hasCredits': False, 'unlimited': False, 'balance': '0'},
        'primary': {'usedPercent': 10, 'windowDurationMins': 300, 'resetsAt': 1794067200},
        'secondary': {'usedPercent': 20, 'windowDurationMins': 10080, 'resetsAt': 1794153600}}
    return {'kind': 'subscription-quota-snapshot-v1', 'synthetic': True, 'account_scope': 'fixture-account',
        'auth_mode': 'chatgpt', 'method': 'account/rateLimits/read', 'observed_at': '2026-11-07T10:00:00Z',
        'result': {'accountId': 'fixture-account-id', 'ordinaryUsageAllowed': True, 'rateLimits': deepcopy(bucket), 'rateLimitsByLimitId': {'codex': bucket}}}


class SubscriptionPolicyTests(unittest.TestCase):
    def ready(self, value, **kwargs):
        return pilot.admission(value, now=kwargs.get('now', '2026-11-07T10:00:30Z'),
                               account_scope='fixture-account', account_id='fixture-account-id', allow_synthetic=kwargs.get('allow_synthetic', True))

    def test_quota_readiness_never_authorizes_a_run(self):
        result = self.ready(quota())
        self.assertTrue(result['quota_ready']); self.assertIs(result['execution_authorized'], False)
        self.assertFalse(self.ready(quota(), allow_synthetic=False)['quota_ready'])

    def test_missing_denied_credit_backed_or_stale_quota_blocks(self):
        changes = []
        for key, value in [('ordinaryUsageAllowed', None), ('ordinaryUsageAllowed', False)]:
            doc = quota(); doc['result'][key] = value; changes.append(doc)
        for key, value in [('credits', None), ('credits', {'hasCredits': True, 'unlimited': False}),
                           ('primary', None), ('secondary', None), ('rateLimitReachedType', 'rate_limit_reached')]:
            doc = quota(); doc['result']['rateLimitsByLimitId']['codex'][key] = value; changes.append(doc)
        for value in [float('nan'), True, -1, 101, 90]:
            doc = quota(); doc['result']['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = value; changes.append(doc)
        doc = quota(); doc['account_scope'] = 'other'; changes.append(doc)
        doc = quota(); doc['result']['accountId'] = 'wrong-account'; changes.append(doc)
        doc = quota(); doc['auth_mode'] = 'apikey'; changes.append(doc)
        for doc in changes:
            with self.subTest(doc=doc): self.assertFalse(self.ready(doc)['quota_ready'])
        for now in ['2026-11-07T10:02:00Z', '2026-11-07T09:59:00Z']:
            self.assertFalse(self.ready(quota(), now=now)['quota_ready'])

    def test_all_buckets_are_checked_and_fallback_needs_an_explicit_id(self):
        doc = quota(); second = deepcopy(doc['result']['rateLimitsByLimitId']['codex'])
        second['limitId'] = 'extra'; second['primary']['usedPercent'] = 99
        doc['result']['rateLimitsByLimitId']['extra'] = second
        self.assertFalse(self.ready(doc)['quota_ready'])
        doc = quota(); del doc['result']['rateLimitsByLimitId']
        self.assertTrue(self.ready(doc)['quota_ready'])
        doc['result']['rateLimits']['limitId'] = None
        self.assertFalse(self.ready(doc)['quota_ready'])

    def test_shared_rounded_delta_is_not_exact_run_consumption_or_zero_cost(self):
        before = quota(); after = deepcopy(before); after['observed_at'] = '2026-11-07T10:00:30Z'
        after['result']['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = 12
        report = pilot.reconcile(before, after)
        self.assertEqual(report['deltas']['codex/primary'], 2)
        self.assertIs(report['synthetic'], True); self.assertEqual(report['account_scope'], 'fixture-account')
        self.assertEqual(report['deltas']['codex/secondary'], 0)
        self.assertIsNone(report['cost_usd']); self.assertIsNone(report['exact_run_quota_consumption'])
        self.assertEqual(report['attribution'], 'shared_account_observation')
        self.assertFalse(report['automatic_next_attempt'])
        after['result']['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = 17
        self.assertTrue(pilot.reconcile(before, after)['above_proposed_target'])

    def test_reset_account_plan_or_window_change_invalidates_deltas(self):
        before = quota()
        for change in ['account', 'backend_account', 'funding', 'denied', 'plan', 'reset', 'window', 'decrease', 'class', 'bucket']:
            after = deepcopy(before); bucket = after['result']['rateLimitsByLimitId']['codex']
            if change == 'account': after['account_scope'] = 'other'
            if change == 'backend_account': after['result']['accountId'] = 'other'
            if change == 'funding': bucket['credits'] = None
            if change == 'denied': after['result']['ordinaryUsageAllowed'] = False
            if change == 'plan': bucket['planType'] = 'plus'
            if change == 'reset': bucket['primary']['resetsAt'] += 300
            if change == 'window': bucket['primary']['windowDurationMins'] += 1
            if change == 'decrease': bucket['primary']['usedPercent'] -= 1
            if change == 'class': after['synthetic'] = False
            if change == 'bucket': after['result']['rateLimitsByLimitId'] = {'other': bucket}
            result = pilot.reconcile(before, after)
            with self.subTest(change=change):
                self.assertEqual(result['deltas'], {}); self.assertTrue(result['issues'])

    def test_profile_is_chatgpt_only_and_live_has_no_fixture_endpoint(self):
        live = pilot.native_config(offline=False); fixture = pilot.native_config(offline=True)
        self.assertIn('forced_login_method = "chatgpt"', live)
        self.assertIn('cli_auth_credentials_store = "file"', live)
        self.assertIn('apps = false', live); self.assertIn('plugins = false', live)
        self.assertNotIn('127.0.0.1', live); self.assertNotIn('base_url', live)
        self.assertIn('requires_openai_auth = true', fixture)
        self.assertNotIn('env_key', fixture)
        plan = pilot.read(pilot.BASE / 'plan.json')
        self.assertFalse(plan['execution_authorized']); self.assertFalse(plan['live_launcher_implemented'])

    def test_record_cannot_promote_fixtures_or_fabricate_subscription_cost(self):
        record = {'kind': 'subscription-pilot-run-v1', 'funding': 'chatgpt_subscription', 'cost_usd': None,
            'exact_run_quota_consumption': None, 'execution_authorized': False, 'status': 'prepared',
            'synthetic': True, 'observed_model': None, 'started_at': None, 'verdict': None, 'live_qualification': 'unverified'}
        self.assertTrue(pilot.validate_record(record))
        for patch in [{'cost_usd': 0}, {'exact_run_quota_consumption': 0}, {'observed_model': 'gpt-6.1-sol'},
                      {'execution_authorized': True}, {'live_qualification': 'qualified'}, {'verdict': 'pass'}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError): pilot.validate_record(record | patch)


if __name__ == '__main__': unittest.main()
