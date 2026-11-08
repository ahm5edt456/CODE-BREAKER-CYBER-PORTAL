"""Fail-closed Linux isolation for local educational code (not a kernel boundary).

Only toolchain files and one disposable job directory are mounted. Never fall
back to host execution if namespaces, seccomp, or resource limits fail.
"""
import contextlib
import ctypes
import ctypes.util
import errno
import functools
import json
import os
import platform
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

OUTPUT_LIMIT = 8192
MEMORY_LIMIT = 2 * 1024**3  # Per-process virtual address space, including JVM reservations.
PROCESS_LIMIT = 64          # RLIMIT_NPROC counts threads as well as processes for this UID.

# No inherited values: all compilation and execution entrypoints rebuild this
# exact environment. LC_CTYPE remains tolerated by the existing self-check for
# CPython locale coercion, but is never copied from the caller.
JOB_ENVIRONMENT = {'PATH': '/usr/bin:/bin', 'HOME': '/tmp',
                   'LANG': 'C.UTF-8', 'TMPDIR': '/tmp'}
ENVIRONMENT_POLICY = 'JOB_ENVIRONMENT = ' + repr(JOB_ENVIRONMENT) + '\n'

# This bootstrap is trusted and copied into the disposable job, not bind-mounted
# from the project. Limits apply to compilers too, before processing player text.
BOOTSTRAP = 'import os, resource, sys, ctypes\n' + ENVIRONMENT_POLICY + '''os.environ.clear()
os.environ.update(JOB_ENVIRONMENT)
compile_job = sys.argv[1] == "compile"
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (8 if compile_job else 2, 8 if compile_job else 2))
resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
size = 32 * 1024 * 1024 if compile_job else 8192
resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))
os.umask(0o077)
if not compile_job:
    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte), ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]
    data = open('/input/runtime.bpf', 'rb').read()
    filters = (Filter * (len(data) // ctypes.sizeof(Filter))).from_buffer_copy(data)
    program = Program(len(filters), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise RuntimeError('Cannot apply runtime syscall restrictions')
os.execve(sys.argv[2], sys.argv[2:], dict(JOB_ENVIRONMENT))
'''


JOB_DRIVER = "import json, os, resource, shutil, subprocess, sys\nentry_names = sorted(os.environ)\nENVIRONMENT_POLICY\nos.environ.clear()\nos.environ.update(JOB_ENVIRONMENT)\nresource.setrlimit(resource.RLIMIT_CORE, (0, 0))\nresource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))\nresource.setrlimit(resource.RLIMIT_NPROC, (64, 64))\nresource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))\nresource.setrlimit(resource.RLIMIT_CPU, (10, 10))\nresource.setrlimit(resource.RLIMIT_FSIZE, (33554432, 33554432))\nos.umask(0o077)\njob = json.load(open('/input/job.json'))\nfor name in os.listdir('/input'):\n    if name not in ('limits.py', 'driver.py', 'job.json', 'runtime.bpf'):\n        shutil.copyfile('/input/' + name, '/work/' + name)\n# This diagnostic deliberately contains NAMES ONLY, never environment values.\nwith open('/work/.environment-names.json', 'w') as stream:\n    json.dump({'received_names': entry_names,\n               'removed_names': sorted(set(entry_names) - set(JOB_ENVIRONMENT))}, stream)\nif job['build']:\n    try:\n        result = subprocess.run([sys.executable, '-I', '/input/limits.py', 'compile'] + job['build'],\n                                timeout=10, env=dict(JOB_ENVIRONMENT))\n    except subprocess.TimeoutExpired:\n        print('Compilation time limit exceeded.', file=sys.stderr)\n        sys.exit(1)\n    if result.returncode:\n        sys.exit(1)\nos.execve(sys.executable, [sys.executable, '-I', '/input/limits.py', 'run'] + job['run'],\n          dict(JOB_ENVIRONMENT))\n".replace('ENVIRONMENT_POLICY\n', ENVIRONMENT_POLICY)

def _seccomp_file(compile_job=False):
    """Export a libseccomp filter; absence/failure is fatal, never optional."""
    library = ctypes.util.find_library('seccomp')
    if not library:
        raise RuntimeError('libseccomp is required')
    lib = ctypes.CDLL(library, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.seccomp_export_bpf.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError('seccomp_init failed')
    exported = tempfile.TemporaryFile()
    try:
        # No socket creation, even loopback or Unix sockets. Block namespace and
        # host introspection primitives as defense in depth after bwrap setup.
        denied = ('socket', 'socketpair', 'connect', 'bind', 'listen', 'accept',
                  'accept4', 'sendto', 'sendmsg', 'sendmmsg', 'recvfrom', 'recvmsg',
                  'recvmmsg', 'socketcall', 'ptrace', 'process_vm_readv',
                  'process_vm_writev', 'mount', 'umount2', 'pivot_root', 'unshare',
                  'setns', 'bpf', 'perf_event_open', 'keyctl', 'add_key',
                  'request_key', 'userfaultfd', 'io_uring_setup', 'open_by_handle_at',
                  'kexec_load', 'init_module', 'finit_module', 'delete_module',
                  'reboot', 'swapon', 'swapoff')
        for name in denied:
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError('Cannot restrict syscall: ' + name)
        if not compile_job:
            # Java needs threads, but player programs must not create child
            # processes. clone3 returns ENOSYS so libc can use filtered clone.
            for name, error in [('fork', errno.EPERM), ('vfork', errno.EPERM), ('clone3', errno.ENOSYS)]:
                number = lib.seccomp_syscall_resolve_name(name.encode())
                if number >= 0 and lib.seccomp_rule_add(context, 0x00050000 | error, number, 0) != 0:
                    raise RuntimeError('Cannot restrict process creation')
            class Comparison(ctypes.Structure):
                _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int),
                            ('datum_a', ctypes.c_uint64), ('datum_b', ctypes.c_uint64)]
            lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                                  ctypes.c_int, ctypes.c_uint,
                                                  ctypes.POINTER(Comparison)]
            lib.seccomp_rule_add_array.restype = ctypes.c_int
            clone = lib.seccomp_syscall_resolve_name(b'clone')
            if clone < 0:
                raise RuntimeError('Unsupported clone ABI')
            # Only CLONE_THREAD, with no new namespaces, may be used.
            rules = [(0x00010000, 0)]
            rules += [(flag, flag) for flag in (0x00020000, 0x02000000, 0x04000000,
                                                0x08000000, 0x10000000, 0x20000000,
                                                0x40000000, 0x00000080)]
            for mask, value in rules:
                comparison = Comparison(0, 7, mask, value)
                if lib.seccomp_rule_add_array(context, 0x00050000 | errno.EPERM,
                                              clone, 1, ctypes.byref(comparison)) != 0:
                    raise RuntimeError('Cannot restrict clone flags')
        if lib.seccomp_export_bpf(context, exported.fileno()) != 0:
            raise RuntimeError('Cannot export seccomp filter')
        exported.seek(0)
        return exported
    except BaseException:
        exported.close()
        raise
    finally:
        lib.seccomp_release(context)


def sandbox_command(directory, command, filter_fd, compile_job=False):
    """Build a minimal mount tree, never ro-bind /, /home, /etc, or the project."""
    bwrap = shutil.which('bwrap')
    if sys.platform != 'linux' or platform.machine() != 'x86_64' or not bwrap or os.geteuid() == 0:
        raise RuntimeError('A non-root x86_64 Linux account and bubblewrap are required')
    runtime_python = str(Path(sys.executable).resolve())
    if not runtime_python.startswith('/usr/'):
        runtime_python = '/usr/bin/python3'
    args = [bwrap, '--unshare-all', '--unshare-user', '--disable-userns', '--die-with-parent',
            '--cap-drop', 'ALL', '--clearenv',
            '--ro-bind', '/usr', '/usr']
    for name in ('lib', 'lib64', 'bin', 'sbin'):
        path = Path('/') / name
        if path.is_symlink():
            args += ['--symlink', os.readlink(path), str(path)]
        elif path.is_dir():
            args += ['--ro-bind', str(path), str(path)]
    if Path('/etc/ld.so.cache').is_file():
        args += ['--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache']
    # Fedora keeps public JDK configuration outside /usr. Expose only these
    # specific files, never the entire /etc/java tree (which may contain secrets).
    java = shutil.which('java')
    if java:
        java_conf = Path(java).resolve().parent.parent / 'conf'
        for relative in ('security/java.security', 'net.properties', 'logging.properties', 'jaxp.properties'):
            config = java_conf / relative
            if config.is_file():
                target = config.resolve()
                if str(target).startswith('/etc/java/'):
                    args += ['--ro-bind', str(target), str(target)]
    args += ['--proc', '/proc', '--dev', '/dev',
             '--size', '16777216', '--tmpfs', '/tmp',
             '--size', '67108864', '--tmpfs', '/work',
             '--ro-bind', str(directory), '/input', '--chdir', '/work',
             '--remount-ro', '/',
             '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
             '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'TMPDIR', '/tmp',
             '--seccomp', str(filter_fd), '--', runtime_python, '-I', '/input/driver.py']
    return args



def validated_cgroup_root():
    """An environment variable is a path hint, never delegation authority."""
    raw = os.environ.get('CODE_BREAKER_CGROUP_ROOT')
    if not raw:
        raise RuntimeError('A delegated cgroup v2 directory is required (use local.sh)')
    base = Path(raw).resolve()
    hierarchy = Path('/sys/fs/cgroup')
    scope = base.parent
    if (hierarchy not in base.parents or base.name != 'jobs'
            or not re.fullmatch(r'code-breaker-[0-9a-f]{32}\.scope', scope.name)
            or not base.is_dir()):
        raise RuntimeError('A delegated cgroup v2 game subtree is required')
    current = None
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            current = (hierarchy / line[3:].lstrip('/')).resolve()
    if current != scope/'supervisor':
        raise RuntimeError('Refusing a cgroup outside this game supervisor scope')
    return base


@contextlib.contextmanager
def job_cgroup():
    """Require game-local delegated cgroup accounting; never change host policy."""
    base = validated_cgroup_root()
    enabled = set((base / 'cgroup.subtree_control').read_text().split())
    if not {'memory', 'pids', 'cpu'} <= enabled:
        raise RuntimeError('Delegated cgroup must have memory, pids and cpu controllers enabled')
    folder = Path(tempfile.mkdtemp(prefix='job-', dir=base))
    try:
        for name, value in {'memory.max': '536870912', 'memory.swap.max': '0',
                            'memory.oom.group': '1', 'pids.max': '64',
                            'cpu.max': '100000 100000'}.items():
            (folder / name).write_text(value)
            if (folder / name).read_text().strip() != value:
                raise RuntimeError('Cgroup limit was not applied: ' + name)
        # If cgroup.kill is absent, descendant cleanup cannot be guaranteed.
        if not (folder / 'cgroup.kill').is_file():
            raise RuntimeError('cgroup.kill support is required')
        # Prove cleanup authority while the fresh job is still empty.
        (folder / 'cgroup.kill').write_text('1')
        yield folder
    finally:
        if (folder / 'cgroup.kill').is_file():
            (folder / 'cgroup.kill').write_text('1')
        deadline = time.monotonic() + 1
        while 'populated 1' in (folder / 'cgroup.events').read_text():
            if time.monotonic() >= deadline:
                raise RuntimeError('Cgroup cleanup did not complete')
            time.sleep(.01)
        folder.rmdir()


def _cpu_seconds(group):
    values = dict(line.split() for line in (group / 'cpu.stat').read_text().splitlines())
    return int(values['usage_usec']) / 1000000



def finish_job(group, proc):
    """Cgroup identity, not a potentially reused numeric PGID, owns cleanup."""
    try:
        (group / 'cgroup.kill').write_text('1')
        proc.wait(timeout=3)
    finally:
        proc.stdout.close()
        proc.stderr.close()


def run_isolated(directory, command, compile_job=False, run_command=None):
    """Run with bounded combined output; kill the complete job on every exit."""
    directory = Path(directory)
    (directory / 'limits.py').write_text(BOOTSTRAP, encoding='utf-8')
    (directory / 'driver.py').write_text(JOB_DRIVER, encoding='utf-8')
    if compile_job and run_command is None:
        raise ValueError('Compilation must share one isolated job with execution')
    (directory / 'job.json').write_text(json.dumps({
        'build': list(command) if compile_job else [],
        'run': list(run_command) if compile_job else list(command)}), encoding='utf-8')
    with _seccomp_file(False) as runtime_filter:
        (directory / 'runtime.bpf').write_bytes(runtime_filter.read())
    with job_cgroup() as group, _seccomp_file(compile_job) as seccomp:
        args = sandbox_command(directory, command, seccomp.fileno(), compile_job)
        # A trusted host launcher enters the delegated cgroup BEFORE bwrap
        # starts. No submitted text is evaluated in this launcher.
        launcher = [sys.executable, '-I', '-c',
                    "import os,sys; open(sys.argv[1], 'w').write(str(os.getpid())); os.execve(sys.argv[2], sys.argv[2:], {})",
                    str(group / 'cgroup.procs')] + args
        proc = subprocess.Popen(launcher, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env={}, close_fds=True,
                                pass_fds=(seccomp.fileno(),), start_new_session=True)
        buffers = {'out': bytearray(), 'error': bytearray()}
        failure = ''
        deadline = time.monotonic() + (15 if compile_job else 3)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ, 'out')
                selector.register(proc.stderr, selectors.EVENT_READ, 'error')
                while selector.get_map():
                    if _cpu_seconds(group) >= (10 if compile_job else 2):
                        failure = 'CPU time limit exceeded.'
                        break
                    if time.monotonic() >= deadline:
                        failure = 'Time limit exceeded.'
                        break
                    for key, _ in selector.select(min(.1, max(0, deadline-time.monotonic()))):
                        chunk = os.read(key.fd, 4096)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        remaining = OUTPUT_LIMIT - sum(map(len, buffers.values()))
                        buffers[key.data].extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            failure = 'Output limit exceeded.'
                            break
                    if failure:
                        break
                if not failure:
                    proc.wait(timeout=max(.001, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            failure = 'Time limit exceeded.'
        finally:
            finish_job(group, proc)
        out = buffers['out'].decode(errors='replace')
        error = buffers['error'].decode(errors='replace')
        if failure:
            error = (error[:2500] + '\n' + failure).strip()
        elif proc.returncode and not error:
            error = 'Execution stopped: resource limit or runtime error.'
        return {'out': out, 'error': error, 'returncode': proc.returncode}


PREFLIGHT_SCRIPT = "import errno, json, os, resource, socket\nfrom pathlib import Path\n\ndef require(condition, detail):\n    if not condition:\n        raise RuntimeError('Isolation self-check failed: ' + detail)\n\nfor name, host_namespace in HOST_NAMESPACES.items():\n    require(os.readlink('/proc/self/ns/' + name) != host_namespace, name + ' namespace was shared')\nfor path in PRIVATE_PATHS:\n    require(not os.path.exists(path), 'host path was visible: ' + path)\nunexpected_names = sorted(set(os.environ) - {'PATH', 'HOME', 'LANG', 'TMPDIR', 'LC_CTYPE'})\nrequire(not unexpected_names, 'unexpected environment variable names: ' + json.dumps(unexpected_names))\nrequire(os.environ.get('HOME') == '/tmp', 'unexpected HOME')\nrequire(os.environ.get('PATH') == '/usr/bin:/bin', 'unexpected executable search path')\nfor limit, value in ((resource.RLIMIT_AS, 2147483648), (resource.RLIMIT_NPROC, 64),\n                     (resource.RLIMIT_NOFILE, 64), (resource.RLIMIT_FSIZE, 8192),\n                     (resource.RLIMIT_CPU, 2), (resource.RLIMIT_CORE, 0)):\n    require(resource.getrlimit(limit) == (value, value), 'a hard resource limit is missing')\nfor operation in (lambda: socket.socket(), os.fork):\n    try:\n        result = operation()\n    except OSError as exc:\n        require(exc.errno == errno.EPERM, 'unexpected syscall-denial reason')\n    else:\n        if isinstance(result, int) and result == 0:\n            os._exit(1)\n        raise RuntimeError('Isolation self-check failed: socket or fork was permitted')\ntry:\n    with open('/input/readonly-canary', 'w') as stream:\n        stream.write('unexpected')\nexcept OSError as exc:\n    require(exc.errno in (errno.EROFS, errno.EACCES, errno.EPERM), 'unexpected read-only input error')\nelse:\n    raise RuntimeError('Isolation self-check failed: input mount was writable')\nwith open('/work/write-canary', 'w') as stream:\n    stream.write('disposable')\nrequire(Path('/input/readonly-canary').read_text() == 'unchanged', 'input canary changed')\nentry_names = json.loads(Path('/work/.environment-names.json').read_text())\nprint(json.dumps({'status': 'CODE_BREAKER_ISOLATION_READY', 'environment_names': entry_names}))\n"

@functools.lru_cache(maxsize=1)
def isolation_error():
    """A failed real probe disables ALL player execution, including compilation."""
    try:
        with tempfile.TemporaryDirectory(prefix='code-breaker-probe-') as folder:
            job = Path(folder)
            namespaces = {name: os.readlink('/proc/self/ns/' + name)
                          for name in ('net', 'mnt', 'pid', 'user', 'ipc', 'uts', 'cgroup')}
            private_paths = ['/home', '/root', '/run', '/sys', '/etc/passwd', '/etc/shadow',
                             str(Path(__file__).resolve().parent)]
            script = ('HOST_NAMESPACES = ' + repr(namespaces) + '\nPRIVATE_PATHS = '
                      + repr(private_paths) + '\n' + PREFLIGHT_SCRIPT)
            (job / 'selfcheck.py').write_text(script, encoding='utf-8')
            (job / 'readonly-canary').write_text('unchanged', encoding='utf-8')
            result = run_isolated(folder, ['/usr/bin/python3', '-I', '/work/selfcheck.py'])
        if result['returncode'] or result['error']:
            detail = result['error'].strip() or 'The real isolation self-check did not complete'
            return 'Execution disabled: isolation unavailable. ' + detail[:600]
        try:
            checked = json.loads(result['out'])
            names = checked['environment_names']
            if (checked['status'] != 'CODE_BREAKER_ISOLATION_READY'
                    or set(names) != {'received_names', 'removed_names'}
                    or any(not isinstance(names[key], list)
                           or any(not isinstance(name, str) for name in names[key])
                           for key in names)):
                raise ValueError('Invalid names-only self-check result')
        except (KeyError, TypeError, ValueError):
            return 'Execution disabled: isolation unavailable. The real isolation self-check did not complete'
        if names['removed_names']:
            print('Isolation sanitization removed environment variable names: '
                  + json.dumps(names['removed_names']), flush=True)
        return ''
    except Exception as exc:
        return f'Execution disabled: isolation unavailable ({type(exc).__name__}: {exc}).'
