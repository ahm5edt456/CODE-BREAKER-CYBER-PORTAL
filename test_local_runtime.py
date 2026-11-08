"""Local setup policy tests; mocked cgroups never replace kernel integration tests."""
import contextlib
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import local_runtime as local


class LocalRuntimeTests(unittest.TestCase):
    def test_scope_is_transient_user_only_and_retains_limits(self):
        args = local.scope_command('verify')
        for flag in ('--user', '--scope', '--collect', '--property=Delegate=cpu memory pids',
                     '--property=MemoryMax=1G', '--property=MemorySwapMax=0', '--property=TasksMax=128'):
            self.assertIn(flag, args)
        for forbidden in ('--system', '--machine', 'sudo'):
            self.assertNotIn(forbidden, args)
        self.assertIn('_session', args)
        self.assertEqual(args[-1], 'verify')
        self.assertNotEqual(local.scope_command('play'), local.scope_command('play'))

    def test_restricted_environment_cannot_launch_host_service(self):
        with patch.object(local, 'diagnose', return_value={'local_session_ready': False}), \
             patch.object(local.os, 'execvp') as execute, \
             patch.object(local, 'setup_report') as report, \
             patch('sys.argv', ['local_runtime.py', 'verify']):
            self.assertEqual(local.main(), 2)
            execute.assert_not_called()
            self.assertEqual(report.call_args.args[0], 'blocked')

    def test_current_cgroup_cannot_be_root_or_outside_hierarchy(self):
        for path in ('/', '/../../tmp/outside'):
            with self.subTest(path=path), patch.object(local, '_read', return_value='0::'+path):
                with self.assertRaises(RuntimeError):
                    local.current_cgroup()

    def make_group(self, directory, name='code-breaker-'+'a'*32+'.scope'):
        group = Path(directory)/name
        group.mkdir()
        (group/'cgroup.procs').write_text(str(os.getpid()))
        (group/'cgroup.controllers').write_text('cpu memory pids')
        (group/'cgroup.subtree_control').write_text('')
        return group

    @contextlib.contextmanager
    def manager(self, group, overrides=None, ok=True, suffix=''):
        values = {'Id': group.name, 'ControlGroup': '/'+group.name, 'Delegate': 'yes',
                  'DelegateControllers': 'cpu memory pids', 'Transient': 'yes',
                  'ActiveState': 'active', 'MemoryMax': str(1024**3),
                  'MemorySwapMax': '0', 'TasksMax': '128'}
        values.update(overrides or {})
        response = '\n'.join(key+'='+value for key,value in values.items()) + suffix
        # Reproduce the user's ENODATA. Successful authentication must instead
        # come from matching manager properties, never from ignoring a denial.
        with patch.object(local, 'CGROUP', group.parent), \
             patch.object(local.os, 'getxattr', side_effect=OSError(errno.ENODATA, 'No data available')) as xattr, \
             patch.object(local, '_capture', return_value={'ok':ok,'detail':response}) as capture:
            yield capture
            xattr.assert_not_called()

    def test_missing_xattr_with_authoritative_delegation(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            with self.manager(group) as query:
                local.authenticate_delegation(group)
            args = query.call_args.args[0]
            self.assertEqual(args[:3], ['systemctl','--user','show'])
            self.assertEqual(args[-1], group.name)

    def test_denied_or_mismatched_manager_properties_never_modify_scope(self):
        cases = [{'Delegate':'no'}, {'Transient':'no'}, {'ActiveState':'inactive'},
                 {'Id':'other.scope'}, {'ControlGroup':'/other.scope'},
                 {'ControlGroup':'/../other.scope'}, {'DelegateControllers':'memory pids'},
                 {'MemoryMax':'infinity'}, {'MemoryMax':str(2*1024**3)}, {'TasksMax':'4096'},
                 {'TasksMax':'0'}, {'MemorySwapMax':'1'}]
        for values in cases:
            with self.subTest(properties=values), tempfile.TemporaryDirectory() as folder:
                group = self.make_group(folder)
                with self.manager(group, values), patch.object(local, 'current_cgroup', return_value=group):
                    with self.assertRaises(RuntimeError):
                        local.prepare_delegation()
                self.assertFalse((group/'supervisor').exists())
                self.assertEqual((group/'cgroup.subtree_control').read_text(), '')

    def test_manager_failure_is_not_bypassed(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            with self.manager(group, ok=False):
                with self.assertRaisesRegex(RuntimeError, 'Cannot authenticate'):
                    local.authenticate_delegation(group)
            self.assertFalse((group/'supervisor').exists())

    def test_duplicate_properties_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            with self.manager(group, suffix='\nDelegate=yes'):
                with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
                    local.authenticate_delegation(group)

    def test_unrelated_scope_not_modified_or_queried(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder, 'some-other-app.scope')
            with patch.object(local, 'current_cgroup', return_value=group), patch.object(local, '_capture') as query:
                with self.assertRaisesRegex(RuntimeError, 'unrelated'):
                    local.prepare_delegation()
                query.assert_not_called()
            self.assertFalse((group/'supervisor').exists())

    def test_missing_kernel_controller_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            (group/'cgroup.controllers').write_text('memory pids')
            with self.manager(group), patch.object(local, 'current_cgroup', return_value=group):
                with self.assertRaisesRegex(RuntimeError, 'lacks'):
                    local.prepare_delegation()
            self.assertFalse((group/'supervisor').exists())

    def test_other_processes_never_moved(self):
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            members = str(os.getpid())+'\n999999'
            (group/'cgroup.procs').write_text(members)
            with self.manager(group), patch.object(local, 'current_cgroup', return_value=group):
                with self.assertRaisesRegex(RuntimeError, 'other processes'):
                    local.prepare_delegation()
            self.assertEqual((group/'cgroup.procs').read_text(), members)
            self.assertFalse((group/'supervisor').exists())

    def test_enables_controllers_only_in_own_delegation(self):
        # Simulates cgroup filesystem semantics solely to test setup ordering.
        with tempfile.TemporaryDirectory() as folder:
            group = self.make_group(folder)
            original_write = Path.write_text
            writes = []
            def kernel_write(path, text, *args, **kwargs):
                self.assertIn(group, path.parents)
                writes.append(path)
                if path == group/'supervisor/cgroup.procs':
                    original_write(group/'cgroup.procs', '')
                if path.name == 'cgroup.subtree_control':
                    text = text.replace('+', '')
                return original_write(path, text, *args, **kwargs)
            with self.manager(group), patch.object(local, 'current_cgroup', return_value=group), \
                 patch.object(Path, 'write_text', kernel_write), patch.dict(os.environ, {}, clear=False):
                jobs = local.prepare_delegation()
                self.assertEqual(jobs, group/'jobs')
                self.assertEqual(os.environ['CODE_BREAKER_CGROUP_ROOT'], str(jobs))
            self.assertEqual(writes[0], group/'supervisor/cgroup.procs')
            self.assertEqual(set((jobs/'cgroup.subtree_control').read_text().split()), local.CONTROLLERS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
