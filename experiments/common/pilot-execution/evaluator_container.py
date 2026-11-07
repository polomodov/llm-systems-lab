"""Independent operator's opaque-check execution; never supplies a task verdict.

Use only from a separate evaluator context. During implementation/tests, only
synthetic checker packages are used; real T002/T004 hidden checks are not read.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from common import BASE, ROOT, command, read, require, sha, write


def inventory(directory):
    result = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'Symlink evaluator inputs are forbidden')
        if path.is_file():
            result[str(path.relative_to(directory))] = sha(path)
    return result


async def evaluate(submission, checks, argv, output, image, timeout=120):
    require(not output.exists(), 'Never overwrite an evaluator receipt')
    require(isinstance(argv, list) and argv and all(isinstance(s, str) and s for s in argv), 'Use a literal argument array for the trusted checker')
    require(image.startswith('sha256:') and len(image) == 71, 'Evaluator toolchain must be an immutable local image ID')
    require(1 <= timeout <= 600, 'Evaluator timeout must be 1..600 seconds')
    manifest = read(submission / 'manifest.json')
    require(manifest.get('kind') == 'independent-evaluation-submission' and manifest.get('task') in ['T002-repo-janitor', 'T004-feature-from-spec'], 'Unsupported evaluator submission')
    require(manifest.get('method') == 'hidden-check', 'Evaluator requires the sealed hidden-check method')
    before = inventory(submission)
    require({name: value for name, value in before.items() if name != 'manifest.json'} == {row['path']: row['sha256'] for row in manifest['files']}, 'Submission differs from its sealed inventory')
    require(not output.resolve().is_relative_to(submission.resolve()) and not output.resolve().is_relative_to(checks.resolve()), 'Output must be separate from evaluator inputs')
    check_files = inventory(checks)
    require(check_files, 'Trusted evaluator checker package is empty')
    name = 'independent-evaluator-' + uuid.uuid4().hex
    output.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    failure = None
    stdout = stderr = ''
    exit_code = None
    try:
        await command('docker', 'run', '-d', '--rm', '--pull=never', '--name', name,
            '--network', 'none', '--read-only', '--user', '1000:1000', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--pids-limit', '256', '--cpus', '1', '--memory', '2g',
            '--tmpfs', '/work:rw,nosuid,uid=1000,gid=1000,mode=0700,size=1073741824',
            '--mount', f'type=bind,src={submission},dst=/work/submission,readonly',
            '--mount', f'type=bind,src={checks},dst=/work/check-package,readonly',
            '--env', 'HOME=/work/home', '--env', 'GIT_CONFIG_NOSYSTEM=1', '--env', 'GIT_CONFIG_GLOBAL=/dev/null',
            '--entrypoint', 'sleep', image, 'infinity')
        metadata = json.loads(await command('docker', 'inspect', name, '--format',
            '{"network":{{json .HostConfig.NetworkMode}},"mounts":{{json .Mounts}}}'))
        expected_mounts = {str(submission): '/work/submission', str(checks): '/work/check-package'}
        require(metadata['network'] == 'none' and len(metadata['mounts']) == 2 and
                all(not mount['RW'] and expected_mounts.get(mount['Source']) == mount['Destination'] for mount in metadata['mounts']),
                'Unexpected evaluator mounts or network')
        await command('docker', 'exec', name, 'sh', '-c',
                      'cp -R /work/submission/workspace /work/workspace; mkdir -p /work/home')
        process = await asyncio.create_subprocess_exec('docker', 'exec', '--workdir', '/work/workspace/sample', name, *argv,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            async with asyncio.timeout(timeout):
                out, err = await process.communicate()
            stdout, stderr, exit_code = out.decode(), err.decode(), process.returncode
        except asyncio.TimeoutError:
            failure = 'checker-timeout'
            await command('docker', 'rm', '-f', name)
            out, err = await process.communicate()
            stdout, stderr = out.decode(), err.decode()
        (output / 'stdout.txt').write_text(stdout)
        (output / 'stderr.txt').write_text(stderr)
    except Exception as error:
        failure = type(error).__name__
        (output / 'infrastructure-error.txt').write_text(str(error))
    finally:
        remaining = (await command('docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}')).strip()
        if remaining:
            await command('docker', 'rm', '-f', name)
    require(inventory(submission) == before and inventory(checks) == check_files, 'Evaluator source inputs changed')
    receipt = {'schema_version': 1, 'method': manifest['method'], 'submission_id': manifest['submission_id'],
       'submission_manifest_sha256': sha(submission / 'manifest.json'),
       'artifacts_sha256': manifest['artifacts_sha256'], 'workspace_sha256': manifest['workspace_sha256'],
       'checker_revision': manifest['checker_revision'],
       'check_package_sha256': hashlib.sha256(json.dumps(check_files, sort_keys=True).encode()).hexdigest(),
       'check_command': json.dumps(argv), 'check_environment': image,
       'checked_at': started, 'network': 'none', 'independent_context': True,
       'evaluator': '', 'result': None, 'check_output': '',
       'infrastructure_failure': failure, 'checker_exit_code': exit_code,
       'stdout_sha256': sha(output / 'stdout.txt') if (output / 'stdout.txt').exists() else None,
       'stderr_sha256': sha(output / 'stderr.txt') if (output / 'stderr.txt').exists() else None,
       'source_unchanged': True, 'provider_requests': 0,
       'instructions': 'Independent evaluator must interpret pinned checker semantics, identify themselves and fill result/check_output. Exit0 alone is not a pass. Infrastructure failure is not a task verdict.'}
    write(output / 'receipt-template.json', receipt)
    print(json.dumps({'receipt': str(output / 'receipt-template.json'), 'result': None, 'failure': failure}))
    return receipt


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission', type=Path, required=True)
    parser.add_argument('--checks', type=Path, required=True)
    parser.add_argument('--command-json', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--docker-host', required=True)
    args = parser.parse_args()
    require(args.docker_host.startswith('unix://'), 'Only local Docker is supported')
    # No .env or host authentication is loaded; the checker container gets no keys.
    path = os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    os.environ.clear()
    os.environ.update(PATH=path, DOCKER_HOST=args.docker_host, HOME=str(BASE / '.cache/evaluator-home'))
    image = read(BASE.with_name('model-refresh-2026-11') / 'lab-runtime-lock.json')['images']['codex']['image_id']
    await evaluate(args.submission.resolve(), args.checks.resolve(), json.loads(args.command_json), args.out.resolve(), image)


if __name__ == '__main__':
    asyncio.run(main())
