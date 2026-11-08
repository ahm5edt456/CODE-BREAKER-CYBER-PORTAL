"""Restricted event-mode syntax, with mandatory Linux process isolation.

Source checks are defense in depth, not a sandbox. Neither compilation nor
execution is permitted when execution_isolation's real probe fails.
"""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from execution_isolation import isolation_error, run_isolated

SAFE = {'print','range','len','sum','min','max','int','float','str','bool','list','abs','enumerate','round'}
FORBIDDEN = ['#','import','package','Runtime','Process','System.exit','system','exec',
             'fork','fstream','fopen','freopen','File','Thread','Class','getClass',
             'include','\\u']

PYTHON_WORKER = '''import builtins, contextlib, io, json, traceback
class Limited(io.StringIO):
    def write(self, text):
        if self.tell() + len(text) > 4000:
            raise ValueError('Output limit exceeded.')
        return super().write(text)
out = Limited()
error = ''
try:
    scope = {'__builtins__': {name: getattr(builtins, name) for name in SAFE}}
    with contextlib.redirect_stdout(out):
        exec(compile(open('/work/player.py').read(), 'player.py', 'exec'), scope)
except BaseException as exc:
    frames = [frame for frame in traceback.extract_tb(exc.__traceback__) if frame.filename == 'player.py']
    location = f'Line {frames[-1].lineno}: ' if frames else ''
    error = f'{location}{type(exc).__name__}: {exc}'
print(json.dumps({'out': out.getvalue(), 'error': error}))
'''
JVM_OPTIONS = ['-Xmx64m', '-Xss256k', '-XX:+UseSerialGC', '-XX:ActiveProcessorCount=2',
               '-XX:ReservedCodeCacheSize=32m', '-XX:CompressedClassSpaceSize=32m',
               '-XX:MaxMetaspaceSize=128m', '-XX:+PerfDisableSharedMem']


def validate_source(code, language):
    if language == 'Python':
        tree = ast.parse(code)
        defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Attribute, ast.ClassDef,
                                 ast.With, ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)):
                raise ValueError('This operation is unavailable in event mode.')
            if isinstance(node, ast.Name) and node.id.startswith('__'):
                raise ValueError('Private names are unavailable.')
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE | defined):
                raise ValueError('This function is unavailable in event mode.')
    elif language in ('C++', 'Java'):
        if any(word in code for word in FORBIDDEN):
            raise ValueError('This operation is unavailable in event mode.')
    else:
        raise ValueError('Unsupported language: ' + language)


def native_source(code, language):
    body, marker, entry = code.partition('// ENTRY')
    if language == 'Java':
        if re.search(r'public\s+class\s+Main\b', code):
            return code + '\n'
        # Every generated boundary starts on a separate line, including after //.
        if marker:
            return 'public class Main {\n' + body + '\npublic static void main(String[] args) {\n' + entry + '\n}\n}\n'
        return 'public class Main {\npublic static void main(String[] args) {\n' + code + '\n}\n}\n'
    headers = '#include <iostream>\n#include <string>\n#include <algorithm>\n#include <vector>\n#include <numeric>\nusing namespace std;\n'
    if re.search(r'\bint\s+main\s*\(', code):
        return headers + code + '\n'
    if marker:
        return headers + body + '\nint main() {\n' + entry + '\n}\n'
    return headers + 'int main() {\n' + code + '\n}\n'


def cpp_build_command(compiler):
    """Use an installed linker within /usr, not Fedora's hidden alternatives alias."""
    linker = Path('/usr/bin/ld.bfd')
    try:
        resolved = linker.resolve(strict=True)
    except (OSError, RuntimeError):
        raise RuntimeError('C++ linker unavailable: /usr/bin/ld.bfd is required (Fedora binutils)') from None
    if (Path('/usr/bin') not in resolved.parents or not resolved.is_file()
            or not os.access(resolved, os.X_OK)):
        raise RuntimeError('C++ linker must be an executable tool within /usr/bin')
    # /usr/bin/ld -> /etc/alternatives/ld is intentionally unresolved inside the
    # sandbox. GCC's documented selection finds ld.bfd in the existing clean PATH.
    return [str(Path(compiler).resolve()), '-fuse-ld=bfd', '/work/main.cpp', '-o', '/work/app']


def execute(code, language='Python'):
    if len(code) > 12000:
        return {'out': '', 'error': 'Code is too long.'}
    try:
        validate_source(code, language)
        unavailable = isolation_error()
        if unavailable:
            return {'out': '', 'error': unavailable}
        with tempfile.TemporaryDirectory(prefix='code-breaker-job-') as folder:
            job = Path(folder)
            if language == 'Python':
                (job / 'player.py').write_text(code, encoding='utf-8')
                (job / 'worker.py').write_text('SAFE = ' + repr(SAFE) + '\n' + PYTHON_WORKER, encoding='utf-8')
                python = str(Path(sys.executable).resolve())
                if not python.startswith('/usr/'):
                    python = '/usr/bin/python3'
                result = run_isolated(job, [python, '-I', '/work/worker.py'])
                if result['error'] or result['returncode']:
                    return {'out': '', 'error': result['error']}
                return json.loads(result['out'])
            if language == 'Java':
                java = shutil.which('java')
                if not java:
                    return {'out': '', 'error': 'Java runtime/compiler unavailable. Install a JDK.'}
                java = str(Path(java).resolve())
                (job / 'Main.java').write_text(native_source(code, language), encoding='utf-8')
                build = [java] + JVM_OPTIONS + ['-m', 'jdk.compiler/com.sun.tools.javac.Main', '-proc:none', '/work/Main.java']
                run = [java] + JVM_OPTIONS + ['-cp', '/work', 'Main']
            else:
                compiler = shutil.which('g++')
                if not compiler:
                    return {'out': '', 'error': 'C++ compiler unavailable. Install g++.'}
                (job / 'main.cpp').write_text(native_source(code, language), encoding='utf-8')
                build = cpp_build_command(compiler)
                run = ['/work/app']
            result = run_isolated(job, build, compile_job=True, run_command=run)
            return {'out': result['out'], 'error': result['error']}
    except Exception as exc:
        return {'out': '', 'error': f'{type(exc).__name__}: {exc}'}


if __name__ == '__main__':
    # No host-side worker/native mode. Player text may only enter the sandbox.
    raise SystemExit('Use execute(); direct host execution is disabled.')
