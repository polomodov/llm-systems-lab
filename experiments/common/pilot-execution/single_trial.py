"""One pinned Harbor Trial, with explicit admission and evidence collection.

Default planning is data-only. Offline execution uses a scratch lab catalog,
fake credentials and a loopback fixture. Real execution requires a separately
issued, exact-run authorization file and never advances to another slot.
"""
import argparse
from contextlib import contextmanager
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import sys
import uuid

from common import BASE, ROOT, NATIVE, INTEROP, command, load, operator_document, operator_file, read, require, sha, write

import hn_o01
import hn_o01_billing

a = load('single_trial_accounting', NATIVE / 'accounting.py')
FAKE_KEY = 'offline-fixture-not-a-secret'
RUN_PATTERN = r'\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*'


def isolate(host, plugins):
    require(host.startswith('unix://'), 'Only a local Unix Docker socket is allowed')
    private = BASE / '.cache' / ('home-' + uuid.uuid4().hex)
    config = private / '.docker'
    config.mkdir(parents=True)
    write(config / 'config.json', {'cliPluginsExtraDirs': [str(plugins.resolve())]})
    path = os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    os.environ.clear()
    os.environ.update(PATH=path, HOME=str(private), DOCKER_CONFIG=str(config),
                      DOCKER_HOST=host, HARBOR_TELEMETRY='0', PYTHONDONTWRITEBYTECODE='1',
                      LITELLM_LOCAL_MODEL_COST_MAP='True', LC_ALL='C.UTF-8')
    sys.dont_write_bytecode = True
    def no_host_ip(event, args):
        if event == 'socket.connect' and args[0].family != socket.AF_UNIX:
            raise RuntimeError('Host IP connections are disabled; Docker uses its Unix socket')
    sys.addaudithook(no_host_ip)


def validate_permit(permit, record, bundle, *, now=None):
    """A local operator receipt is separate from the immutable preparation plan."""
    require(isinstance(permit, dict), 'An exact-run authorization is required')
    stamp = now or datetime.now(timezone.utc)
    expected = {'kind': 'harbor-single-trial-authorization-v1', 'allow_paid': True,
                'max_trials': 1, 'run_id': record['run_id'],
                'slot_id': read(bundle / 'inputs/pilot-slot.json')['slot_id'],
                'plan_sha256': sha(bundle / 'inputs/plan.json'),
                'inputs_sha256': record['inputs']['manifest_sha256'],
                'runner_sha256': sha(Path(__file__)), 'common_sha256': sha(BASE / 'common.py'),
                'accounting_sha256': sha(NATIVE / 'accounting.py'), 'budget_target_usd': record['loop']['budget_usd']}
    if expected['slot_id'] == 'HN-O01':
        require(isinstance(permit.get('billing_api_key_id'), str) and permit['billing_api_key_id'].strip(), 'HN-O01 requires the attributable API key ID, never its secret')
        expected.update(collector_sha256=sha(BASE / 'hn_o01.py'), reconciler_sha256=sha(BASE / 'hn_o01_billing.py'), telemetry_sha256=sha(BASE / 'otel_receiver.mjs'))
    require(all(permit.get(key) == value for key, value in expected.items()), 'Authorization does not bind this exact one-Trial execution')
    require(permit.get('approved_by') and permit.get('billing_project'), 'Authorization requires an operator and attributable billing project')
    expiry = datetime.fromisoformat(permit['expires_at'].replace('Z', '+00:00'))
    require(expiry.tzinfo is not None and expiry > stamp, 'Authorization has expired or lacks a timezone')
    require(isinstance(permit.get('previous_run_ids'), list), 'Explicit prior ordered attempts are required')


def selected_credential(path, name):
    """Called only after exact authorization and admission. Never source an env file."""
    values = []
    for line in path.read_text().splitlines():
        match = re.fullmatch(re.escape(name) + r'=([A-Za-z0-9_./+\-=]+)', line)
        if line.startswith(name + '='):
            require(match is not None, 'Selected credential is not a literal assignment')
            values.append(match[1])
    require(len(values) == 1, 'Selected credential must occur exactly once as a literal in .env')
    return values[0]


def config_for(slot, package, directory, trial_name, offline):
    agent = {'name': slot['harbor_agent'], 'model_name': slot['model_name'],
             'model_api_key_name': slot['model_api_key_name'],
             'kwargs': dict(slot['planned_kwargs'])}
    if slot.get('model_api_format'):
        agent['model_api_format'] = slot['model_api_format']
    if offline:
        agent.update(base_url='http://127.0.0.1:8768/v1',
                     model_api_key_name='HARBOR_OFFLINE_FIXTURE_KEY')
    if slot['slot_id'] == 'HN-O01':
        agent['kwargs']['config'] = {**agent['kwargs'].get('config', {}),
            'analytics': {'enabled': False},
            'otel': {'exporter': {'otlp-http': {'endpoint': 'http://127.0.0.1:8769/v1/logs', 'protocol': 'json'}},
                     'trace_exporter': 'none', 'metrics_exporter': 'none', 'log_user_prompt': False}}
    return {'task': {'path': str(package)}, 'trial_name': trial_name,
            'trials_dir': str(directory), 'agent': agent,
            'environment': {'type': 'docker', 'delete': True, 'force_build': False}}


def scratch_attempt(directory):
    """Fresh separate catalog; never mutate any existing results/runs directory."""
    require(directory.resolve().is_relative_to((BASE / '.cache').resolve()), 'Offline records must stay in the dedicated scratch cache')
    root = directory / 'lab'
    catalog = root / 'experiments/common/harbor-native-pilot/task'
    catalog.mkdir(parents=True)
    for filename in ['registration.json', 'contract.md', 'agent-spec.md']:
        shutil.copy2(NATIVE / 'task' / filename, catalog / filename)
    plan = read(NATIVE / 'plan.json')
    slot = plan['slots'][0]
    require(slot['harness'] == 'codex', 'Offline integration probe is the first pinned Codex slot')
    plan['pilot_id'] = 'offline-single-trial-' + uuid.uuid4().hex
    slot['run_id'] = datetime.now(timezone.utc).strftime('%Y-%m-%d') + '-fixture-single-trial-' + uuid.uuid4().hex[:10]
    profile = root / 'experiments/codex'
    profile.mkdir()
    (profile / 'README.md').write_text('Synthetic isolated catalog; not a campaign result.\n')
    package_lock = read(NATIVE / 'package-lock.json')
    package = next(row for row in package_lock['packages'] if row['slot_id'] == slot['slot_id'] and row['mode'] == 'offline')
    package = {**package, 'mode': 'prepared'}
    package_lock['packages'] = [package]
    plan_path, lock_path = directory / 'plan.json', directory / 'packages.json'
    write(plan_path, plan)
    write(lock_path, package_lock)
    bundle = a.prepare(root, slot['run_id'], slot, NATIVE / package['path'],
                       NATIVE / 'runtime-lock.json', lock_path, plan_path,
                       source_revision=None)
    record = read(bundle / 'run.json')
    record['sandbox']['network'] = 'off'
    record['execution']['network_policy'] = 'All Harbor phases deny controlled TCP; synthetic loopback fixture only; DNS/ICMP remain permitted'
    record['notes'] = 'Offline scratch condition only. Synthetic responses, no provider credentials, no live-model identity or billing; never a campaign result.'
    a.save_record(bundle, record)
    a.core_check(root, record)
    return root, bundle


def coordinator_sources():
    paths = [Path(__file__), BASE / 'common.py', NATIVE / 'accounting.py', NATIVE / 'offline_smoke.py', BASE / 'hn_o01.py', BASE / 'hn_o01_billing.py', BASE / 'otel_receiver.mjs']
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


async def runtime_probe(slot, image):
    profile = read(ROOT / 'experiments' / slot['harness'] / 'harness.json')
    argv = profile['version_command']
    # Profile version commands print exact package versions; native stderr is
    # separately preserved by Trial setup. No credentials or host mounts here.
    output = await command('docker', 'run', '--rm', '--pull=never', '--network', 'none',
        '--user', '1000:1000', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--env', 'HOME=/tmp', '--entrypoint', argv[0], image, *argv[1:])
    versions = re.findall(r'(?<![0-9.])\d+\.\d+\.\d+(?![0-9.])', output)
    require(versions == [slot['version']], 'Image version differs from the sealed slot')
    actual = (await command('docker', 'image', 'inspect', image, '--format', '{{.Id}}')).strip()
    require(actual == image, 'Image identity differs from the sealed slot')
    return {'image_id': image, 'observed_version': slot['version'], 'version_output': output}


async def owned_containers(prefix):
    data = await command('docker', 'ps', '-a', '--format', '{{.ID}} {{.Label "com.docker.compose.project"}}')
    return [line.split()[0] for line in data.splitlines()
            if len(line.split()) == 2 and line.split()[1].startswith(prefix)]


async def observe_runtime(prefix, captured):
    for container in await owned_containers(prefix):
        if container in captured:
            continue
        text = await command('docker', 'inspect', container, '--format',
            '{"image":{{json .Image}},"mounts":{{json .Mounts}},"labels":{{json .Config.Labels}}}')
        captured[container] = json.loads(text)


async def cleanup(prefix):
    remaining = await owned_containers(prefix)
    if remaining:
        await command('docker', 'rm', '-f', *remaining)
    return not await owned_containers(prefix)


def reference(file, pointer, kind):
    return {'file': file, 'pointer': pointer, 'kind': kind}


def redact_tree(directory, secret):
    if not secret:
        return
    root = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for _, directories, files, parent in os.fwalk('.', dir_fd=root, follow_symlinks=False):
            for name in directories:
                require(stat.S_ISDIR(os.stat(name, dir_fd=parent, follow_symlinks=False).st_mode),
                        'Symlink in collected evidence')
            for name in files:
                descriptor = os.open(name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                with os.fdopen(descriptor, 'r+b') as stream:
                    info = os.fstat(stream.fileno())
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                            'Collected evidence must be regular files without links')
                    content = stream.read()
                    if secret.encode() in content:
                        stream.seek(0)
                        stream.write(content.replace(secret.encode(), b'[REDACTED]'))
                        stream.truncate()
    finally:
        os.close(root)


async def run_trial(root, bundle, host, offline, permit=None):
    if offline:
        require(root.resolve().is_relative_to((BASE / '.cache').resolve()) and
                bundle.resolve().is_relative_to(root.resolve()), 'Offline execution requires a scratch catalog')
    record, slot = read(bundle / 'run.json'), read(bundle / 'inputs/pilot-slot.json')
    if not offline:
        validate_permit(permit, record, bundle)
    from harbor.models.trial.config import TrialConfig
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial
    from harbor.publisher.packager import Packager
    from harbor.utils.trajectory_validator import TrajectoryValidator
    prior = load('single_trial_network_observer', INTEROP / 'synthetic_controls.py')
    a.core_check(root, record)
    require(record['status'] == 'prepared', 'Only an unused prepared attempt can execute')
    plan = read(bundle / 'inputs/plan.json')
    previous = [] if offline else permit['previous_run_ids']
    require(a.admission(root, previous, slot, plan)['admitted'], 'Prior attempt qualification or accounting blocks admission')
    harbor_head = (await command('git', '-C', INTEROP / '.cache/harbor', 'rev-parse', 'HEAD')).strip()
    require(harbor_head == plan['harbor_commit'], 'Harbor source pin differs from the sealed plan')
    require(not (await command('git', '-C', INTEROP / '.cache/harbor', 'status', '--porcelain', '--untracked-files=no')).strip(), 'Pinned Harbor source has tracked modifications')
    sources_before = coordinator_sources()
    probe = await runtime_probe(slot, record['execution']['image_id'])
    # The claim is exclusive and never removed: setup failures and retries do
    # not silently reuse this attempt. A new attempt needs a new record/permit.
    directory = bundle / 'trace/collection'
    package = bundle / 'inputs/task-package'
    task_digest = 'sha256:' + Packager.compute_content_hash(package)[0]
    prefix = 'controlled-' + uuid.uuid4().hex
    config = config_for(slot, package, directory, prefix, offline)
    secret = None
    key = 'HARBOR_OFFLINE_FIXTURE_KEY' if offline else slot['model_api_key_name']
    if offline:
        secret = FAKE_KEY
    else:
        secret = selected_credential(ROOT / '.env', key)
    config['agent']['env'] = {
        **slot.get('planned_env', {}), **(hn_o01.TRACE_ENV if slot['slot_id'] == 'HN-O01' else {}),
        key: secret, 'HOME': '/home/agent',
        'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}
    directory.mkdir()
    write(bundle / 'trace/execution-claim.json', {'offline': offline, 'permit': permit,
                                                'runner_sha256': sha(Path(__file__)), 'source_sha256': sources_before})
    source_snapshot = directory / 'coordinator-sources'
    source_snapshot.mkdir()
    for relative in sources_before:
        shutil.copy2(ROOT / relative, source_snapshot / Path(relative).name)
    receipt = {**probe, 'command': [sys.executable, str(Path(__file__)), *sys.argv[1:]],
               'cwd': '/app', 'started_at': a.now()}
    a.mark_started(root, record['run_id'], receipt)
    sidecars, hooks, runtime, caught, diagnostic = {}, [], {}, None, None
    trial = None
    try:
        trial = await Trial.create(TrialConfig.model_validate(config))
        async def agent_start(event):
            env = trial.agent_environment
            boundary = await env.exec('id -u; test ! -e /tests; test ! -e /opt/verifier-fixtures; test ! -e /var/run/docker.sock', user='1000:1000')
            require(boundary.return_code == 0 and boundary.stdout.strip() == '1000', 'Agent boundary probe failed')
            if slot['slot_id'] == 'HN-O01':
                await env.upload_file(BASE / 'otel_receiver.mjs', '/app/hn-o01-otel-receiver.mjs')
                started_sink = await env.exec('node /app/hn-o01-otel-receiver.mjs > /logs/agent/hn-o01-otel-sink.log 2>&1 &', user='1000:1000')
                require(started_sink.return_code == 0, 'Cannot start local telemetry sink')
                for _ in range(20):
                    ready = await env.exec('test -f /logs/agent/hn-o01-otel-ready', user='1000:1000')
                    if ready.return_code == 0:
                        break
                    await asyncio.sleep(0.05)
                require(ready.return_code == 0, 'Local telemetry sink not ready')
            if offline:
                await env.upload_file(NATIVE / 'mock-provider.mjs', '/app/offline-provider.mjs')
                started = await env.exec('node /app/offline-provider.mjs > /logs/agent/mock-server.log 2>&1 &', user='1000:1000')
                require(started.return_code == 0, 'Cannot start in-container loopback fixture')
                await asyncio.sleep(0.2)
            hooks.append({'event': event.event.value, 'at': event.timestamp.isoformat(), 'uid': 1000})
        trial.add_hook(TrialEvent.AGENT_START, agent_start)
        async with asyncio.timeout(480):
            active = asyncio.create_task(trial.run())
            try:
                while not active.done():
                    await observe_runtime(prefix, runtime)
                    if offline:
                        await prior.observe_sidecars(prefix, sidecars)
                    await asyncio.sleep(0.25)
                await active
            finally:
                if not active.done():
                    active.cancel()
                    await asyncio.gather(active, return_exceptions=True)
    except (Exception, asyncio.CancelledError) as error:
        caught = type(error).__name__
        diagnostic = str(error).replace(secret, '[REDACTED]') if secret else str(error)
    finally:
        try:
            cleaned = await cleanup(prefix)
        except Exception as error:
            cleaned = False
            caught = caught or 'CleanupFailure'
            diagnostic = type(error).__name__
        redact_tree(directory, None if offline else secret)
        secret = None
    trial_dir = directory / prefix
    if trial_dir.exists():
        result = read(trial_dir / 'result.json') if (trial_dir / 'result.json').exists() else {}
    else:
        trial_dir.mkdir()
        result = {}
    write(directory / 'controller.json', {'hooks': hooks, 'runtime_probe': probe, 'caught': caught, 'diagnostic': diagnostic,
          'cleanup_complete': cleaned, 'sidecars': sidecars, 'runtime': runtime, 'offline': offline,
          'finished_at': a.now(), 'source_sha256': sources_before,
          'sources_stable': sources_before == coordinator_sources(), 'task_digest_before': task_digest,
          'task_digest_after': 'sha256:' + Packager.compute_content_hash(package)[0]})
    if slot['slot_id'] == 'HN-O01':
        hn_o01.collect(directory, prefix, record, offline=offline)
    write(directory / 'state.json', {'phase': 'collected-awaiting-finalization', 'run_id': record['run_id'],
          'trial_directory': prefix, 'automatic_next_trial': False, 'provider_billing': 'unknown',
          'offline': offline, 'synthetic_usage_not_billing': offline})
    write(bundle / 'trace/collection-seal.json', {'files': a.inventory(directory), 'offline': offline,
          'run_id': record['run_id'], 'runner_sha256': sha(Path(__file__)), 'common_sha256': sha(BASE / 'common.py')})
    return directory, result


def import_collection(root, bundle, directory, *, offline, billing=None, billing_evidence=None, observation=None):
    """Freeze evidence once. Live finalization waits for actual settled billing."""
    record = read(bundle / 'run.json')
    seal = read(bundle / 'trace/collection-seal.json')
    require(seal['files'] == a.inventory(directory), 'Collected evidence changed after sealing')
    require(seal['offline'] is offline and seal['run_id'] == record['run_id'], 'Collection seal class/attempt mismatch')
    state = read(directory / 'state.json')
    require(state['run_id'] == record['run_id'] and state['offline'] is offline, 'Collection class/attempt mismatch')
    mapped = None
    if read(bundle / 'inputs/pilot-slot.json')['slot_id'] == 'HN-O01':
        mapped = hn_o01.observations(directory, record, offline=offline)
        require(observation is None or observation == mapped, 'HN-O01 observations are generated from sealed native evidence; overrides are forbidden')
    if not offline:
        require(billing and billing.get('status') == 'settled' and billing.get('run_id') == record['run_id'], 'Live finalization waits for attributable settled billing')
        require(not billing.get('synthetic'), 'Synthetic billing cannot finalize a live attempt')
        permit = read(bundle / 'trace/execution-claim.json')['permit']
        require(billing.get('project') == permit['billing_project'] and billing.get('provider') == record['model']['provider'], 'Billing project/provider differs from authorized execution')
        require(isinstance(billing.get('cost_usd'), (int, float)) and not isinstance(billing['cost_usd'], bool) and math.isfinite(billing['cost_usd']) and billing['cost_usd'] >= 0, 'Invalid settled cost')
        require(billing_evidence is not None and not billing_evidence.is_symlink() and billing_evidence.is_file(), 'Provider billing export evidence is required')
        require(sha(billing_evidence) == billing.get('evidence_sha256') and billing.get('attribution'), 'Billing export hash and attribution method are required')
        if mapped is not None:
            hn_o01_billing.verify_receipt(record, directory, seal, billing, read(billing_evidence))
    evidence = bundle / 'trace/import-source'
    require(not evidence.exists(), 'Finalization already started; inspect rather than overwrite')
    shutil.copytree(directory, evidence)
    trial_path = state['trial_directory']
    raw = evidence / trial_path
    controller = read(evidence / 'controller.json')
    result = read(raw / 'result.json') if (raw / 'result.json').exists() else {}
    terminal = False
    try:
        smoke = load('single_trial_terminal_check', NATIVE / 'offline_smoke.py')
        smoke.terminal_event(record['harness']['name'], raw / 'agent')
        terminal = True
    except (ValueError, OSError, KeyError):
        pass
    verifier_path = raw / 'verifier/evidence.json'
    reward = result.get('verifier_result', {}).get('rewards', {}).get('reward') if result.get('verifier_result') else None
    verifier = None
    artifact = raw / 'artifacts/result.json'
    if reward in (0, 1) and verifier_path.exists():
        verifier = {'result': 'pass' if reward == 1 else 'fail',
                    'check_output': 'Frozen independent Harbor verifier reward=' + str(reward),
                    'artifact_file': trial_path + '/artifacts/result.json',
                    'artifact_sha256': sha(artifact) if artifact.is_file() else None,
                    'verifier_sha256': sha(bundle / 'inputs/task-package/tests/evaluate.py')}
        if not artifact.exists():
            verifier['artifact_absent'] = True
        write(evidence / 'verifier.json', verifier)
    boundary = {'passed': bool(controller['hooks']) and not controller['caught'] and controller['sources_stable']
                          and controller['task_digest_before'] == controller['task_digest_after'],
                'cleanup_complete': controller['cleanup_complete']}
    images = {item['image'] for item in controller.get('runtime', {}).values()}
    expected_verifier = read(bundle / 'inputs/runtime-lock.json')['verifier']['image_id']
    boundary['passed'] = boundary['passed'] and record['execution']['image_id'] in images
    if verifier:
        boundary['passed'] = boundary['passed'] and expected_verifier in images
        separate = read(verifier_path)
        boundary['passed'] = boundary['passed'] and separate.get('effective_uid') == 1000 and separate.get('fixture_writable') is False and separate.get('external_https_probe_blocked') is True
    write(evidence / 'boundary.json', boundary)
    native = raw / 'agent' / (record['harness']['name'] + '.txt')
    if not native.exists():
        native = evidence / 'missing-native.json'
        write(native, {'native_trace_available': False})
    observed = mapped if mapped is not None else observation or {}
    observed.update(native_log=str(native.relative_to(evidence)),
        atif=trial_path + '/agent/trajectory.json' if (raw / 'agent/trajectory.json').exists() else None,
        terminal_native_trace=terminal,
        verifier=reference('verifier.json', '', 'independent_verifier') if verifier else None,
        boundary=reference('boundary.json', '', 'coordinator_observation'),
        execution={'finished_at': controller['finished_at'],
                   'exit_code': 0 if not result.get('exception_info') and not controller['caught'] else 1,
                   'signal': None, 'timed_out': controller['caught'] == 'TimeoutError'})
    if offline:
        # Synthetic model identity/usage/price never enter billing/model evidence.
        observed.pop('billing', None)
        observed.pop('identity', None)
        observed['metrics'] = {}
    else:
        shutil.copy2(billing_evidence, evidence / 'provider-billing-export.json')
        write(evidence / 'billing.json', billing)
        observed['billing'] = reference('billing.json', '', 'provider_billing')
    return a.finish(root, record['run_id'], evidence, observed)


@contextmanager
def execution_lock():
    lock = BASE / '.cache/live-coordinator.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir()
    try:
        yield
    finally:
        lock.rmdir()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'offline', 'execute', 'finalize'])
    parser.add_argument('--run-id')
    parser.add_argument('--authorization', help='Plain filename under pilot-execution/.cache/operator')
    parser.add_argument('--billing', help='Plain filename under pilot-execution/.cache/operator')
    parser.add_argument('--observations', help='Plain filename under pilot-execution/.cache/operator')
    parser.add_argument('--docker-host', default='unix:///Users/apolomodov/.colima/default/docker.sock')
    parser.add_argument('--docker-plugin-dir', type=Path, default=INTEROP / '.cache/docker-plugins')
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps({'kind': 'single-trial-plan', 'execution_authorized': False,
                          'plan_sha256': sha(NATIVE / 'plan.json'), 'runner_sha256': sha(Path(__file__)),
                          'slots': [s['slot_id'] for s in read(NATIVE / 'plan.json')['slots']],
                          'max_trials_per_invocation': 1, 'automatic_retries': 0}))
        return
    if args.action == 'offline':
        isolate(args.docker_host, args.docker_plugin_dir)
        directory = BASE / '.cache' / ('offline-' + uuid.uuid4().hex)
        directory.mkdir()
        root, bundle = scratch_attempt(directory)
        collection, result = await run_trial(root, bundle, args.docker_host, True)
        final = import_collection(root, bundle, collection, offline=True)
        write(directory / 'summary.json', {'offline': True, 'provider_requests': 0, 'paid_runs': 0,
              'synthetic_usage_not_billing': True, 'run_id': final['run_id'], 'status': final['status'],
              'verdict': final['verdict']['result'], 'cost_usd': final['loop']['cost_usd'],
              'qualification': read(bundle / 'trace/accounting.json')['qualification'],
              'files': a.inventory(bundle), 'source_sha256': {str(p.relative_to(ROOT)): sha(p)
                 for p in [Path(__file__), BASE / 'common.py', BASE / 'hn_o01.py', BASE / 'hn_o01_billing.py', BASE / 'otel_receiver.mjs', NATIVE / 'accounting.py', NATIVE / 'mock-provider.mjs']}})
        print(json.dumps({'summary': str(directory / 'summary.json'), 'verdict': final['verdict']['result'],
                          'qualification': read(bundle / 'trace/accounting.json')['qualification']}))
        require(final['status'] == 'completed' and final['verdict']['result'] == 'pass', 'Offline Trial failed; retained its evidence')
        return
    require(args.run_id and re.fullmatch(RUN_PATTERN, args.run_id), 'An exact prepared run ID is required')
    bundle = a.safe(ROOT, 'results/runs/' + args.run_id)
    record = read(bundle / 'run.json')
    if args.action == 'finalize':
        require(args.billing, 'Finalization requires independent billing')
        require(args.observations or read(bundle / 'inputs/pilot-slot.json')['slot_id'] == 'HN-O01', 'Other slots require explicit provenance references')
        _, billing = operator_document(args.billing)
        export, _ = operator_file(billing['evidence_file'])
        observations = operator_document(args.observations)[1] if args.observations else None
        result = import_collection(ROOT, bundle, bundle / 'trace/collection', offline=False,
                                   billing=billing, billing_evidence=export, observation=observations)
        print(json.dumps({'run_id': result['run_id'], 'status': result['status']}))
        return
    require(args.authorization is not None, 'Paid execution is disabled without a separate exact-run authorization')
    _, permit = operator_document(args.authorization)
    validate_permit(permit, record, bundle)
    isolate(args.docker_host, args.docker_plugin_dir)
    with execution_lock():
        collection, _ = await run_trial(ROOT, bundle, args.docker_host, False, permit)
    print(json.dumps({'run_id': record['run_id'], 'phase': 'collected-awaiting-finalization',
                      'collection': str(collection), 'automatic_next_trial': False}))


if __name__ == '__main__':
    asyncio.run(main())
