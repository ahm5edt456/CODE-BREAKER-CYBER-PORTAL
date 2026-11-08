"""Real headless game Run/Submit smoke checks, with isolated temporary player data.

Run through bash local.sh verify. A blocked sandbox is an error, never a pass.
The JSON report records exactly which language/mode flows actually completed.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import time

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
ROOT = Path(__file__).resolve().parent
from verification_report import write_report


def require(condition, *detail):
    if not condition:
        raise RuntimeError('Verification failed: ' + ' '.join(map(str, detail)))


def data_hashes():
    return {name: hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()
            if (ROOT/'data'/name).exists() else None
            for name in ('dashboard.json', 'question_history.json')}


def settle(game):
    deadline = time.monotonic() + 25
    while game.future:
        if time.monotonic() >= deadline:
            raise AssertionError('Game runner did not finish within 25 seconds')
        time.sleep(.01)
        game.update(.001)


def run_flows(report):
    import game as core
    from campaign import CampaignGame
    try:
        with tempfile.TemporaryDirectory(prefix='code-breaker-ui-check-') as directory:
            # All game state writes use this disposable directory. Never save a
            # test result or rotation history into the real player's data.
            core.DATA = Path(directory)
            for language in ('Python', 'C++', 'Java'):
                for mode in ('Debug', 'Complete Code', 'Predict Output'):
                    app = CampaignGame()
                    app.language = language
                    app.challenge = mode
                    app.start()
                    edge = next(iter(app.gates))
                    question = dict(app.gates[edge]['question'])
                    app.open_editor(edge)
                    settle(app)
                    require(not app.reference_error, language, mode, app.error)
                    require(bool(app.expected.strip()), language, mode, 'Missing reference output')
                    lives, score = app.lives, app.score
                    if mode == 'Predict Output':
                        app.answer = app.expected.strip()
                    else:
                        code = question['answer']
                        if language != 'Python':
                            code += '// trailing comment'
                        app.lines = code.split('\n')
                    app.run_code(False)
                    settle(app)
                    require(not app.gates[edge]['open'], 'Run unexpectedly opened a gate')
                    require(app.lives == lives, 'Run changed the life count')
                    if mode != 'Predict Output':
                        require(not app.error, language, mode, app.error)
                        require(app.test_status == 'Output matches expected', language, mode, app.output, app.expected)
                    app.run_code(True)
                    settle(app)
                    require(app.gates[edge]['open'], language, mode, app.error, app.notice)
                    require(app.lives == lives and app.score > score, 'Invalid lives or score after Submit')
                    require(app.gates[edge]['question'] == question, 'Question changed during verification')
                    report['flows'].append({'language': language, 'mode': mode,
                                            'reference': 'passed', 'run': 'passed', 'submit': 'passed',
                                            'predict_run_executes_code': False} if mode == 'Predict Output' else
                                           {'language': language, 'mode': mode,
                                            'reference': 'passed', 'run': 'passed', 'submit': 'passed'})
                    print(f'PASS: {language} / {mode}: real reference, Run and Submit', flush=True)
    finally:
        core.POOL.shutdown(wait=True)


def main():
    from execution_isolation import isolation_error
    before = None
    report = {'status': 'blocked', 'flows': []}
    exit_code = 2
    try:
        before = data_hashes()
        error = isolation_error()
        if error:
            report['error'] = error
            print(error)
        else:
            report['status'] = 'failed'
            run_flows(report)
            require(len(report['flows']) == 9, 'Not all language/mode flows completed')
            report['status'] = 'passed'
            exit_code = 0
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        print(report['error'])
        exit_code = 1
    finally:
        try:
            report['saved_player_data_unchanged'] = before is not None and before == data_hashes()
        except OSError:
            report['saved_player_data_unchanged'] = False
        if not report['saved_player_data_unchanged']:
            report['status'] = 'failed'
            report['error'] = 'Saved player data changed unexpectedly'
            exit_code = 1
        write_report(ROOT, report)
        print('Verification report:', ROOT/'local-verification.json')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
