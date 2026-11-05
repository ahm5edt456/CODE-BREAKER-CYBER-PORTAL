"""Curated puzzle bank. The IEEE edition evaluates observable output via runner.py."""
import random


def build_questions(language):
    """Return 3 difficulty tiers with 6 unique templates per language."""
    if language == 'Python':
        snippets = [
            ("Addition", "Make the output 12.", "a = 7\nb = 5\nprint(a - b)", "a = 7\nb = 5\nprint(a + b)", "Change subtraction to addition."),
            ("Assignment", "Print 9.", "value = 9\nprint(values)", "value = 9\nprint(value)", "Variable names must match."),
            ("Multiplication", "Make the output 24.", "n = 6\nprint(n + 4)", "n = 6\nprint(n * 4)", "Use multiplication."),
            ("String", "Print ACCESS.", "status = 'ACCESS'\nprint(state)", "status = 'ACCESS'\nprint(status)", "Print the declared variable."),
            ("Division", "Print 4.0.", "print(12 * 3)", "print(12 / 3)", "Use division."),
            ("Remainder", "Print 1.", "print(10 / 3)", "print(10 % 3)", "The modulo operator computes remainder."),
            ("Compare", "Print OPEN if score is 8.", "score = 8\nif score < 5:\n    print('OPEN')", "score = 8\nif score > 5:\n    print('OPEN')", "8 is greater than 5."),
            ("Loop range", "Print 0,1,2,3.", "for i in range(3):\n    print(i)", "for i in range(4):\n    print(i)", "range() excludes the stop value."),
            ("Boolean", "Print READY when key is True.", "key = True\nif not key:\n    print('READY')", "key = True\nif key:\n    print('READY')", "Remove negation."),
            ("List index", "Print 30.", "items = [10, 20, 30]\nprint(items[1])", "items = [10, 20, 30]\nprint(items[2])", "Indexes begin at zero."),
            ("Loop condition", "Print 1,2,3.", "n = 1\nwhile n < 3:\n    print(n)\n    n += 1", "n = 1\nwhile n <= 3:\n    print(n)\n    n += 1", "Use <= to include 3."),
            ("Logical AND", "Print PASS when both are True.", "a = True\nb = True\nif a and not b:\n    print('PASS')", "a = True\nb = True\nif a and b:\n    print('PASS')", "Both operands should be True."),
            ("Function", "Make the function return 10.", "def double(n):\n    return n + 2\nprint(double(5))", "def double(n):\n    return n * 2\nprint(double(5))", "Double means multiply by two."),
            ("Function call", "Print 15.", "def add(a, b):\n    return a + b\nprint(add(5, 5))", "def add(a, b):\n    return a + b\nprint(add(5, 10))", "Fix the argument."),
            ("List length", "Print 3.", "nums = [1, 2, 3]\nprint(len(nums) - 1)", "nums = [1, 2, 3]\nprint(len(nums))", "len() already returns the number of items."),
            ("Return", "Print HELLO.", "def greet():\n    return 'BYE'\nprint(greet())", "def greet():\n    return 'HELLO'\nprint(greet())", "Fix the returned string."),
            ("Sum", "Print 6.", "values = [1, 2, 3]\nprint(max(values))", "values = [1, 2, 3]\nprint(sum(values))", "Use sum(), not max()."),
            ("Slice", "Print [2, 3].", "nums = [1, 2, 3]\nprint(nums[0:2])", "nums = [1, 2, 3]\nprint(nums[1:3])", "Slices exclude the end index."),
        ]
    elif language == 'Java':
        snippets = [
            ("Addition", "Print 12.", "int a = 7;\nint b = 5;\nSystem.out.println(a - b);", "int a = 7;\nint b = 5;\nSystem.out.println(a + b);", "Change the operator."),
            ("Variable", "Print 9.", "int value = 9;\nSystem.out.println(values);", "int value = 9;\nSystem.out.println(value);", "Use the correct variable name."),
            ("Product", "Print 24.", "int n = 6;\nSystem.out.println(n + 4);", "int n = 6;\nSystem.out.println(n * 4);", "Use *."),
            ("String", "Print ACCESS.", 'String code = "ACCESS";\nSystem.out.println(codes);', 'String code = "ACCESS";\nSystem.out.println(code);', "Check the identifier."),
            ("Modulo", "Print 1.", "System.out.println(10 / 3);", "System.out.println(10 % 3);", "Use remainder operator."),
            ("Equality", "Print true.", "int n = 5;\nSystem.out.println(n != 5);", "int n = 5;\nSystem.out.println(n == 5);", "Use ==."),
            ("Compare", "Print OPEN.", 'int score = 8;\nif (score < 5) {\n    System.out.println("OPEN");\n}', 'int score = 8;\nif (score > 5) {\n    System.out.println("OPEN");\n}', "Use >."),
            ("Loop", "Print 0 through 3.", "for (int i = 0; i < 3; i++) {\n    System.out.println(i);\n}", "for (int i = 0; i < 4; i++) {\n    System.out.println(i);\n}", "Increase the upper bound."),
            ("Boolean", "Print READY.", 'boolean key = true;\nif (!key) {\n    System.out.println("READY");\n}', 'boolean key = true;\nif (key) {\n    System.out.println("READY");\n}', "Remove !."),
            ("Array index", "Print 30.", "int[] a = {10, 20, 30};\nSystem.out.println(a[1]);", "int[] a = {10, 20, 30};\nSystem.out.println(a[2]);", "Indexes begin at 0."),
            ("While", "Print 1 to 3.", "int n = 1;\nwhile (n < 3) {\n    System.out.println(n++);\n}", "int n = 1;\nwhile (n <= 3) {\n    System.out.println(n++);\n}", "Use <=."),
            ("AND", "Print PASS.", 'boolean a = true, b = true;\nif (a && !b) {\n    System.out.println("PASS");\n}', 'boolean a = true, b = true;\nif (a && b) {\n    System.out.println("PASS");\n}', "Both conditions must be true."),
            ("Method", "Make doubleIt(5) return 10.", "static int doubleIt(int n) {\n    return n + 2;\n}", "static int doubleIt(int n) {\n    return n * 2;\n}", "Use multiplication."),
            ("Return", "Make sum return 15.", "static int sum(int a, int b) {\n    return a - b;\n}", "static int sum(int a, int b) {\n    return a + b;\n}", "Use +."),
            ("Array length", "Print 3.", "int[] a = {1, 2, 3};\nSystem.out.println(a.length - 1);", "int[] a = {1, 2, 3};\nSystem.out.println(a.length);", "length already counts all elements."),
            ("Return string", "Make greet return HELLO.", 'static String greet() {\n    return "BYE";\n}', 'static String greet() {\n    return "HELLO";\n}', "Correct the returned string."),
            ("Minimum", "Print 2.", "System.out.println(Math.max(2, 9));", "System.out.println(Math.min(2, 9));", "Use min()."),
            ("Index", "Print 8.", "int[] data = {4, 8, 12};\nSystem.out.println(data[2]);", "int[] data = {4, 8, 12};\nSystem.out.println(data[1]);", "Select the middle element."),
        ]
    else:
        snippets = [
            ("Addition", "Print 12.", "int a = 7;\nint b = 5;\ncout << a - b;", "int a = 7;\nint b = 5;\ncout << a + b;", "Change the operator."),
            ("Variable", "Print 9.", "int value = 9;\ncout << values;", "int value = 9;\ncout << value;", "Match the variable name."),
            ("Product", "Print 24.", "int n = 6;\ncout << n + 4;", "int n = 6;\ncout << n * 4;", "Use *."),
            ("String", "Print ACCESS.", 'string code = "ACCESS";\ncout << codes;', 'string code = "ACCESS";\ncout << code;', "Check the identifier."),
            ("Modulo", "Print 1.", "cout << 10 / 3;", "cout << 10 % 3;", "Use %."),
            ("Equality", "Print true as 1.", "int n = 5;\ncout << (n != 5);", "int n = 5;\ncout << (n == 5);", "Use ==."),
            ("Compare", "Print OPEN.", 'int score = 8;\nif (score < 5) {\n    cout << "OPEN";\n}', 'int score = 8;\nif (score > 5) {\n    cout << "OPEN";\n}', "Use >."),
            ("Loop", "Print 0 through 3.", "for (int i = 0; i < 3; i++) {\n    cout << i;\n}", "for (int i = 0; i < 4; i++) {\n    cout << i;\n}", "Increase the end bound."),
            ("Boolean", "Print READY.", 'bool key = true;\nif (!key) {\n    cout << "READY";\n}', 'bool key = true;\nif (key) {\n    cout << "READY";\n}', "Remove !."),
            ("Array index", "Print 30.", "int a[] = {10, 20, 30};\ncout << a[1];", "int a[] = {10, 20, 30};\ncout << a[2];", "Indexes begin at 0."),
            ("While", "Print 1 to 3.", "int n = 1;\nwhile (n < 3) {\n    cout << n++;\n}", "int n = 1;\nwhile (n <= 3) {\n    cout << n++;\n}", "Use <=."),
            ("AND", "Print PASS.", 'bool a = true, b = true;\nif (a && !b) {\n    cout << "PASS";\n}', 'bool a = true, b = true;\nif (a && b) {\n    cout << "PASS";\n}', "Both conditions are true."),
            ("Function", "Make doubleIt(5) return 10.", "int doubleIt(int n) {\n    return n + 2;\n}", "int doubleIt(int n) {\n    return n * 2;\n}", "Use *."),
            ("Return", "Make sum return 15.", "int sum(int a, int b) {\n    return a - b;\n}", "int sum(int a, int b) {\n    return a + b;\n}", "Use +."),
            ("Array size", "Print 3.", "int a[] = {1, 2, 3};\ncout << sizeof(a) / sizeof(a[0]) - 1;", "int a[] = {1, 2, 3};\ncout << sizeof(a) / sizeof(a[0]);", "Do not subtract one."),
            ("Return string", "Make greet return HELLO.", 'string greet() {\n    return "BYE";\n}', 'string greet() {\n    return "HELLO";\n}', "Correct the returned string."),
            ("Minimum", "Print 2.", "cout << max(2, 9);", "cout << min(2, 9);", "Use min()."),
            ("Index", "Print 8.", "int data[] = {4, 8, 12};\ncout << data[2];", "int data[] = {4, 8, 12};\ncout << data[1];", "Select the middle element."),
        ]
    return [[dict(title=t, prompt=p, code=c, answer=a, hint=h)
             for t, p, c, a, h in snippets[i:i + 6]]
            for i in (0, 6, 12)]


def normalize(code):
    return ''.join(code.split())


def check_answer(submitted, question):
    return normalize(submitted) == normalize(question['answer'])


def pick_questions(language, level, count, rng=None):
    rng = rng or random
    return rng.sample(build_questions(language)[level], count)
