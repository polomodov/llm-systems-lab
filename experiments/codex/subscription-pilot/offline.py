"""Network-none native subscription-auth plumbing; invented tokens only.

There is deliberately no execute/login/live action. No host .env, HOME auth or
keychain is inspected. This script only runs the sealed public normalization
fixture inside disposable containers with an invented account and backend.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

from subscription_pilot import BASE, ROOT, admission, native_config, read, reconcile, require, sha, validate_record, write


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Evidence symlinks forbidden')
        if path.is_file(): result[str(path.relative_to(root))] = sha(path)
    return result


def run(docker_host):
    require(docker_host.startswith('unix://'), 'Only a local Docker Unix socket is allowed')
    plan = read(BASE / 'plan.json'); tag = uuid.uuid4().hex
    directory = BASE / '.cache' / ('offline-' + tag); directory.mkdir(parents=True)
    private = directory / 'host-home'; private.mkdir()
    env = {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'), 'HOME': str(private),
           'DOCKER_CONFIG': str(private), 'DOCKER_HOST': docker_host}
    def command(args, *, data=None, timeout=30, fail=True):
        result = subprocess.run(args, input=data, capture_output=True, env=env, timeout=timeout)
        if fail: require(result.returncode == 0, 'Offline command failed: ' + result.stderr.decode()[-3000:])
        return result.stdout
    def docker(*args, **kwargs): return command(['docker', *map(str, args)], **kwargs)
    def upload(container, name, data):
        # Only coordinator-selected fixed paths, never filenames supplied by the model.
        docker('exec', '-i', container, 'node', '-e',
               'const fs=require("fs");fs.writeFileSync(process.argv[1],fs.readFileSync(0));', '/app/' + name, data=data)
    condition = plan['condition']; agent = 'subscription-offline-' + tag; verifier = agent + '-verifier'
    record = {'kind': 'subscription-pilot-run-v1', 'run_id': datetime.now(timezone.utc).strftime('%Y-%m-%d') + '-subscription-fixture-' + tag[:10],
        'funding': 'chatgpt_subscription', 'synthetic': True, 'execution_authorized': False, 'status': 'prepared',
        'started_at': None, 'verdict': None, 'observed_model': None, 'cost_usd': None,
        'exact_run_quota_consumption': None, 'live_qualification': 'unverified', 'condition': condition,
        'measurements': {key: None for key in ['turns', 'tokens_in', 'tokens_out', 'permissions_asked', 'compactions', 'subagents', 'wall_clock_s']},
        'inputs_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [BASE / 'contract.md', BASE / 'instruction.md', ROOT / 'experiments/common/harbor-interop/task/environment/input.json', ROOT / 'experiments/common/harbor-interop/task/tests/evaluate.py']},
        'plan_sha256': sha(BASE / 'plan.json'), 'source_sha256': {p.name: sha(p) for p in BASE.iterdir() if p.suffix in ['.py', '.mjs']},
        'notes': 'Synthetic infrastructure control only. No subscription allowance or API billing consumed.'}
    validate_record(record); write(directory / 'prepared-record.json', record)
    created = []
    try:
        for name, image in [(agent, condition['image_id']), (verifier, condition['verifier_image_id'])]:
            args = ['run', '-d', '--pull=never', '--name', name, '--network', 'none', '--read-only', '--user', '1000:1000',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256', '--memory', '2g', '--cpus', '1',
                '--tmpfs', '/app:rw,nosuid,uid=1000,gid=1000,mode=0700,size=268435456',
                '--tmpfs', '/tmp:rw,nosuid,size=268435456',
                '--tmpfs', '/run/subscription-home:rw,nosuid,uid=1000,gid=1000,mode=0700,size=268435456',
                '--tmpfs', '/logs/verifier:rw,nosuid,uid=1000,gid=1000,mode=0700,size=16777216',
                '--env', 'HOME=/run/subscription-home', '--env', 'CODEX_HOME=/run/subscription-home/.codex',
                '--env', 'RUST_LOG=error,codex_core::session=info,codex_api::sse::responses=trace',
                '--env', 'NO_COLOR=1', '--env', 'CODEX_CA_CERTIFICATE=/app/fixture-cert.pem', '--entrypoint', 'sleep', image, 'infinity']
            docker(*args); created.append(name)
            metadata = json.loads(docker('inspect', name))[0]
            require(metadata['Image'] == image and metadata['Config']['User'] == '1000:1000' and
                    metadata['HostConfig']['NetworkMode'] == 'none' and metadata['HostConfig']['ReadonlyRootfs'] and
                    not metadata['Mounts'], 'Unexpected image, user, network, root or host mounts')
            write(directory / (('agent' if name == agent else 'verifier') + '-runtime.json'),
                  {'image': image, 'network': 'none', 'read_only_root': True, 'host_mounts': [], 'uid': 1000})
        version = docker('exec', agent, 'codex', '--version').decode().strip()
        require(version == 'codex-cli 0.167.0', 'Native version mismatch')
        source = ROOT / 'experiments/common/harbor-interop/task'
        public = source / 'environment/input.json'
        command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                 '-addext', 'subjectAltName=IP:127.0.0.1', '-keyout', str(private / 'fixture-key.pem'), '-out', str(directory / 'fixture-cert.pem')])
        upload(agent, 'fixture-key.pem', (private / 'fixture-key.pem').read_bytes())
        (private / 'fixture-key.pem').unlink()
        upload(agent, 'fixture-cert.pem', (directory / 'fixture-cert.pem').read_bytes())
        upload(agent, 'input.json', public.read_bytes())
        upload(agent, 'instruction.md', (BASE / 'instruction.md').read_bytes())
        upload(agent, 'config.toml', native_config(offline=True).encode())
        upload(agent, 'offline_agent.mjs', (BASE / 'offline_agent.mjs').read_bytes())
        upload(agent, 'provider-base.mjs', (ROOT / 'experiments/common/harbor-native-2026-11/mock-provider.mjs').read_bytes())
        record.update(status='running', started_at=datetime.now(timezone.utc).isoformat())
        write(directory / 'start-record.json', record)
        output = docker('exec', '--workdir', '/app', agent, 'node', '/app/offline_agent.mjs', timeout=260)
        (directory / 'driver-stdout.txt').write_bytes(output)
        evidence = directory / 'raw'; evidence.mkdir()
        archive = docker('exec', agent, 'tar', '-C', '/app/evidence', '-cf', '-', '.')
        require(len(archive) <= 32 * 1024 * 1024, 'Offline evidence archive exceeds bound')
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            for member in stream.getmembers():
                relative = Path(member.name)
                require(not relative.is_absolute() and '..' not in relative.parts and
                        (member.isdir() or member.isfile()) and not member.islnk() and not member.issym(), 'Unsafe evidence archive entry')
                target = evidence / relative
                if member.isdir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as output: output.write(stream.extractfile(member).read())
        require(not any(p.name in ['auth.json', 'config.toml'] for p in evidence.rglob('*')), 'Private credential/config file exported')
        before, after = read(evidence / 'quota-before.json'), read(evidence / 'quota-after.json')
        gate = admission(before, now=before['observed_at'], account_scope='offline-subscription-fixture', account_id='subscription-fixture-account', allow_synthetic=True)
        require(gate['quota_ready'] and not gate['execution_authorized'], 'Native quota plumbing failed admission')
        write(directory / 'quota-admission.json', gate)
        write(directory / 'quota-reconciliation.json', reconcile(before, after))
        # The public input remains byte-identical; select only a regular bounded artifact.
        artifact = docker('exec', agent, 'node', '-e',
            'const fs=require("fs"),crypto=require("crypto");if(crypto.createHash("sha256").update(fs.readFileSync("/app/input.json")).digest("hex")!==process.argv[1])throw Error("input changed");const fd=fs.openSync("/app/output/result.json",fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);const s=fs.fstatSync(fd);if(!s.isFile()||s.size>1024)throw Error("invalid artifact");process.stdout.write(fs.readFileSync(fd));', sha(public))
        (directory / 'artifact.json').write_bytes(artifact)
        docker('exec', verifier, 'mkdir', '-p', '/app/output')
        # Verifier gets only the selected artifact and the frozen public oracle, no agent home/session/config.
        command(['docker', 'exec', '-i', verifier, 'python3', '-c', 'import pathlib,sys;pathlib.Path("/app/output/result.json").write_bytes(sys.stdin.buffer.read())'], data=artifact)
        command(['docker', 'exec', '-i', verifier, 'python3', '-c', 'import pathlib,sys;pathlib.Path("/app/evaluate.py").write_bytes(sys.stdin.buffer.read())'], data=(source / 'tests/evaluate.py').read_bytes())
        verdict = json.loads(docker('exec', verifier, 'python3', '/app/evaluate.py', timeout=60))
        write(directory / 'verifier.json', verdict)
        require(verdict['reward'] == 1 and verdict['effective_uid'] == 1000 and verdict['external_https_probe_blocked'] and
                not verdict['agent_input_present_in_verifier'], 'Independent verifier failed')
        sys.path.insert(0, str(ROOT / 'experiments/common/pilot-execution'))
        from hn_o01 import extract
        measured = extract(evidence, condition['model'])
        write(directory / 'synthetic-measurements.json', measured)
        require(measured['identity_coverage_complete'] and measured['values']['tool_operations'] > 0, 'Native response/tool trace incomplete')
        record.update(status='completed', verdict='pass', quota_status='synthetic_only', metrics_unavailable=['permissions.asked', 'cost_usd', 'exact_run_quota_consumption'])
    except BaseException as error:
        record.update(status='aborted', verdict='aborted', failure=type(error).__name__)
        raise
    finally:
        for name in reversed(created): docker('rm', '-f', name, fail=False)
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        record['cleanup_complete'] = all(not docker('ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}').strip() for name in created)
        validate_record(record); write(directory / 'run.json', record)
    require(record['cleanup_complete'], 'Owned container cleanup failed')
    files = inventory(directory)
    write(directory / 'summary.json', {'kind': 'offline-subscription-pilot-evidence', 'synthetic': True, 'paid_runs': 0,
          'provider_requests': 0, 'real_credentials_read': False, 'real_subscription_allowance_consumed': False,
          'record': 'run.json', 'files': files, 'source_sha256': record['source_sha256']})
    print(json.dumps({'summary': str(directory / 'summary.json'), 'task_verdict': record['verdict'], 'live_qualification': 'unverified'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'offline'])
    parser.add_argument('--docker-host', default='unix:///Users/apolomodov/.colima/default/docker.sock')
    args = parser.parse_args()
    if args.action == 'plan': print(json.dumps(read(BASE / 'plan.json')))
    else: run(args.docker_host)
