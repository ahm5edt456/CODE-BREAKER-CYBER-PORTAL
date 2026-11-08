"""Thirteen question types; each campaign samples six across increasing difficulty tiers."""
import random
import json
import os
import tempfile
from pathlib import Path
from itertools import combinations
TOPICS=['Arithmetic','Indexing','Loop bounds','Accumulation','Functions + conditions','Nested loops','String joining','Comparisons','Filtered counting','Positive transformation','Unit conversion','Filtered sum','Function grid']
TIERS=((0,6,1,7,10),(2,3,8,11),(4,9,5,12))
ORDER={topic:i for i,topic in enumerate(sum((list(t) for t in TIERS),[]))}

def campaign_plan(rng=None):
    rng=rng or random
    return [topic for tier in TIERS for topic in sorted(rng.sample(tier,2),key=ORDER.get)]

def fresh_campaign(language,kind,directory,previous=None,rng=None):
    """Rotate each tier and change repeated topics' values, including after restart."""
    rng=rng or random.SystemRandom()
    path=Path(directory)/'question_history.json'
    if previous is None:
        try:
            previous=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            previous={}
    if not isinstance(previous,dict):previous={}
    old_plan=previous.get('plan',[])
    if not isinstance(old_plan,list):old_plan=[]
    old_answers=previous.get('answers',{})
    if not isinstance(old_answers,dict):old_answers={}
    old_fingerprints=previous.get('fingerprints',{})
    if not isinstance(old_fingerprints,dict):old_fingerprints={}
    plan=[]
    for stage,tier in enumerate(TIERS):
        old=set(t for t in old_plan[stage*2:stage*2+2] if isinstance(t,int))
        choices=[pair for pair in combinations(tier,2) if set(pair)!=old]
        plan.extend(sorted(rng.choice(choices),key=ORDER.get))
    questions=[]
    for topic in plan:
        # Every topic has at least two variants. Reject the previous exact answer.
        q=problem(language,topic,kind,rng)
        while (q['answer']==old_answers.get(str(topic))
               or q['fingerprint']==old_fingerprints.get(str(topic))):
            q=problem(language,topic,kind,rng)
        questions.append(q)
    history={'plan':plan,'fingerprints':{str(q['topic_id']):q['fingerprint'] for q in questions},'answers':{str(q['topic_id']):q['answer'] for q in questions}}
    temporary=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                prefix='questions-',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(history,stream,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    except OSError:
        pass  # The caller retains history for this process if the folder is read-only.
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
    return plan,questions,history

def problem(language,rank,kind,rng=None):
    rng=rng or random
    a,b=rng.randint(3,9),rng.randint(3,9)
    data=rng.sample(range(10,60,5),3);n=rng.randint(4,6);factor=rng.randint(2,3);depth=rng.randint(3,4)
    titles=TOPICS
    if language=='Python':
        pairs=[(f'a = {a}\nb = {b}\nprint(a - b)',f'a = {a}\nb = {b}\nprint(a + b)'),
          (f'data = {data}\nprint(data[1])',f'data = {data}\nprint(data[2])'),
          (f'for i in range({n-1}):\n    print(i)',f'for i in range({n}):\n    print(i)'),
          (f'total = 0\nn = 1\nwhile n <= {n}:\n    total = n\n    n += 1\nprint(total)',f'total = 0\nn = 1\nwhile n <= {n}:\n    total += n\n    n += 1\nprint(total)'),
          (f'def boost(n):\n    if n % 2 == 0:\n        return n\n    return 0\nprint(boost(3) + boost(4))',f'def boost(n):\n    if n % 2 == 0:\n        return n * {factor}\n    return 0\nprint(boost(3) + boost(4))'),
          (f'total = 0\nfor row in range(1, {depth+1}):\n    for col in range(1, row):\n        total += col\nprint(total)',f'total = 0\nfor row in range(1, {depth+1}):\n    for col in range(1, row + 1):\n        total += col\nprint(total)')]
    else:
        java=language=='Java'
        def out(s):return f'System.out.println({s});' if java else f'cout << {s} << "\\n";'
        declaration=f'int[] data = {{{", ".join(map(str,data))}}};' if java else f'int data[] = {{{", ".join(map(str,data))}}};'
        prefix='static ' if java else ''
        pairs=[(f'int a = {a};\nint b = {b};\n'+out('a - b'),f'int a = {a};\nint b = {b};\n'+out('a + b')),
          (declaration+'\n'+out('data[1]'),declaration+'\n'+out('data[2]')),
          (f'for (int i = 0; i < {n-1}; i++) {{\n    '+out('i')+'\n}',f'for (int i = 0; i < {n}; i++) {{\n    '+out('i')+'\n}'),
          (f'int total = 0;\nint n = 1;\nwhile (n <= {n}) {{\n    total = n;\n    n++;\n}}\n'+out('total'),f'int total = 0;\nint n = 1;\nwhile (n <= {n}) {{\n    total += n;\n    n++;\n}}\n'+out('total')),
          (prefix+'int boost(int n) {\n    if (n % 2 == 0) {\n        return n;\n    }\n    return 0;\n}\n// ENTRY\n'+out('boost(3) + boost(4)'),prefix+'int boost(int n) {\n    if (n % 2 == 0) {\n        return n * '+str(factor)+';\n    }\n    return 0;\n}\n// ENTRY\n'+out('boost(3) + boost(4)')),
          (f'int total = 0;\nfor (int row = 1; row <= {depth}; row++) {{\n    for (int col = 1; col < row; col++) {{\n        total += col;\n    }}\n}}\n'+out('total'),f'int total = 0;\nfor (int row = 1; row <= {depth}; row++) {{\n    for (int col = 1; col <= row; col++) {{\n        total += col;\n    }}\n}}\n'+out('total'))]
    prefix=rng.choice(['BYTE','CODE','IEEE','MAZE']);suffix=rng.choice(['LAB','RUN','CORE'])
    threshold=rng.randint(5,15);score=threshold+rng.randint(1,6)
    even_count=rng.choice([2,4]);filtered=rng.sample([2,4,6,8,10,12],even_count)+rng.sample([1,3,5,7,9,11],6-even_count);rng.shuffle(filtered)
    values=rng.sample([-5,-4,-3,-2,-1],2)+rng.sample([1,2,3,4,5],3);rng.shuffle(values)
    positive=sum(v for v in values if v>0)*factor
    if language=='Python':
        additions=[
          (f"prefix = '{prefix}'\nsuffix = '{suffix}'\nprint(prefix + '_' + suffix)",f"prefix = '{prefix}'\nsuffix = '{suffix}'\nprint(prefix + '-' + suffix)"),
          (f"score = {score}\nthreshold = {threshold}\nif score < threshold:\n    print('OPEN')\nelse:\n    print('LOCKED')",f"score = {score}\nthreshold = {threshold}\nif score >= threshold:\n    print('OPEN')\nelse:\n    print('LOCKED')"),
          (f'values = {filtered}\ncount = 0\nfor n in values:\n    if n % 2 != 0:\n        count += 1\nprint(count)',f'values = {filtered}\ncount = 0\nfor n in values:\n    if n % 2 == 0:\n        count += 1\nprint(count)'),
          (f'def positive_total(values):\n    total = 0\n    for n in values:\n        if n > 0:\n            total += n\n    return total\nprint(positive_total({values}))',f'def positive_total(values):\n    total = 0\n    for n in values:\n        if n > 0:\n            total += n * {factor}\n    return total\nprint(positive_total({values}))')]
    else:
        string_type='String' if java else 'string'
        strings=f'{string_type} prefix = "{prefix}";\n{string_type} suffix = "{suffix}";\n'
        compare=f'int score = {score};\nint threshold = {threshold};\n'
        comparison=lambda op:compare+f'if (score {op} threshold) {{\n    '+out('"OPEN"')+'\n} else {\n    '+out('"LOCKED"')+'\n}'
        array_type='int[]' if java else 'int'
        filtered_decl=(f'int[] values = {{{", ".join(map(str,filtered))}}};' if java else f'int values[] = {{{", ".join(map(str,filtered))}}};')
        counter=lambda op:filtered_decl+'\nint count = 0;\nfor (int n : values) {\n    if (n % 2 '+op+' 0) {\n        count++;\n    }\n}\n'+out('count')
        if java:
            def transformer(expr):
                return 'static int positiveTotal(int[] values) {\n    int total = 0;\n    for (int n : values) {\n        if (n > 0) {\n            total += '+expr+';\n        }\n    }\n    return total;\n}\n// ENTRY\n'+out('positiveTotal(new int[]{'+', '.join(map(str,values))+'})')
        else:
            def transformer(expr):
                return 'int positiveTotal(int values[], int size) {\n    int total = 0;\n    for (int i = 0; i < size; i++) {\n        int n = values[i];\n        if (n > 0) {\n            total += '+expr+';\n        }\n    }\n    return total;\n}\n// ENTRY\nint values[] = {'+', '.join(map(str,values))+'};\n'+out('positiveTotal(values, 5)')
        additions=[(strings+out('prefix + "_" + suffix'),strings+out('prefix + "-" + suffix')),(comparison('<'),comparison('>=')),(counter('!='),counter('==')),(transformer('n'),transformer('n * '+str(factor)))]
    pairs.extend(additions)
    # Additional tasks vary the work performed, not just the constants.
    if language=='Python':
        conversion=lambda op: f'minutes = {a}\nprint(minutes {op} 60)'
        selected=lambda op: f'values = {data}\ntotal = 0\nfor value in values:\n    if value {op} {data[0]}:\n        total += value\nprint(total)'
        grid=lambda op: f'def grid_total(rows, cols):\n    total = 0\n    for row in range(1, rows + 1):\n        for col in range(1, cols + 1):\n            total += row {op} col\n    return total\nprint(grid_total({factor}, {depth}))'
    else:
        conversion=lambda op: f'int minutes = {a};\n'+out(f'minutes {op} 60')
        selected=lambda op: declaration+f'\nint total = 0;\nfor (int value : data) {{\n    if (value {op} {data[0]}) {{\n        total += value;\n    }}\n}}\n'+out('total')
        grid=lambda op: ('static ' if java else '')+'int gridTotal(int rows, int cols) {\n    int total = 0;\n    for (int row = 1; row <= rows; row++) {\n        for (int col = 1; col <= cols; col++) {\n            total += row '+op+' col;\n        }\n    }\n    return total;\n}\n// ENTRY\n'+out(f'gridTotal({factor}, {depth})')
    pairs.extend([(conversion('+'),conversion('*')),
                  (selected('<'),selected('>')),(grid('-'),grid('*'))])
    code,answer=pairs[rank]
    goals=[f'Add {a} and {b}. Print {a+b}.',f'Print the last array/list item: {data[2]}.',f'Print each number from 0 through {n-1}, one per line.',f'Sum 1 through {n}. Print {n*(n+1)//2}.',f'Even inputs are multiplied by {factor}; odd inputs return 0. Print {4*factor}.',f'Add column values from 1 through row, for rows 1 through {depth}. Print {depth*(depth+1)*(depth+2)//6}.',f'Join the two strings with a hyphen. Print {prefix}-{suffix}.','Print OPEN when score reaches or exceeds threshold; otherwise print LOCKED.',f'Count only even numbers in the array/list. Print {even_count}.',f'Multiply each positive value by {factor}, ignore negative values, then sum. Print {positive}.']
    hints=['Use addition.','Indexes begin at zero.','The stop value is excluded in Python range; use the equivalent loop bound.','Accumulate instead of overwriting total.','Multiply only inside the even-number branch.','The inner loop must include the value of row.','Join the strings with the requested separator.','Use the greater-than-or-equal comparison.','Even numbers have remainder zero when divided by 2.','Apply the multiplier to each positive value before adding.']
    goals.extend([f'Convert {a} minutes to seconds. Print {a*60}.',
                  f'Sum only values greater than {data[0]}. Print {sum(v for v in data if v>data[0])}.',
                  f'Use a function with nested loops to sum row * col for rows 1 through {factor} and columns 1 through {depth}. Print {factor*(factor+1)*depth*(depth+1)//4}.'])
    hints.extend(['There are 60 seconds in one minute.',
                  'Use a strict greater-than comparison, then accumulate the matching values.',
                  'Multiply the row and column inside the inner loop; return after both loops finish.'])
    missing_line=None
    if kind=='Complete Code':
        wrong=code.splitlines();lines=answer.splitlines()
        i=next(i for i,(x,y) in enumerate(zip(wrong,lines)) if x!=y)
        missing_line=i
        indent=lines[i][:len(lines[i])-len(lines[i].lstrip())]
        lines[i]=indent+('# TODO: complete this line' if language=='Python' else '// TODO: complete this line')
        code='\n'.join(lines)
    if kind=='Predict Output':
        code=answer
    inputs=[(a,b),data,n,n,factor,depth,(prefix,suffix),(score,threshold),filtered,(values,factor),a,data,(factor,depth)][rank]
    fingerprint=json.dumps([rank,inputs],sort_keys=True)
    return dict(fingerprint=fingerprint, stage=next(i+1 for i,tier in enumerate(TIERS) if rank in tier), title=titles[rank],prompt=goals[rank],code=code,answer=answer,hint=hints[rank],missing_line=missing_line,topic_id=rank)
