"""Regression checks for comments and fresh rounds after a restart."""
import json,random,shutil,subprocess,sys,tempfile
from pathlib import Path
from campaign_questions import fresh_campaign
from runner import execute

for language in ('C++','Java'):
    if not shutil.which('g++' if language=='C++' else 'javac'):
        print('SKIP compiler unavailable:',language);continue
    output='cout << a + b;' if language=='C++' else 'System.out.println(a + b);'
    for ending in ('// TODO: complete this line','// last comment','// last comment\n'):
        result=execute('int a = 7;\nint b = 4;\n'+output+ending,language)
        assert not result['error'] and result['out'].strip()=='11',result
    method=('int add(int a, int b)' if language=='C++' else 'static int add(int a, int b)')+' { return a+b; }\n// ENTRY\n'
    output='cout << add(7,4);' if language=='C++' else 'System.out.println(add(7,4));'
    result=execute(method+output+'// final comment',language)
    assert not result['error'] and result['out'].strip()=='11',result
    assert execute('int a = ;',language)['error']

with tempfile.TemporaryDirectory() as directory:
    previous=None
    for i in range(100):
        plan,questions,history=fresh_campaign('Python','Complete Code',directory,rng=random.Random(i))
        assert len(set(plan))==6
        if previous:
            for stage in range(3):
                assert set(plan[stage*2:stage*2+2])!=set(previous['plan'][stage*2:stage*2+2])
            for q in questions:assert q['answer']!=previous['answers'].get(str(q['topic_id']))
        previous=history
    script='from campaign_questions import fresh_campaign; import json,sys; print(json.dumps(fresh_campaign("Python","Complete Code",sys.argv[1])[2]))'
    new=json.loads(subprocess.check_output([sys.executable,'-c',script,directory],text=True))
    assert new['plan']!=previous['plan']
    Path(directory,'question_history.json').write_text('{broken')
    assert len(fresh_campaign('Python','Debug',directory)[0])==6
print('PASS: final comments, real syntax failures, 100 fresh rounds, restart persistence and damaged-history recovery')

# History identifies the task/inputs across language and mode switches as well.
with tempfile.TemporaryDirectory() as directory:
    previous = None
    for index in range(30):
        language = ('Python', 'C++', 'Java')[index % 3]
        kind = ('Debug', 'Complete Code', 'Predict Output')[index % 3]
        plan, questions, history = fresh_campaign(language, kind, directory, rng=random.Random(index))
        assert [q['stage'] for q in questions] == [1, 1, 2, 2, 3, 3]
        if previous:
            for q in questions:
                assert q['fingerprint'] != previous['fingerprints'].get(str(q['topic_id']))
        previous = history
    script = 'from campaign_questions import fresh_campaign; import json,sys; print(json.dumps(fresh_campaign("Java","Debug",sys.argv[1])[2]))'
    restarted = json.loads(subprocess.check_output([sys.executable, '-c', script, directory], text=True))
    for topic, fingerprint in restarted['fingerprints'].items():
        assert fingerprint != previous['fingerprints'].get(topic)
print('PASS: task/input freshness across languages, modes and a separate application process')
