"""Exercise the separate evaluator container with invented checks, never hidden checks."""
import asyncio
import json
from pathlib import Path
import os
import sys
import uuid

from common import BASE, read, require, sha, write
from evaluator_container import evaluate, inventory


async def main():
    require(len(sys.argv) == 2 and sys.argv[1].startswith('unix://'), 'Pass the local Docker Unix socket')
    path = os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    host = sys.argv[1]
    os.environ.clear()
    os.environ.update(PATH=path, DOCKER_HOST=host, HOME=str(BASE / '.cache/evaluator-smoke-home'))
    directory = BASE / '.cache' / ('evaluator-' + uuid.uuid4().hex)
    directory.mkdir()
    image = read(BASE.with_name('model-refresh-2026-11') / 'lab-runtime-lock.json')['images']['codex']['image_id']
    cases = []
    for task, expected_exit in [('T002-repo-janitor', 0), ('T004-feature-from-spec', 1)]:
        target = directory / task
        submission, checks = target / 'submission', target / 'invented-checks'
        (submission / 'workspace/sample').mkdir(parents=True)
        (submission / 'artifacts').mkdir()
        (submission / 'workspace/sample/input.txt').write_text('synthetic input\n')
        (submission / 'artifacts/report.md').write_text('Synthetic plumbing only, not task performance.\n')
        checks.mkdir()
        (checks / 'check.mjs').write_text('import fs from "node:fs";if(fs.readFileSync("/work/workspace/sample/input.txt","utf8")!=="synthetic input\\n")throw new Error("copy failed");console.log("Invented checker only");process.exit(' + str(expected_exit) + ');\n')
        manifest = {'kind': 'independent-evaluation-submission', 'submission_id': str(uuid.uuid4()),
            'task': task, 'checker_revision': 'a' * 40, 'artifacts_sha256': 'b' * 64, 'workspace_sha256': 'c' * 64,
            'files': [{'path': name, 'sha256': value} for name, value in inventory(submission).items()]}
        write(submission / 'manifest.json', manifest)
        receipt = await evaluate(submission, checks, ['node', '/work/check-package/check.mjs'], target / 'assessment', image)
        require(receipt['checker_exit_code'] == expected_exit and receipt['infrastructure_failure'] is None,
                'Evaluator container plumbing failed')
        require(receipt['result'] is None and receipt['source_unchanged'], 'Evaluator wrapper must not manufacture a verdict')
        cases.append({'task_label': task, 'synthetic_only': True, 'exit_code': expected_exit,
                      'automatic_verdict': None, 'receipt': str((target / 'assessment/receipt-template.json').relative_to(BASE)),
                      'receipt_sha256': sha(target / 'assessment/receipt-template.json')})
    write(directory / 'summary.json', {'kind': 'offline-evaluator-container-smoke', 'provider_requests': 0,
        'paid_runs': 0, 'actual_hidden_checks_read': False, 'cases': cases,
        'source_sha256': {str(p.relative_to(BASE)): sha(p) for p in [Path(__file__), BASE / 'evaluator_container.py', BASE / 'common.py']}})
    print(json.dumps({'summary': str(directory / 'summary.json'), 'cases': len(cases), 'actual_hidden_checks_read': False}))


if __name__ == '__main__':
    asyncio.run(main())
