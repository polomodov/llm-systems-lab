"""Verify retained preregistration history and exact source blobs; no hardware claim."""
import datetime
import hashlib
import re
import subprocess

def stamp(value):
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))

def verify_preregistration(root, commit, files, execution_started_at, head='HEAD'):
    result = dict(commit=commit, head=head, execution_started_at=execution_started_at,
                  verified=False, files=[], errors=[], scope='Retained Git ancestry, committed bytes and recorded timestamps; Git timestamps are author-controlled, not an independent clock attestation.')
    try:
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('A full preregistration commit SHA is required')
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)
        git('merge-base', '--is-ancestor', commit, head)
        result['reviewed_head'] = git('rev-parse', head).decode().strip()
        committed_at = git('show', '-s', '--format=%cI', commit).decode().strip()
        result['committed_at'] = committed_at
        if stamp(committed_at) > stamp(execution_started_at):
            raise ValueError('Preregistration commit is later than execution')
        for relative, expected in files.items():
            if relative.startswith('/') or '..' in relative.split('/') or ':' in relative:
                raise ValueError('Invalid receipt path')
            data = git('show', commit + ':' + relative)
            actual = hashlib.sha256(data).hexdigest()
            matches = actual == expected
            result['files'].append(dict(path=relative, sha256=actual, expected_sha256=expected, matches=matches))
            if not matches:
                result['errors'].append('Committed bytes differ: ' + relative)
        if not files:
            result['errors'].append('Receipt has no files')
        result['verified'] = not result['errors']
    except (ValueError, subprocess.CalledProcessError) as error:
        result['errors'].append(str(error))
    return result
