"""Six increasing concepts, with fresh numeric variants in each campaign."""
import random
TOPICS=['Arithmetic','Indexing','Loop bounds','Accumulation','Functions + conditions','Nested loops']

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
    code,answer=pairs[rank]
    goals=[f'Add {a} and {b}. Print {a+b}.',f'Print the last array/list item: {data[2]}.',f'Print each number from 0 through {n-1}, one per line.',f'Sum 1 through {n}. Print {n*(n+1)//2}.',f'Even inputs are multiplied by {factor}; odd inputs return 0. Print {4*factor}.',f'Add column values from 1 through row, for rows 1 through {depth}. Print {depth*(depth+1)*(depth+2)//6}.']
    hints=['Use addition.','Indexes begin at zero.','The stop value is excluded in Python range; use the equivalent loop bound.','Accumulate instead of overwriting total.','Multiply only inside the even-number branch.','The inner loop must include the value of row.']
    if kind=='Complete Code':
        wrong=code.splitlines();lines=answer.splitlines()
        i=next(i for i,(x,y) in enumerate(zip(wrong,lines)) if x!=y)
        indent=lines[i][:len(lines[i])-len(lines[i].lstrip())]
        lines[i]=indent+('# TODO: complete this line' if language=='Python' else '// TODO: complete this line')
        code='\n'.join(lines)
    return dict(title=titles[rank],prompt=goals[rank],code=code,answer=answer,hint=hints[rank])
