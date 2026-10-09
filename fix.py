#!/usr/bin/env python3
"""Reversible, per-container SteamUtils011 workaround for GameHub on macOS."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import zipfile

NAMES = ('steamclient64.dll', 'tier0_s64.dll', 'vstdlib_s64.dll')
URL = 'https://client-update.akamai.steamstatic.com/bins_win64.zip.36f5d9202e79ab2aa3e3c5902e84bbd799d31fc0'
SHA256 = '93f5b6bea0267fd85dc8cc823fdab5c5fb55d7f3a1deab0598acefef0e133bce'
SIZE = 63700191
BASE = Path.home() / 'Library/Application Support/com.gamemac.www/wine-engine/containers/virtual_containers'
STEAM = Path('drive_c/Program Files (x86)/Steam')
BACKUPS = Path.home() / 'Library/Application Support/gamehub-steamutils011-fix'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download():
    print('Downloading the tested package directly from Valve (about 64 MB)...')
    # macOS curl uses the system certificate setup; some Python distributions
    # ship without a configured CA bundle. TLS verification stays enabled.
    with tempfile.TemporaryDirectory(prefix='gamehub-steam-download-') as directory:
        package = Path(directory) / 'package.zip'
        subprocess.run(['/usr/bin/curl', '--fail', '--location', '--silent', '--show-error',
                        '--proto', '=https', '--proto-redir', '=https',
                        '--connect-timeout', '30', '--max-time', '300',
                        '--max-filesize', str(SIZE), '--output', str(package), URL], check=True)
        data = package.read_bytes()
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Valve package checksum/size mismatch; no game files changed.')
    return unpack(data)


def unpack(data):
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in NAMES:
            matches = [info for info in archive.infolist()
                       if info.filename.replace('\\', '/').split('/')[-1] == name]
            if len(matches) != 1 or matches[0].file_size > 150_000_000:
                raise ValueError('Unexpected archive layout: ' + name)
            result[name] = archive.read(matches[0])
            if not result[name].startswith(b'MZ'):
                raise ValueError('Not a Windows DLL: ' + name)
    if b'SteamUtils011' not in result[NAMES[0]]:
        raise ValueError('Package does not contain SteamUtils011.')
    return result


def replace(path, data=None, link=None):
    """Replace the directory entry, never write through a shared DLL symlink."""
    fd, tmp = tempfile.mkstemp(prefix='.steamutils-fix-', dir=path.parent)
    os.close(fd)
    try:
        if link is not None:
            os.unlink(tmp)
            os.symlink(link, tmp)
        else:
            Path(tmp).write_bytes(data)
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def snapshot(target):
    return {name: {'sha256': digest(target / name),
                   'link': os.readlink(target / name) if (target / name).is_symlink() else None}
            for name in NAMES}


def original(target, backup, name, record):
    link = record['link']
    if link is not None:
        source = Path(link) if Path(link).is_absolute() else target / link
        if not source.is_file() or digest(source) != record['sha256']:
            raise ValueError('Original shared component changed; refusing stale link: ' + name)
    if digest(backup / (name + '.original')) != record['sha256']:
        raise ValueError('Backup checksum mismatch: ' + name)


def apply(target, backup, payload):
    before = snapshot(target)
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    records = {}
    for name in NAMES:
        shutil.copyfile(target / name, backup / (name + '.original'))
        (backup / (name + '.replacement')).write_bytes(payload[name])
        records[name] = dict(before[name], replacement=hashlib.sha256(payload[name]).hexdigest())
    # Persist recovery information before changing any game files.
    (backup / 'manifest.json').write_text(json.dumps({'target': str(target), 'files': records}, indent=2))
    if snapshot(target) != before:
        raise ValueError('GameHub files changed during backup; no replacement made.')
    changed = []
    try:
        for name in NAMES:
            replace(target / name, data=payload[name])
            changed.append(name)
    except BaseException:
        for name in reversed(changed):
            record = records[name]
            replace(target / name, data=(backup / (name + '.original')).read_bytes(), link=record['link'])
        raise


def recover(target, backup, action):
    manifest = json.loads((backup / 'manifest.json').read_text())
    if manifest['target'] != str(target) or set(manifest['files']) != set(NAMES):
        raise ValueError('Backup does not match this Steam directory.')
    records = manifest['files']
    before = snapshot(target)
    for name, record in records.items():
        if before[name]['sha256'] not in (record['sha256'], record['replacement']):
            raise ValueError('Unrecognized/newer DLL; refusing to overwrite: ' + name)
        if action == 'restore':
            original(target, backup, name, record)
        elif digest(backup / (name + '.replacement')) != record['replacement']:
            raise ValueError('Replacement backup checksum mismatch: ' + name)
    saved = {name: (target / name).read_bytes() for name in NAMES}
    changed = []
    try:
        for name, record in records.items():
            suffix = '.original' if action == 'restore' else '.replacement'
            replace(target / name, data=(backup / (name + suffix)).read_bytes(),
                    link=record['link'] if action == 'restore' else None)
            changed.append(name)
    except BaseException:
        for name in reversed(changed):
            replace(target / name, data=saved[name], link=before[name]['link'])
        raise


def ensure_closed():
    processes = subprocess.check_output(['ps', '-axo', 'comm='], text=True).lower().splitlines()
    if any(any(word in line for word in ('wineserver', 'wine64', 'wine-preloader', 'gamehub'))
           for line in processes):
        raise ValueError('Quit GameHub and all Wine games/processes before changing DLLs.')


def locations(root, container):
    root = root.expanduser().resolve()
    if not container.isdecimal():
        raise ValueError('Container ID must contain only decimal digits.')
    target = root / container / STEAM
    if target.resolve() != target or not all((target / n).is_file() for n in NAMES):
        raise ValueError('Expected a real GameHub Steam directory containing all three DLLs: ' + str(target))
    namespace = BACKUPS if root == BASE.resolve() else BACKUPS / ('root-' + hashlib.sha256(str(root).encode()).hexdigest()[:16])
    return target, namespace / container


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='status', choices=['status', 'apply', 'restore', 'reapply'])
    parser.add_argument('--container', help='Numeric GameHub virtual container ID (listed by status)')
    parser.add_argument('--containers-root', type=Path, default=BASE,
                        help='Relocated virtual_containers directory; defaults to GameHub in your home folder')
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('This workaround supports GameHub for macOS only.')
    root = args.containers_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Container root not found: ' + str(root) + '. Open the game C drive in GameHub to locate it.')
    if args.container is None:
        if args.action != 'status':
            parser.error('Select one container explicitly with --container ID.')
        count = 0
        for directory in sorted(root.glob('*')):
            client = directory / STEAM / NAMES[0]
            if directory.name.isdecimal() and client.is_file():
                state = 'present' if b'SteamUtils011' in client.read_bytes() else 'MISSING'
                print(f'Container {directory.name}: SteamUtils011 {state}')
                count += 1
        if not count:
            print('No initialized Steam containers found. Open the game C drive in GameHub to locate its container.')
        print('Use --container ID for details. No files changed.')
        return
    target, backup = locations(root, args.container)
    if args.action == 'status':
        print('Steam directory:', target)
        for name, record in snapshot(target).items():
            print(name, record['sha256'], '(symlink)' if record['link'] else '(private file)')
        print('SteamUtils011:', 'present' if b'SteamUtils011' in (target / NAMES[0]).read_bytes() else 'MISSING')
        print('Tool backup:', backup if backup.exists() else 'none')
        return
    ensure_closed()
    if args.action == 'apply':
        if b'SteamUtils011' in (target / NAMES[0]).read_bytes():
            print('SteamUtils011 is already present. No changes needed.')
            return
        if backup.exists():
            raise ValueError('Backup already exists; use status, restore or reapply.')
        payload = download()
        ensure_closed()
        apply(target, backup, payload)
    else:
        recover(target, backup, args.action)
    print('Completed:', args.action, '\nBackup:', backup)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise SystemExit('Stopped: ' + str(error))
