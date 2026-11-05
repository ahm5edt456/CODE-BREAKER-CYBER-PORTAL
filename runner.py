"""Local educational runner. Runs in a separate process, never in the UI.
Not a security sandbox: use only on a supervised local event computer.
"""
import ast, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

SAFE = {'print','range','len','sum','min','max','int','float','str','bool','list','abs','enumerate','round'}
def execute(code, language='Python'):
    if len(code)>12000: return {'out':'','error':'Code is too long.'}
    try:
        if language=='Python':
            tree=ast.parse(code)
            defined={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
            for n in ast.walk(tree):
                if isinstance(n,(ast.Import,ast.ImportFrom,ast.Attribute,ast.ClassDef,ast.With,ast.AsyncFunctionDef,ast.Global,ast.Nonlocal)):
                    raise ValueError('This operation is unavailable in event mode.')
                if isinstance(n,ast.Name) and n.id.startswith('__'): raise ValueError('Private names are unavailable.')
                if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in SAFE|defined):
                    raise ValueError('This function is unavailable in event mode.')
            cmd=[sys.executable,'-I',str(Path(__file__).resolve()),'--worker']
            data=code
        else:
            # Only the built-in educational syntax is supported. No OS/file/network APIs.
            forbidden=['#','import','package','Runtime','Process','System.exit','system','exec','fork','fstream','fopen','freopen','File','Thread','Class','getClass','include','\\u']
            if any(x in code for x in forbidden): raise ValueError('This operation is unavailable in event mode.')
            compiler=shutil.which('javac' if language=='Java' else 'g++')
            if not compiler: return {'out':'','error':f'{language} compiler unavailable. Install '+('a JDK (javac + java).' if language=='Java' else 'g++.')}
            with tempfile.TemporaryDirectory() as d:
                if language=='Java':
                    body, _, entry=code.partition('// ENTRY');methods='static ' in body
                    src='public class Main { '+(body+' public static void main(String[] args) {'+entry+'}' if methods else 'public static void main(String[] args) { '+code+' }')+' }'
                    p=Path(d)/'Main.java';p.write_text(src)
                    build=[compiler,str(p)]; run=[shutil.which('java') or 'java','-Xmx64m','-cp',d,'Main']
                else:
                    body, _, entry=code.partition('// ENTRY')
                    method=bool(__import__('re').search(r'(int|string)\s+\w+\([^)]*\)\s*\{',code))
                    src='#include <iostream>\n#include <string>\n#include <algorithm>\nusing namespace std;\n'+(body+'\nint main(){'+entry+'}' if method else 'int main(){'+code+'}')
                    p=Path(d)/'main.cpp';p.write_text(src);binary=d+('/app.exe' if os.name=='nt' else '/app');build=[compiler,str(p),'-o',binary];run=[binary]
                r=subprocess.run(build,capture_output=True,text=True,timeout=8)
                if r.returncode:return {'out':'','error':r.stderr[-2500:]}
                with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                    r=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--native']+run,stdout=stdout,stderr=stderr,timeout=2)
                    stdout.seek(0);stderr.seek(0)
                    out=stdout.read(4000).decode(errors='replace');error=stderr.read(2500).decode(errors='replace')
                    if r.returncode and not error:error='Execution stopped: resource limit or runtime error.'
                    return {'out':out,'error':error}
        r=subprocess.run(cmd,input=data,capture_output=True,text=True,timeout=2)
        if r.returncode and not r.stdout:return {'out':'','error':'Execution stopped: time or memory limit exceeded.'}
        return json.loads(r.stdout)
    except subprocess.TimeoutExpired:return {'out':'','error':'Time limit exceeded. Check your loop / recursion.'}
    except Exception as e:return {'out':'','error':f'{type(e).__name__}: {e}'}

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--native':
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_FSIZE,(8192,8192))
            resource.setrlimit(resource.RLIMIT_CPU,(2,2))
        except ImportError:pass
        os.execv(sys.argv[2],sys.argv[2:])
    import builtins, contextlib, io
    class Limited(io.StringIO):
        def write(self,s):
            if self.tell()+len(s)>4000:raise ValueError('Output limit exceeded.')
            return super().write(s)
    out=Limited();error=''
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(128*1024*1024,128*1024*1024))
            resource.setrlimit(resource.RLIMIT_CPU,(1,1))
        except (ImportError,ValueError):pass
        scope={'__builtins__':{k:getattr(builtins,k) for k in SAFE}}
        with contextlib.redirect_stdout(out):exec(compile(sys.stdin.read(),'player.py','exec'),scope)
    except BaseException as e:
        import traceback
        frames=[f for f in traceback.extract_tb(e.__traceback__) if f.filename=='player.py']
        location=f'Line {frames[-1].lineno}: ' if frames else ''
        error=f'{location}{type(e).__name__}: {e}'
    print(json.dumps({'out':out.getvalue(),'error':error}))
