"""Regressions for report integrity, optimized verification, and cleanup scope."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import execution_isolation as isolation
from verification_report import write_report


class SecurityReviewTests(unittest.TestCase):
    def test_report_symlink_cannot_overwrite_saved_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = root/'saved-results.json'
            saved.write_text('[{"score":123}]')
            (root/'local-verification.json').symlink_to(saved)
            write_report(root, {'status':'blocked', 'flows':[]})
            self.assertEqual(saved.read_text(), '[{"score":123}]')
            report = root/'local-verification.json'
            self.assertFalse(report.is_symlink())
            self.assertEqual(json.loads(report.read_text())['status'], 'blocked')
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_report_failed_replace_keeps_previous_report_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root/'local-verification.json'
            report.write_text('old')
            with patch('verification_report.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    write_report(root, {'status':'failed'})
            self.assertEqual(report.read_text(), 'old')
            self.assertEqual([p.name for p in root.iterdir()], ['local-verification.json'])

    def test_verification_cannot_pass_with_optimized_assertions(self):
        result = subprocess.run([sys.executable, '-O', '-c',
            'from verify_playability import require; require(False, "deliberate failed check")'],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Verification failed', result.stderr)

    def test_cleanup_uses_job_cgroup_even_if_process_was_already_reaped(self):
        with tempfile.TemporaryDirectory() as directory:
            group = Path(directory)
            (group/'cgroup.kill').write_text('0')
            proc = Mock(returncode=0, pid=12345)
            with patch.object(os, 'killpg', side_effect=AssertionError('Unsafe numeric group signal')):
                isolation.finish_job(group, proc)
            self.assertEqual((group/'cgroup.kill').read_text(), '1')
            proc.wait.assert_called_once_with(timeout=3)
            proc.stdout.close.assert_called_once()
            proc.stderr.close.assert_called_once()

    def test_cleanup_wait_is_bounded_and_descriptors_close_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Mock()
            proc.wait.side_effect = subprocess.TimeoutExpired('job', 3)
            with self.assertRaises(subprocess.TimeoutExpired):
                isolation.finish_job(Path(directory), proc)
            proc.stdout.close.assert_called_once()
            proc.stderr.close.assert_called_once()

    def test_preflight_rejects_success_without_completed_selfcheck(self):
        for result in ({'out':'','error':'','returncode':0},
                       {'out':'CODE_BREAKER_ISOLATION_READY\n','error':'denied','returncode':1}):
            isolation.isolation_error.cache_clear()
            try:
                with patch.object(isolation, 'run_isolated', return_value=result):
                    self.assertIn('Execution disabled', isolation.isolation_error())
            finally:
                isolation.isolation_error.cache_clear()

    def test_environment_hint_cannot_select_an_unrelated_game_cgroup(self):
        base = Path('/sys/fs/cgroup/user.slice/code-breaker-'+'a'*32+'.scope/jobs')
        with patch.dict(os.environ, {'CODE_BREAKER_CGROUP_ROOT':str(base)}), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(Path, 'read_text', return_value='0::/user.slice/unrelated.scope'):
            with self.assertRaisesRegex(RuntimeError, 'outside this game supervisor'):
                isolation.validated_cgroup_root()

    def test_environment_hint_must_be_this_game_supervisor_jobs(self):
        base = Path('/sys/fs/cgroup/user.slice/code-breaker-'+'a'*32+'.scope/jobs')
        current = '0::'+str((base.parent/'supervisor').relative_to('/sys/fs/cgroup'))
        current = current.replace('0::', '0::/')
        with patch.dict(os.environ, {'CODE_BREAKER_CGROUP_ROOT':str(base)}), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(Path, 'read_text', return_value=current):
            self.assertEqual(isolation.validated_cgroup_root(), base)


if __name__ == '__main__':
    unittest.main(verbosity=2)
