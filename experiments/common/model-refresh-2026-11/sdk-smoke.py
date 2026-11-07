"""Exercise actual lab entrypoints against isolated, synthetic loopback fixtures.

Pi transport is redirected by a test fetch shim. Containers have network none,
no mounts, fake auth and fresh HOME. No provider endpoint is accessible.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import socket
import sys
import uuid

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
NATIVE = BASE.with_name('harbor-native-2026-11')
ADAPTER = 'adapter.mjs'
SOL = 'gpt-6.1-sol'
SONNET = 'claude-sonnet-5-5'
FIXTURE_ORIGIN = 'http://127.0.0.1:8768'
FIXTURE_API = FIXTURE_ORIGIN + '/v1'
CASES = [('pi', 'anthropic', SONNET), ('pi', 'openai', SOL),
         ('mini-swe-agent', 'openai', SOL), ('claude-code', 'anthropic', SONNET),
         ('opencode', 'anthropic', SONNET), ('codex', 'openai', SOL)]
spec = importlib.util.spec_from_file_location('migration_native_smoke', NATIVE / 'offline_smoke.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


async def node_json(script, input_text=None, timeout_s=10):
    """Keep the event loop responsive and reap a failed/cancelled child."""
    process = await asyncio.create_subprocess_exec(
        'node', '--input-type=module', '-e', script,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        async with asyncio.timeout(timeout_s):
            stdout, stderr = await process.communicate(
                None if input_text is None else input_text.encode())
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode() or f'Node exited {process.returncode}')
    return json.loads(stdout)


def isolate_host(docker_host):
    if not docker_host.startswith('unix://'):
        raise ValueError('Local Docker only')
    path = os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    os.environ.clear()
    os.environ.update(PATH=path, HOME=str(BASE / '.cache/sdk-host-home'),
                      LITELLM_LOCAL_MODEL_COST_MAP='True')
    Path(os.environ['HOME']).mkdir(parents=True, exist_ok=True)

    def no_ip(event, args):
        if event == 'socket.connect' and args[0].family != socket.AF_UNIX:
            raise RuntimeError('Host IP connections forbidden')
    sys.addaudithook(no_ip)


def fixture_environment():
    fake = 'offline-fixture-not-a-secret'
    return {'HOME': '/home/agent', 'OPENAI_API_KEY': fake, 'ANTHROPIC_API_KEY': fake,
            'CODEX_API_KEY': fake, 'ANTHROPIC_BASE_URL': FIXTURE_ORIGIN,
            'OPENAI_API_BASE': FIXTURE_API, 'OPENAI_BASE_URL': FIXTURE_API,
            'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT': '1'}


async def prepare_container(environment, record):
    result = await environment.docker(
        'run', '-d', '--rm', '--pull=never', '--name', environment.name,
        '--network', 'none', '--user', '1000:1000', '--cap-drop', 'ALL',
        '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--security-opt', 'no-new-privileges', '--cpus', '1', '--memory', '2g',
        '--entrypoint', 'sleep', record['image_id'], 'infinity')
    require(result.return_code == 0, result.stderr)
    metadata = await environment.docker('inspect', environment.name, '--format',
                                         '{{json .Mounts}} {{json .HostConfig.NetworkMode}}')
    require(metadata.stdout.strip() == '[] "none"', 'Unexpected container mounts/network')
    result = await environment.exec('mkdir -p /control; chown 1000:1000 /control', user='root')
    require(result.return_code == 0, result.stderr)
    await environment.upload_file(NATIVE / 'task/environment/input.json', '/app/input.json')
    await environment.upload_file(NATIVE / 'mock-provider.mjs', '/control/mock-provider.mjs')
    result = await environment.exec('node /control/mock-provider.mjs > /logs/agent/mock-server.log 2>&1 &')
    require(result.return_code == 0, result.stderr)
    await asyncio.sleep(0.2)


async def cli_command(harness, model, launch, environment):
    options = {'model': model, 'provider': launch['provider'],
               'turns': None if harness == 'codex' else 8, 'budget': None,
               'prompt': launch['prompt']}
    js = ('import {buildCommand} from ' + json.dumps(str(ROOT / 'experiments' / harness / ADAPTER))
          + ';console.log(JSON.stringify(buildCommand(' + json.dumps(options) + ')));')
    built = await node_json(js)
    environment.extra_env.update(built['env'])
    command = built['command']
    if harness == 'codex':
        command = command[:-2] + ['-c', 'model_provider="fixture"', '-c',
            'model_providers.fixture={name="Offline fixture",base_url="' + FIXTURE_API
            + '",env_key="CODEX_API_KEY",wire_api="responses"}'] + command[-2:]
    if harness == 'claude-code':
        await environment.upload_file(ROOT / 'experiments/claude-code/settings.example.json', '/control/settings.json')
    if harness == 'opencode':
        await environment.upload_file(ROOT / 'experiments/opencode/opencode.json', '/control/opencode.json')
        config = json.loads(environment.extra_env['OPENCODE_CONFIG_CONTENT'])
        config['provider']['anthropic']['options'] = {'baseURL': FIXTURE_API}
        environment.extra_env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
    return command


async def build_command(harness, model, launch, environment, output):
    if harness == 'pi':
        for filename in ['run.mjs', ADAPTER]:
            await environment.upload_file(ROOT / 'experiments/pi' / filename, '/control/' + filename)
        shim = output / 'fetch-shim.mjs'
        shim.write_text("const nativeFetch=globalThis.fetch;globalThis.fetch=(url,options)=>nativeFetch('"
            + FIXTURE_ORIGIN + "'+new URL(typeof url==='string'?url:(url.url??url.href)).pathname,options);"
            + "await import('/control/run.mjs');\n")
        await environment.upload_file(shim, '/control/fetch-shim.mjs')
        return ['node', '/control/fetch-shim.mjs', json.dumps(launch)]
    if harness == 'mini-swe-agent':
        await environment.upload_file(ROOT / 'experiments/mini-swe-agent/run.py', '/control/run.py')
        return ['/home/agent/.local/share/uv/tools/mini-swe-agent/bin/python', '/control/run.py', json.dumps(launch)]
    return await cli_command(harness, model, launch, environment)


async def check_artifacts(environment):
    artifact = await environment.exec('cat /app/output/result.json; cat /app/output/model-tool.json')
    rows = artifact.stdout.splitlines()
    require(artifact.return_code == 0 and len(rows) == 2, 'Incomplete fixture artifacts')
    require(json.loads(rows[0]) == json.loads((NATIVE / 'task/tests/expected.json').read_text()), 'Wrong fixture artifact')
    require(json.loads(rows[1])['uid'] == 1000, 'Task tool did not run as UID1000')


def requests_for(output, provider, model):
    requests = [json.loads(line) for line in (output / 'agent/mock-requests.jsonl').read_text().splitlines()]
    require(len(requests) >= 2 and {row['model'] for row in requests} == {model}, 'Wrong or incomplete model requests')
    require(not (output / 'agent/mock-rejections.jsonl').exists(), 'Strict request validator rejected SDK call')
    if provider == 'openai':
        require({row['path'] for row in requests} == {'/v1/responses'}, 'Sol did not use Responses')
    return requests


async def parse_trace(harness, stdout):
    js = ('import fs from "node:fs";import {parseTrace} from '
          + json.dumps(str(ROOT / 'experiments' / harness / ADAPTER))
          + ';console.log(JSON.stringify(parseTrace(fs.readFileSync(0,"utf8"))));')
    trace = await node_json(js, stdout)
    require(trace['stopReason'] not in ['error', 'trace_incomplete', 'RepeatedFormatError'], 'Invalid native terminal event')
    return trace


async def cleanup(environment, output, record):
    try:
        await environment.download_dir('/logs/agent', output / 'agent')
    except Exception as error:
        record['log_collection_error'] = str(error)
    removed = await environment.docker('rm', '-f', environment.name)
    record['cleanup_confirmed'] = removed.return_code == 0 or 'No such container' in removed.stderr
    if not record['cleanup_confirmed']:
        record['status'] = 'failed'


async def run_case(harness, provider, model, lock, run, docker_host):
    output = run / (harness + '-' + provider)
    output.mkdir()
    environment = s.OfflineEnvironment('model-refresh-sdk-' + uuid.uuid4().hex,
                                       docker_host, fixture_environment())
    record = {'harness': harness, 'provider': provider, 'model': model, 'status': 'failed',
              'image_id': lock['images'][harness]['image_id'],
              'raw_directory': str(output.relative_to(BASE)), 'provider_requests': 0}
    try:
        await prepare_container(environment, record)
        launch = {'model': model if harness == 'pi' else provider + '/' + model,
                  'provider': provider, 'turns': 8, 'prompt': (NATIVE / 'task/instruction.md').read_text()}
        command = await build_command(harness, model, launch, environment, output)
        result = await environment.exec(shlex.join(command), timeout_sec=100)
        (output / 'stdout.jsonl').write_text(result.stdout)
        (output / 'stderr.txt').write_text(result.stderr)
        require(result.return_code == 0, result.stderr)
        await check_artifacts(environment)
        await environment.download_dir('/logs/agent', output / 'agent')
        requests = requests_for(output, provider, model)
        trace = await parse_trace(harness, result.stdout)
        (output / 'parsed.json').write_text(json.dumps(trace, indent=2) + '\n')
        record.update(status='passed', fixture_calls=len(requests),
            request_settings=[row['settings'] for row in requests], parsed=trace,
            synthetic_usage_not_billing=True,
            transport_deviation='Fixture-only Pi fetch redirection, mini/Claude API-base env, OpenCode baseURL and Codex custom provider; live route unverified')
    except Exception as error:
        record['error'] = str(error) or type(error).__name__
    finally:
        await cleanup(environment, output, record)
    record['raw_sha256'] = {str(path.relative_to(output)): sha(path) for path in output.rglob('*') if path.is_file()}
    print(json.dumps(record), flush=True)
    return record


def source_paths():
    return [Path(__file__), NATIVE / 'offline_smoke.py', NATIVE / 'mock-provider.mjs',
            NATIVE / 'task/instruction.md', NATIVE / 'task/environment/input.json',
            NATIVE / 'task/tests/expected.json',
            ROOT / 'experiments/pi/run.mjs', ROOT / 'experiments/pi/adapter.mjs',
            ROOT / 'experiments/mini-swe-agent/run.py', ROOT / 'experiments/mini-swe-agent/adapter.mjs',
            ROOT / 'experiments/claude-code/adapter.mjs', ROOT / 'experiments/claude-code/settings.example.json',
            ROOT / 'experiments/opencode/adapter.mjs', ROOT / 'experiments/opencode/opencode.json',
            ROOT / 'experiments/codex/adapter.mjs']


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker-host', required=True)
    args = parser.parse_args()
    isolate_host(args.docker_host)
    lock = json.loads((BASE / 'lab-runtime-lock.json').read_text())
    run = BASE / '.cache/sdk-smoke' / uuid.uuid4().hex
    run.mkdir(parents=True)
    results = []
    for harness, provider, model in CASES:
        results.append(await run_case(harness, provider, model, lock, run, args.docker_host))
    report = {'schema_version': 1, 'kind': 'lab-sdk-model-migration-offline-fixture',
              'provider_requests': 0, 'credentials_read': False,
              'runtime_lock_sha256': sha(NATIVE / 'runtime-lock.json'),
              'lab_runtime_lock_sha256': sha(BASE / 'lab-runtime-lock.json'),
              'sources_sha256': {str(path.relative_to(ROOT)): sha(path) for path in source_paths()},
              'cases': results}
    (BASE / 'sdk-smoke-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if all(row['status'] == 'passed' for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
