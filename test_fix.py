import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile
import fix


class FixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'Steam'
        self.shared = self.root / 'shared'
        self.backup = self.root / 'backup'
        self.target.mkdir()
        self.shared.mkdir()
        self.payload = {name: b'MZ replacement SteamUtils011 ' + name.encode() for name in fix.NAMES}
        for name in fix.NAMES:
            (self.shared / name).write_bytes(b'MZ original SteamUtils010')
            (self.target / name).symlink_to(self.shared / name)

    def test_apply_restore_reapply_preserves_shared_files(self):
        before = fix.snapshot(self.target)
        fix.apply(self.target, self.backup, self.payload)
        for name in fix.NAMES:
            self.assertFalse((self.target / name).is_symlink())
            self.assertEqual((self.target / name).read_bytes(), self.payload[name])
            self.assertEqual((self.shared / name).read_bytes(), b'MZ original SteamUtils010')
        fix.recover(self.target, self.backup, 'restore')
        self.assertEqual(fix.snapshot(self.target), before)
        fix.recover(self.target, self.backup, 'reapply')
        self.assertEqual((self.target / fix.NAMES[0]).read_bytes(), self.payload[fix.NAMES[0]])

    def test_regular_files_restore(self):
        for name in fix.NAMES:
            (self.target / name).unlink()
            (self.target / name).write_bytes(b'original')
        before = fix.snapshot(self.target)
        fix.apply(self.target, self.backup, self.payload)
        fix.recover(self.target, self.backup, 'restore')
        self.assertEqual(fix.snapshot(self.target), before)

    def test_newer_file_is_not_overwritten(self):
        fix.apply(self.target, self.backup, self.payload)
        (self.target / fix.NAMES[1]).write_bytes(b'newer vendor update')
        before = fix.snapshot(self.target)
        for action in ('restore', 'reapply'):
            with self.assertRaises(ValueError):
                fix.recover(self.target, self.backup, action)
            self.assertEqual(fix.snapshot(self.target), before)

    def test_corrupt_backup_rejected_before_any_write(self):
        fix.apply(self.target, self.backup, self.payload)
        (self.backup / (fix.NAMES[2] + '.original')).write_bytes(b'corrupt')
        before = fix.snapshot(self.target)
        with self.assertRaises(ValueError):
            fix.recover(self.target, self.backup, 'restore')
        self.assertEqual(fix.snapshot(self.target), before)

    def test_partial_failure_rolls_back(self):
        before = fix.snapshot(self.target)
        actual = fix.replace
        calls = []
        def fail_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError('simulated disk failure')
            return actual(*args, **kwargs)
        with patch.object(fix, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                fix.apply(self.target, self.backup, self.payload)
        self.assertEqual(fix.snapshot(self.target), before)

    def test_changed_shared_component_blocks_restore(self):
        fix.apply(self.target, self.backup, self.payload)
        (self.shared / fix.NAMES[0]).write_bytes(b'vendor updated shared DLL')
        with self.assertRaises(ValueError):
            fix.recover(self.target, self.backup, 'restore')

    def test_extracts_only_named_dll_bytes(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            for name, content in self.payload.items():
                archive.writestr('bin/' + name, content)
            archive.writestr('../../unwanted', 'ignored')
        self.assertEqual(fix.unpack(data.getvalue()), self.payload)
        self.assertFalse((self.root / 'unwanted').exists())

    def test_download_integrity_failure(self):
        def bad_download(command, **kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(b'bad download')
        with patch.object(fix.subprocess, 'run', side_effect=bad_download):
            with self.assertRaises(ValueError):
                fix.download()

    def test_custom_container_roots_have_distinct_backups(self):
        roots = [self.root / 'disk one' / 'virtual_containers', self.root / 'disk two' / 'virtual_containers']
        backups = []
        for root in roots:
            target = root / '2' / fix.STEAM
            target.mkdir(parents=True)
            for name in fix.NAMES:
                (target / name).write_bytes(b'MZ original')
            actual, backup = fix.locations(root, '2')
            self.assertEqual(actual, target.resolve())
            backups.append(backup)
        self.assertNotEqual(*backups)

    def test_container_traversal_and_missing_files_rejected(self):
        for identifier in ('../2', '/2', '2'):
            with self.assertRaises(ValueError):
                fix.locations(self.root, identifier)

    def test_symlinked_steam_directory_rejected(self):
        root = self.root / 'virtual_containers'
        target = root / '2' / fix.STEAM
        target.parent.mkdir(parents=True)
        target.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(ValueError):
            fix.locations(root, '2')


if __name__ == '__main__':
    unittest.main()
