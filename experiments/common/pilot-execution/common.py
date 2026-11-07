"""Small local evidence helpers; no provider clients or credential discovery."""
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import stat
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
NATIVE = BASE.with_name('harbor-native-2026-11')
INTEROP = BASE.with_name('harbor-interop')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


async def command(*args, timeout=30):
    process = await asyncio.create_subprocess_exec(
        *map(str, args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        async with asyncio.timeout(timeout):
            stdout, stderr = await process.communicate()
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode() or 'Local command failed')
    return stdout.decode()


# Operator inputs are flat names within a dedicated private staging directory.
# Neither CLI arguments nor document contents may select arbitrary host paths.
OPERATOR_ROOT = BASE / '.cache/operator'


def operator_file(name):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', str(name)) is not None,
            'Operator input must be a plain filename under .cache/operator')
    root = OPERATOR_ROOT.resolve(strict=True)
    require(not OPERATOR_ROOT.is_symlink(), 'Operator directory must not be a symlink')
    path = (root / name).resolve(strict=True)
    require(path.parent == root and not (root / name).is_symlink(), 'Operator input escapes its directory')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(str(name), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                'Operator input must be a regular file without hard links')
        require(info.st_uid == os.getuid() and not info.st_mode & 0o022,
                'Operator input must be operator-owned and not group/world writable')
        data = stream.read(2_000_001)
        require(len(data) <= 2_000_000, 'Operator input exceeds 2 MB')
    return path, data


def operator_document(name):
    path, data = operator_file(name)
    return path, json.loads(data)
