"""Executable contracts for tiered puzzles, native wrappers, and UI submission."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import random
import shutil
import tempfile
import time
from pathlib import Path
from campaign_questions import TIERS, problem, fresh_campaign
from questions import check_answer
from runner import execute
import game
from campaign import CampaignGame


def settle(g):
    deadline = time.monotonic() + 20
    while g.future:
        assert time.monotonic() < deadline
        time.sleep(.01)
        g.update(.001)


languages = ['Python']
for language, compiler in [('C++', 'g++'), ('Java', 'javac')]:
    if shutil.which(compiler) and (language != 'Java' or shutil.which('java')):
        languages.append(language)
    else:
        print('SKIP execution:', language, '(compiler/runtime unavailable)')

with tempfile.TemporaryDirectory() as folder:
    game.DATA = Path(folder)
    for language in languages:
        # Every template in every mode, including independent literal solutions.
        for stage, tier in enumerate(TIERS, 1):
            for topic in tier:
                for mode in ['Debug', 'Complete Code', 'Predict Output']:
                    q = problem(language, topic, mode, random.Random(topic + 8))
                    assert q['stage'] == stage
                    result = execute(q['answer'], language)
                    assert not result['error'], (language, topic, result)
                    # Numeric goals provide an independent expected-output contract.
                    import re
                    numeric = re.search(r'Print (\d+)\.$', q['prompt'])
                    if numeric:
                        assert result['out'].strip() == numeric.group(1), (q, result)
                    if topic == 7:
                        assert result['out'].strip() == 'OPEN'
                    starter = execute(q['code'], language)
                    if mode == 'Predict Output':
                        assert starter == result
                    else:
                        assert starter['error'] or starter['out'] != result['out']
                    if mode == 'Debug':
                        value = result['out'].strip()
                        import json
                        literal = json.dumps(value)
                        equivalent = ('print(' + literal + ')' if language == 'Python' else
                                      'System.out.println(' + literal + ');' if language == 'Java' else
                                      'cout << ' + literal + ';')
                        assert check_answer(equivalent, q, language)
                        assert not check_answer(equivalent.replace(literal, '"WRONG"'), q, language)
        for mode in ['Debug', 'Complete Code', 'Predict Output']:
            g = CampaignGame(); g.language = language; g.challenge = mode; g.start()
            assert [q['stage'] for q in g.campaign_puzzles] == [1,1,2,2,3,3]
            edge = next(iter(g.gates)); q = dict(g.gates[edge]['question'])
            g.open_editor(edge); settle(g)
            assert not g.reference_error, g.error
            expected = g.expected
            g.close_editor(); g.open_editor(edge); settle(g)
            g.reset_code()
            assert g.gates[edge]['question'] == q
            assert '\n'.join(g.lines) == q['code'] and g.expected == expected
            lives = g.lives
            if mode == 'Predict Output':
                g.answer = 'WRONG'; g.run_code(True); assert g.lives == lives-1
                g.answer = expected
            else:
                g.lines = ['print("WRONG")' if language == 'Python' else
                           'System.out.println("WRONG");' if language == 'Java' else 'cout << "WRONG";']
                g.run_code(False); settle(g); assert g.lives == lives
                g.run_code(True); settle(g); assert g.lives == lives-1
                g.lines = q['answer'].splitlines()
                g.run_code(False); settle(g); assert g.test_status == 'Output matches expected'
            g.run_code(True); settle(g); assert g.gates[edge]['open']
        assert execute('print(' if language == 'Python' else 'int n = ;', language)['error']
        invalid = 'print(1 / 0)' if language == 'Python' else ('int n = 0; System.out.println(1 / n);' if language == 'Java' else 'throw 1;')
        assert execute(invalid, language)['error']
        if language == 'Python':
            # Restored event-mode policy intentionally disallows attribute calls.
            assert 'unavailable in event mode' in execute('values = [1, 2]\nvalues.append(3)')['error']
        elif language == 'C++':
            # Player-supplied includes remain blocked; wrappers provide headers.
            assert 'unavailable in event mode' in execute('#include <vector>', language)['error']
        else:
            assert execute('public class Main { public static void main(String[] args) { System.out.println(2); } } // end', language)['out'].strip() == '2'
        print('PASS:', language, 'all templates/modes, equivalent output, Run/Submit, errors, reopen/reset')
game.POOL.shutdown(wait=True)
