"""Security regression checks. No player code is ever run on the host.

Full isolation integration checks are explicitly skipped if the real kernel
probe fails. Unit checks and policy checks do not imply a working sandbox.
"""
import errno
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import execution_isolation as isolation
import runner
from campaign_questions import TIERS, fresh_campaign, problem


class SourceRestrictionTests(unittest.TestCase):
    def test_python_baseline(self):
        for code in ('import os', 'print((1).__class__)', 'open("/etc/passwd")',
                     'eval("1")', 'class A: pass', 'exec("print(1)")'):
            with self.subTest(code=code), self.assertRaises(ValueError):
                runner.validate_source(code, 'Python')

    def test_native_baseline(self):
        for language, code in [('C++', '#include <fstream>'), ('C++', 'system("id");'),
                               ('C++', 'fork();'), ('Java', 'Runtime.getRuntime();'),
                               ('Java', 'new java.io.File("/etc/passwd");'),
                               ('Java', 'new Thread();'), ('Java', r'\u0069mport java.io.*;')]:
            with self.subTest(language=language, code=code), self.assertRaises(ValueError):
                runner.validate_source(code, language)

    def test_all_challenge_sources_still_pass_policy(self):
        for language in ('Python', 'C++', 'Java'):
            for topic in sum((list(tier) for tier in TIERS), []):
                for mode in ('Debug', 'Complete Code', 'Predict Output'):
                    q = problem(language, topic, mode, random.Random(topic+8))
                    runner.validate_source(q['answer'], language)
                    # Incomplete Python may intentionally fail syntax parsing.
                    if mode != 'Complete Code' or language != 'Python':
                        runner.validate_source(q['code'], language)

    def test_native_wrapper_boundaries(self):
        for language in ('C++', 'Java'):
            for text in ('int a = 1; // final', 'int f() { return 1; }\n// ENTRY\n// final'):
                source = runner.native_source(text, language)
                self.assertIn('// final\n}', source)
                self.assertTrue(source.endswith('\n'))

    def test_failure_never_runs_or_compiles_on_host(self):
        for language, source in [('Python', 'print(42)'), ('C++', 'cout << 42;'),
                                 ('Java', 'System.out.println(42);')]:
            with patch.object(runner, 'isolation_error', return_value='Execution disabled: isolation unavailable.'), \
                 patch.object(runner, 'run_isolated') as isolated:
                result = runner.execute(source, language)
                self.assertEqual(result['out'], '')
                self.assertIn('Execution disabled', result['error'])
                isolated.assert_not_called()

    def test_old_host_worker_entrypoint_is_disabled(self):
        for flag in ('--worker', '--native'):
            result = subprocess.run([sys.executable, '-I', str(Path(runner.__file__).resolve()), flag],
                                    input='print("UNSAFE")', capture_output=True, text=True, timeout=3)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('UNSAFE', result.stdout)


class IsolationPolicyTests(unittest.TestCase):
    def test_cgroup_delegation_is_required_not_created_on_host(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'CODE_BREAKER_CGROUP_ROOT': folder}):
                with self.assertRaisesRegex(RuntimeError, 'delegated cgroup'):
                    with isolation.job_cgroup():
                        self.fail('Non-cgroup path accepted')
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_mounts_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            with isolation._seccomp_file() as policy:
                args = isolation.sandbox_command(directory, ['/usr/bin/true'], policy.fileno())
        for required in ('--unshare-all', '--unshare-user', '--disable-userns', '--clearenv',
                         '--seccomp', '--cap-drop', '--remount-ro'):
            self.assertIn(required, args)
        self.assertNotIn('--share-net', args)
        self.assertNotIn('--bind', args)
        for index, value in enumerate(args):
            if value in ('--ro-bind', '--bind'):
                source = args[index+1]
                self.assertNotIn(source, ('/', '/home', '/etc', '/tmp', str(Path.cwd())))
        self.assertIn('67108864', args)
        self.assertIn('16777216', args)

    def test_network_and_process_syscalls_denied_in_trusted_helper(self):
        # This is our own small policy probe, never player text. It only attempts
        # socket creation and fork after installing the restrictive filter.
        helper = '''import ctypes, errno, os, socket, sys
class Filter(ctypes.Structure):
    _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),('jf',ctypes.c_ubyte),('k',ctypes.c_uint)]
class Program(ctypes.Structure):
    _fields_=[('length',ctypes.c_ushort),('filter',ctypes.POINTER(Filter))]
data=os.read(int(sys.argv[1]),65536)
filters=(Filter*(len(data)//ctypes.sizeof(Filter))).from_buffer_copy(data)
program=Program(len(filters),filters)
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(38,1,0,0,0)==0
assert libc.prctl(22,2,ctypes.byref(program),0,0)==0
for operation in (lambda: socket.socket(), os.fork):
    try:
        operation()
    except OSError as exc:
        assert exc.errno==errno.EPERM, exc
    else:
        raise AssertionError('Operation unexpectedly permitted')
print('policy-denied')
'''
        with isolation._seccomp_file(False) as policy:
            result = subprocess.run([sys.executable, '-I', '-c', helper, str(policy.fileno())],
                                    pass_fds=(policy.fileno(),), capture_output=True,
                                    text=True, timeout=3, env={})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'policy-denied')

    def test_real_kernel_probe_and_all_language_fail_closed(self):
        unavailable = isolation.isolation_error()
        if not unavailable:
            self.skipTest('Isolation available; successful execution is checked by language regressions')
        for language, code in [('Python', 'print(42)'), ('C++', 'cout << 42;'),
                               ('Java', 'System.out.println(42);')]:
            result = runner.execute(code, language)
            self.assertEqual(result['out'], '')
            self.assertIn('Execution disabled: isolation unavailable', result['error'])
        print('\nREAL PROBE:', unavailable)

    @unittest.skipIf(bool(isolation.isolation_error()), 'Real isolation is blocked; no host fallback allowed')
    def test_isolated_files_network_environment_and_limits(self):
        # Deliberately bypass the syntax allowlist INSIDE isolation to test the
        # independent OS boundary. This code is never executed on the host.
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as private:
            sentinel = Path(private)/'personal-secret'
            sentinel.write_text('secret')
            script = '''import json, os, resource, socket
for path in PATHS:
    assert not os.path.exists(path), path
try:
    socket.socket()
except PermissionError:
    pass
else:
    raise AssertionError('Socket allowed')
try:
    os.fork()
except PermissionError:
    pass
else:
    raise AssertionError('Process allowed')
assert os.environ.get('PRIVATE_CANARY') is None
assert resource.getrlimit(resource.RLIMIT_AS)[0] == 2147483648
assert resource.getrlimit(resource.RLIMIT_NPROC)[0] == 64
assert resource.getrlimit(resource.RLIMIT_NOFILE)[0] == 64
print('isolated')
'''
            (Path(directory)/'probe.py').write_text('PATHS = '+repr([str(sentinel), str(Path.cwd()/'data/dashboard.json')])+'\n'+script)
            result = isolation.run_isolated(directory, ['/usr/bin/python3', '-I', '/work/probe.py'])
            self.assertEqual(result['error'], '', result)
            self.assertEqual(result['out'].strip(), 'isolated')
            self.assertEqual(sentinel.read_text(), 'secret')
            for code, expected in [('while True: pass', 'limit'),
                                   ('while True: print("x" * 1000)', 'Output limit'),
                                   ('x = bytearray(3 * 1024**3)', 'MemoryError')]:
                (Path(directory)/'probe.py').write_text(code)
                result = isolation.run_isolated(directory, ['/usr/bin/python3', '-I', '/work/probe.py'])
                self.assertIn(expected.lower(), result['error'].lower())


class QuestionPreservationTests(unittest.TestCase):
    def test_progression_rotation_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = None
            for index in range(30):
                language = ('Python', 'C++', 'Java')[index%3]
                mode = ('Debug', 'Complete Code', 'Predict Output')[index%3]
                _, questions, history = fresh_campaign(language, mode, directory, rng=random.Random(index))
                self.assertEqual([q['stage'] for q in questions], [1,1,2,2,3,3])
                if previous:
                    for q in questions:
                        self.assertNotEqual(q['fingerprint'], previous['fingerprints'].get(str(q['topic_id'])))
                previous = history
            script = 'from campaign_questions import fresh_campaign; import json,sys; print(json.dumps(fresh_campaign("Java","Debug",sys.argv[1])[2]))'
            result = json.loads(subprocess.check_output([sys.executable, '-c', script, directory], text=True))
            for topic, fingerprint in result['fingerprints'].items():
                self.assertNotEqual(fingerprint, previous['fingerprints'].get(topic))


if __name__ == '__main__':
    unittest.main(verbosity=2)
