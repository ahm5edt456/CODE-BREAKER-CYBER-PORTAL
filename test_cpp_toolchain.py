"""Linker selection regressions; no submitted code or host compilation is run."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import runner
import execution_isolation as isolation


class CppToolchainTests(unittest.TestCase):
    def test_build_uses_bfd_without_adding_host_search_paths(self):
        command = runner.cpp_build_command('/usr/bin/g++')
        self.assertIn('-fuse-ld=bfd', command)
        self.assertEqual(command[2:], ['/work/main.cpp','-o','/work/app'])
        self.assertFalse(any('/etc' in argument or '/home' in argument for argument in command))
        self.assertFalse(any(argument.startswith('-B') for argument in command))
        self.assertEqual(isolation.JOB_ENVIRONMENT['PATH'], '/usr/bin:/bin')

    def test_selected_linker_is_in_the_existing_read_only_mount(self):
        resolved = Path('/usr/bin/ld.bfd').resolve(strict=True)
        self.assertIn(Path('/usr/bin'), resolved.parents)
        self.assertTrue(os.access(resolved, os.X_OK))
        with tempfile.TemporaryDirectory() as directory, isolation._seccomp_file(True) as policy:
            args = isolation.sandbox_command(directory, ['/usr/bin/g++'], policy.fileno(), True)
        mounts = [(args[i+1],args[i+2]) for i,arg in enumerate(args) if arg in ('--bind','--ro-bind')]
        self.assertIn(('/usr','/usr'), mounts)
        for source,destination in mounts:
            self.assertNotIn(source, ('/','/home','/etc','/etc/alternatives'))
            self.assertNotEqual(destination, '/etc/alternatives')
        self.assertNotIn('--bind', args)

    def test_linker_missing_fails_with_actionable_error(self):
        with patch.object(Path, 'resolve', side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, 'Fedora binutils'):
                runner.cpp_build_command('/usr/bin/g++')

    def test_linker_cannot_resolve_to_home_directory(self):
        with patch.object(Path, 'resolve', return_value=Path('/home/example/private-linker')):
            with self.assertRaisesRegex(RuntimeError, 'within /usr/bin'):
                runner.cpp_build_command('/usr/bin/g++')

    def test_linker_must_be_executable(self):
        with patch.object(runner.os, 'access', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'executable'):
                runner.cpp_build_command('/usr/bin/g++')

    def test_gcc_recognizes_bfd_selection_without_compiling_or_linking(self):
        # -### prints the planned tool invocations without running any of them.
        command = runner.cpp_build_command('/usr/bin/g++')
        command = [command[0], '-###', '-fuse-ld=bfd', '-x', 'c++', '/dev/null', '-o', '/dev/null']
        result = subprocess.run(command, env=dict(isolation.JOB_ENVIRONMENT),
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, 'GCC rejected the linker selection')
        self.assertIn('-fuse-ld=bfd', result.stderr)
        self.assertIn('collect2', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
