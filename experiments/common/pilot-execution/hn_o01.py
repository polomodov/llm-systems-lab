"""HN-O01 provenance from Codex 0.167.0; no credentials, sockets or estimates.

Transport remains native. ServerModel logs are emitted by the pinned native
client after server response metadata; configuration/ATIF model labels are not
identity. Missing coverage is reported, never synthesized as a measured zero.
"""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from common import read, require, sha, write

TRACE_ENV = {'RUST_LOG': 'error,codex_core::session=info,codex_api::sse::responses=trace', 'NO_COLOR': '1'}
MODEL_EVENT = re.compile(r'^\S+\s+(?:INFO|WARN)\s+codex_core::session[^: ]*(?:::[^: ]+)*:\s+server reported model ([A-Za-z0-9._-]+) (?:\(matches requested model\)|while requested model was [A-Za-z0-9._-]+)$')
ANSI = re.compile(r'\x1b\[[0-9;]*m')
MAX_INT = 2**53 - 1


def number(value, *, integer=True):
    require(not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value) and 0 <= value <= MAX_INT and
            (not integer or isinstance(value, int)), 'Invalid native measurement')
    return value


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'UTC-offset timestamps are required')
    return result


def ref(file, pointer, kind):
    return {'file': file, 'pointer': pointer, 'kind': kind}


def inventory(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'No symlinks in HN-O01 telemetry')
        if path.is_file():
            files[str(path.relative_to(directory))] = sha(path)
    return files


def extract(raw, requested):
    """Read a captured native Trial; return derived values plus exact raw bindings."""
    native = raw / 'agent/codex.txt'
    lines = [ANSI.sub('', line) for line in native.read_text().splitlines()]
    events, models, responses = [], [], {}
    issues = []
    for index, line in enumerate(lines):
        if line.startswith('{'):
            try:
                event = json.loads(line)
                require(isinstance(event, dict), 'Native event is not an object')
                events.append(event)
            except (ValueError, TypeError):
                issues.append('Malformed native JSON event')
        model = MODEL_EVENT.fullmatch(line)
        if model:
            models.append({'model': model[1], 'line': index + 1, 'timestamp': line.split()[0]})
        if 'codex_api::sse::responses: SSE event: ' in line:
            try:
                prefix, payload = line.split('codex_api::sse::responses: SSE event: ', 1)
                require(re.fullmatch(r'\S+\s+TRACE\s+', prefix) is not None, 'Untrusted SSE prefix')
                event = json.loads(payload)
                if event.get('type') == 'response.completed':
                    response = event['response']; identity = response['id']
                    require(isinstance(identity, str) and identity, 'Missing response ID')
                    if identity in responses:
                        require(responses[identity]['response'] == response, 'Conflicting duplicate response')
                    responses[identity] = {'response': response, 'line': index + 1}
            except (ValueError, KeyError, TypeError):
                issues.append('Malformed or conflicting response completion')
    threads = [e.get('thread_id') for e in events if e.get('type') == 'thread.started']
    terminal = bool(events and events[-1].get('type') == 'turn.completed')
    sessions = sorted((raw / 'agent/sessions').rglob('*.jsonl'))
    rollouts, bindings = [], {}
    try:
        require(len(threads) == 1 and isinstance(threads[0], str), 'Exactly one native thread is required')
        require(len(sessions) == 1, 'HN-O01 requires one complete root rollout; child sessions need separate accounting')
        path = sessions[0]
        rollouts = [json.loads(line) for line in path.read_text().splitlines()]
        require(rollouts and rollouts[0]['type'] == 'session_meta', 'Missing session metadata')
        meta = rollouts[0]['payload']
        require(meta.get('id') == threads[0] and meta.get('cli_version') == '0.167.0' and
                meta.get('source') == 'exec' and meta.get('thread_source') == 'user', 'Wrong session/version/source')
        require(all(r.get('type') in ['session_meta', 'response_item', 'compacted', 'event_msg', 'turn_context', 'token_usage_record', 'world_state'] for r in rollouts), 'Unsupported rollout record type')
        require([r.get('ordinal') for r in rollouts] == list(range(len(rollouts))), 'Rollout is incomplete or duplicated')
        require(sum(r.get('payload', {}).get('type') == 'task_started' for r in rollouts) == 1 and
                sum(r.get('payload', {}).get('type') == 'task_complete' for r in rollouts) == 1 and terminal and
                rollouts[-1].get('payload', {}).get('type') == 'task_complete',
                'Native thread did not finish completely')
        bindings[str(path.relative_to(raw))] = sha(path)
    except (ValueError, KeyError, TypeError, OSError) as error:
        issues.append(str(error))
    values = {'tokens_in': None, 'tokens_out': None, 'turns': None, 'wall_clock_s': None,
              'compactions': None, 'subagents': None, 'permissions.asked': None, 'tool_operations': None}
    coverage = not issues
    usage = {}
    for row in rollouts:
        if row.get('type') != 'token_usage_record':
            continue
        payload = row['payload']; identity = payload.get('response_id')
        try:
            require(isinstance(identity, str) and identity and payload.get('thread_id') == threads[0], 'Unbound token usage record')
            measured = {key: number(payload['usage'][key]) for key in ['input_tokens', 'output_tokens']}
            require(identity not in usage, 'Repeated response usage would double count tokens')
            usage[identity] = measured
            if identity in responses:
                response = responses[identity]['response']
                require(response.get('status') == 'completed' and response.get('model') == requested and
                        all(response['usage'][key] == measured[key] for key in measured), 'Response/rollout usage or model mismatch')
        except (ValueError, KeyError, TypeError) as error:
            issues.append(str(error)); coverage = False
    completed = [e['usage'] for e in events if e.get('type') == 'turn.completed']
    try:
        require(coverage and usage and len(completed) == 1, 'Complete unique per-response usage is unavailable')
        for field, key in [('tokens_in', 'input_tokens'), ('tokens_out', 'output_tokens')]:
            total = number(sum(row[key] for row in usage.values()))
            require(number(completed[0][key]) == total, 'Terminal token aggregate differs from per-response records')
            values[field] = total
        # Model response completions, not Codex user turns. Native retry attempts
        # without a completed response are listed separately, not counted as turns.
        values['turns'] = len(usage)
        calls = [r['payload'] for r in rollouts if r.get('type') == 'response_item' and
                 r.get('payload', {}).get('type') in ['function_call', 'custom_tool_call', 'local_shell_call']]
        values['tool_operations'] = len(calls)
        values['compactions'] = sum(r.get('type') == 'compacted' for r in rollouts)
        values['subagents'] = 0  # Complete single root rollout, checked above; observation scope only.
    except (ValueError, KeyError, TypeError) as error:
        issues.append(str(error))
        for field in ['tokens_in', 'tokens_out', 'turns', 'tool_operations', 'compactions', 'subagents']:
            values[field] = None
    # Count native decision events, not the configured approval policy. A missing
    # or partial OTLP stream cannot establish a measured permission-request zero.
    otel_path = raw / 'agent/hn-o01-otel.jsonl'
    if otel_path.exists() and coverage and values['tool_operations'] is not None:
        try:
            decisions, tool_results = {}, {}
            for batch in map(json.loads, otel_path.read_text().splitlines()):
                for resource in batch['body']['resourceLogs']:
                    for scope in resource['scopeLogs']:
                        for event in scope['logRecords']:
                            attrs = {a['key']: a['value'].get('stringValue') for a in event.get('attributes', [])}
                            if attrs.get('event.name') not in ['codex.tool_decision', 'codex.tool_result']:
                                continue
                            require(attrs.get('conversation.id') == threads[0] and attrs.get('app.version') == '0.167.0', 'Unbound tool decision')
                            identity = attrs['call_id']
                            if attrs['event.name'] == 'codex.tool_result':
                                require(identity not in tool_results and attrs.get('tool_name') in ['exec', 'exec_command', 'write_stdin', 'apply_patch'], 'Unknown/duplicate tool result')
                                tool_results[identity] = attrs['tool_name']
                            else:
                                require(identity not in decisions and attrs.get('source') in ['Config', 'User', 'AutomatedReviewer'], 'Incomplete/duplicate tool decision')
                                decisions[identity] = attrs['source']
            expected_calls = {c['call_id'] for c in calls}
            approval_calls = {identity for identity, tool in tool_results.items() if tool != 'exec'}
            require(expected_calls and expected_calls.issubset(tool_results) and set(decisions) == approval_calls, 'Tool-decision coverage differs from native calls/results')
            values['permissions.asked'] = sum(source == 'User' for source in decisions.values())
            bindings[str(otel_path.relative_to(raw))] = sha(otel_path)
        except (ValueError, KeyError, TypeError):
            issues.append('Permission telemetry is absent, incomplete or unbound')

    result_path = raw / 'result.json'
    if result_path.exists():
        result = read(result_path)
        try:
            execution = result['agent_execution']
            seconds = (stamp(execution['finished_at']) - stamp(execution['started_at'])).total_seconds()
            values['wall_clock_s'] = number(seconds, integer=False)
            bindings['result.json'] = sha(result_path)
        except (ValueError, KeyError, TypeError):
            issues.append('Agent execution duration unavailable')
    identities = {m['model'] for m in models} | {v['response'].get('model') for v in responses.values()}
    mismatch = bool(identities - {requested}) or any(e.get('type') == 'model.rerouted' for e in events)
    # Each completed model call needs a native server-model report. SSE can
    # additionally bind each response ID; WS uses the native ServerModel path.
    model_coverage = bool(usage and coverage and terminal and
                          (len(models) >= len(usage) or responses and set(responses) == set(usage)))
    if responses and set(responses) != set(usage):
        model_coverage = False
        issues.append('SSE response IDs do not cover the native usage set')
    observed = next(iter(sorted(identities - {requested})), requested) if mismatch else requested if model_coverage and identities == {requested} else None
    bindings['agent/codex.txt'] = sha(native)
    return {'schema_version': 1, 'kind': 'hn-o01-native-measurements',
            'requested_model': requested, 'observed_model': observed, 'model_mismatch': mismatch,
            'identity_coverage_complete': model_coverage and not mismatch,
            'server_model_events': models, 'response_ids': sorted(usage),
            'response_set_sha256': hashlib.sha256(json.dumps(sorted(usage), separators=(',', ':')).encode()).hexdigest(),
            'values': values, 'raw_sha256': bindings, 'issues': sorted(set(issues)),
            'unavailable': {key: 'No complete native measurement for this field; not inferred from configuration or ATIF defaults'
                            for key, value in values.items() if value is None},
            'definitions': {'tokens_in': 'Sum unique native response input_tokens; cached tokens already included',
                'tokens_out': 'Sum unique native response output_tokens; reasoning tokens already included',
                'turns': 'Completed model responses with unique response_id, not user requests or failed HTTP attempts',
                'wall_clock_s': 'Harbor agent_execution finished_at minus started_at; excludes setup/verifier',
                'compactions': 'Compacted records in the complete single native rollout',
                'subagents': 'Child rollouts observed in the complete collected root-session tree',
                'tool_operations': 'Native function/custom/local-shell call records; not a task-success verdict',
                'permissions.asked': 'User-sourced native tool decisions with matching result IDs and complete outer-call coverage; not configuration-inferred'}}


def collect(collection, trial_name, record, *, offline):
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', trial_name) is not None, 'Invalid Trial directory selector')
    raw = collection / trial_name
    try:
        report = extract(raw, record['model']['id'])
    except (ValueError, OSError, KeyError, TypeError) as error:
        report = {'schema_version': 1, 'kind': 'hn-o01-native-measurements',
                  'collection_error': type(error).__name__, 'raw_sha256': inventory(raw),
                  'observed_model': None, 'values': {}, 'issues': ['Native telemetry could not be collected']}

    report.update(run_id=record['run_id'], offline=offline, synthetic=offline,
                  collector_sha256=sha(Path(__file__)), trial_directory=trial_name)
    write(collection / 'hn-o01-measurements.json', report)
    return report


def observations(collection, record, *, offline):
    """Recompute all derived values before using them; operator pointers cannot override."""
    report = read(collection / 'hn-o01-measurements.json')
    require(report['run_id'] == record['run_id'] and report['offline'] is offline and report['synthetic'] is offline,
            'HN-O01 evidence class/run mismatch')
    require(report['collector_sha256'] == sha(Path(__file__)), 'Collector changed after collection')
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', report['trial_directory']) is not None, 'Invalid Trial directory selector')
    require((collection / report['trial_directory']).resolve().parent == collection.resolve(), 'Trial directory escapes collection')
    if report.get('collection_error'):
        require(report['raw_sha256'] == inventory(collection / report['trial_directory']), 'Failed telemetry inventory changed')
        return {'metrics': {}, 'tool_operations': None, 'identity': None}
    expected = extract(collection / report['trial_directory'], record['model']['id'])
    require(all(report[key] == value for key, value in expected.items()), 'HN-O01 measurement binding changed')
    file = 'hn-o01-measurements.json'
    result = {'metrics': {}, 'tool_operations': None, 'identity': None}
    if not offline:
        for field, value in report['values'].items():
            if value is None:
                continue
            source = 'coordinator_observation' if field == 'wall_clock_s' else 'native_usage'
            pointer = ref(file, '/values/' + field, source)
            if field == 'tool_operations': result[field] = pointer
            else: result['metrics'][field] = pointer
        if report['observed_model']:
            result['identity'] = ref(file, '/observed_model', 'native_response')
    return result
