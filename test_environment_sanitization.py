"""Names-only diagnostics and explicit environments at all job entrypoints.

Mocked wrapper tests never execute compilers or submitted code on the host.
The real child test runs only our fixed environment-inspection helper.
"""
import contextlib
import ctypes
import io
import json
import os
import resource
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch
import execution_isolation as isolation

EXPECTED = {'PATH':'/usr/bin:/bin', 'HOME':'/tmp', 'LANG':'C.UTF-8', 'TMPDIR':'/tmp'}
NOISY = {'PWD':'synthetic-private-directory', 'PRIVATE_TOKEN':'synthetic-secret-token',
         'JAVA_TOOL_OPTIONS':'synthetic-secret-jvm-argument', 'PYTHONPATH':'synthetic-private-path',
         'HOME':'synthetic-private-home', 'PATH':'synthetic-private-bin',
         'LC_CTYPE':'synthetic-private-locale'}


class UnclosedBuffer(io.StringIO):
    def close(self):
        pass


class EnvironmentSanitizationTests(unittest.TestCase):
    def test_driver_removes_pwd_and_secrets_before_compile_and_execution(self):
        diagnostic = UnclosedBuffer()
        def open_input(path, mode='r', *args, **kwargs):
            if path == '/input/job.json':
                return io.StringIO(json.dumps({'build':['/fake/compiler'], 'run':['/work/app']}))
            if path == '/work/.environment-names.json' and mode == 'w':
                return diagnostic
            raise AssertionError('Unexpected file access in trusted driver unit test')
        compile_call = Mock(return_value=types.SimpleNamespace(returncode=0))
        execute_call = Mock()
        with patch.dict(os.environ, NOISY, clear=True), \
             patch('builtins.open', side_effect=open_input), \
             patch.object(os, 'listdir', return_value=[]), patch.object(os, 'umask'), \
             patch.object(resource, 'setrlimit'), patch.object(subprocess, 'run', compile_call), \
             patch.object(os, 'execve', execute_call):
            exec(compile(isolation.JOB_DRIVER, 'trusted-driver', 'exec'), {})
            self.assertEqual(dict(os.environ), EXPECTED)
        self.assertEqual(compile_call.call_args.kwargs['env'], EXPECTED)
        self.assertEqual(execute_call.call_args.args[2], EXPECTED)
        for env in (compile_call.call_args.kwargs['env'], execute_call.call_args.args[2]):
            self.assertNotIn('PWD', env)
            self.assertNotIn('PRIVATE_TOKEN', env)
            self.assertNotIn('JAVA_TOOL_OPTIONS', env)
        names = json.loads(diagnostic.getvalue())
        self.assertEqual(names['received_names'], sorted(NOISY))
        self.assertEqual(names['removed_names'], sorted(set(NOISY) - set(EXPECTED)))
        self.assertTrue(all(value not in diagnostic.getvalue() for value in NOISY.values()),
                        'Diagnostic contained environment values')

    def test_final_compiler_and_runtime_execve_use_fresh_environment(self):
        for phase in ('compile', 'run'):
            with self.subTest(phase=phase):
                execute_call = Mock()
                # Fixed BPF bytes plus mocked prctl exercise the trusted wrapper
                # without installing filters or running any submitted program.
                with patch.dict(os.environ, NOISY, clear=True), \
                     patch.object(sys, 'argv', ['limits.py',phase,'/fake/program']), \
                     patch.object(resource, 'setrlimit'), patch.object(os, 'umask'), \
                     patch.object(os, 'execve', execute_call), \
                     patch('builtins.open', return_value=io.BytesIO(b'\0'*8)), \
                     patch.object(ctypes, 'CDLL', return_value=types.SimpleNamespace(prctl=Mock(return_value=0))):
                    exec(compile(isolation.BOOTSTRAP, 'trusted-limits', 'exec'), {})
                    self.assertEqual(dict(os.environ), EXPECTED)
                execute_call.assert_called_once()
                self.assertEqual(execute_call.call_args.args[2], EXPECTED)

    def test_fixed_environment_survives_real_python_exec_without_pwd_or_tokens(self):
        # Only fixed trusted introspection code is run, never player source.
        child = 'import json,os; print(json.dumps(sorted(os.environ)))'
        helper = (isolation.ENVIRONMENT_POLICY
                  + 'import os,sys\nos.execve(sys.executable, [sys.executable,"-I","-c",'
                  + repr(child) + '], dict(JOB_ENVIRONMENT))\n')
        # No real credentials are passed to this helper, only synthetic values.
        result = subprocess.run([sys.executable, '-I', '-c', helper], env=NOISY,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, 'Trusted child helper failed')
        self.assertEqual(set(json.loads(result.stdout)), set(EXPECTED))
        self.assertTrue(all(value not in result.stdout+result.stderr for value in NOISY.values()),
                        'Trusted helper printed environment values')

    def test_selfcheck_rejects_unexpected_names_without_printing_values(self):
        # Exercise the actual strict environment check before any namespace-only
        # checks. It is trusted validation code, not sandbox or player execution.
        source = isolation.PREFLIGHT_SCRIPT
        start = source.index('unexpected_names = ')
        end = source.index("require(os.environ.get('HOME')", start)
        namespace = {'os':os, 'json':json,
                     'require': lambda condition, message: None if condition else (_ for _ in ()).throw(RuntimeError(message))}
        with patch.dict(os.environ, dict(EXPECTED, PRIVATE_TOKEN=NOISY['PRIVATE_TOKEN']), clear=True):
            with self.assertRaises(RuntimeError) as failed:
                exec(compile(source[start:end], 'trusted-environment-check', 'exec'), namespace)
        message = str(failed.exception)
        self.assertIn('PRIVATE_TOKEN', message)
        self.assertTrue(NOISY['PRIVATE_TOKEN'] not in message, 'Self-check error contained a value')
        self.assertNotIn('PWD', EXPECTED)

    def test_preflight_diagnostic_prints_only_names(self):
        checked = {'status':'CODE_BREAKER_ISOLATION_READY',
                   'environment_names':{'received_names':sorted(set(EXPECTED)|{'PWD'}), 'removed_names':['PWD']}}
        result = {'out':json.dumps(checked), 'error':'', 'returncode':0}
        isolation.isolation_error.cache_clear()
        try:
            with patch.object(isolation, 'run_isolated', return_value=result), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(isolation.isolation_error(), '')
            self.assertIn('["PWD"]', output.getvalue())
            self.assertTrue(all(value not in output.getvalue() for value in NOISY.values()),
                            'Preflight printed environment values')
        finally:
            isolation.isolation_error.cache_clear()


if __name__ == '__main__':
    unittest.main(verbosity=2)
