"""Local Fedora entrypoint. Never escape a restricted agent environment.

A user-launched transient systemd scope delegates only its own cgroup subtree.
No sudo, sysctls, persistent units, global controller changes, or sandbox bypass.
"""
import argparse
import ctypes.util
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
CGROUP = Path('/sys/fs/cgroup')
CONTROLLERS = {'cpu', 'memory', 'pids'}


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as exc:
        return f'unavailable: {exc.strerror}'


def _capture(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return {'ok': result.returncode == 0, 'detail': (result.stdout + result.stderr).strip()[:1200]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'detail': str(exc)}


def environment_evidence():
    status = dict(line.split(':', 1) for line in _read('/proc/self/status').splitlines() if ':' in line)
    readonly = bool(os.statvfs(CGROUP).f_flag & os.ST_RDONLY) if CGROUP.exists() else True
    uid_map = _read('/proc/self/uid_map')
    fields = uid_map.split()
    initial_userns = fields == ['0', '0', '4294967295']
    return {'uid_map': uid_map, 'no_new_privileges': status.get('NoNewPrivs', '').strip(),
            'seccomp_mode': status.get('Seccomp', '').strip(), 'cgroup_read_only': readonly,
            'container_restrictions_detected': readonly and not initial_userns
                and status.get('Seccomp', '').strip() == '2'}


def namespace_probe():
    bwrap = shutil.which('bwrap')
    if not bwrap:
        return {'ok': False, 'detail': 'bubblewrap is not installed'}
    args = [bwrap, '--unshare-all', '--unshare-user', '--disable-userns',
            '--die-with-parent', '--cap-drop', 'ALL', '--clearenv', '--ro-bind', '/usr', '/usr']
    for name in ('lib', 'lib64', 'bin', 'sbin'):
        path = Path('/')/name
        if path.is_symlink():
            args += ['--symlink', os.readlink(path), str(path)]
        elif path.is_dir():
            args += ['--ro-bind', str(path), str(path)]
    args += ['--proc', '/proc', '--dev', '/dev', '--remount-ro', '/', '--', '/usr/bin/true']
    # Only the fixed, trusted true executable is used. No player text, files,
    # network connections, or personal data are involved in this diagnostic.
    return _capture(args)


def diagnose():
    evidence = environment_evidence()
    evidence['user_bus'] = _capture(['systemctl', '--user', 'show', '--property=Version', '--value'])
    if evidence['user_bus']['ok']:
        evidence['user_bus']['detail'] = 'User service manager is reachable'
    evidence['namespaces'] = namespace_probe()
    evidence['tools'] = {name: shutil.which(name) for name in ('bwrap', 'systemd-run', 'g++', 'java')}
    evidence['libseccomp'] = ctypes.util.find_library('seccomp')
    evidence['python_dependencies'] = {name: importlib.util.find_spec(name) is not None
                                       for name in ('pygame', 'pygame_gui')}
    from runner import cpp_build_command
    try:
        cpp_build_command(evidence['tools']['g++'] or '/usr/bin/g++')
        evidence['cpp_linker'] = {'ok':True, 'detail':'ld.bfd is executable within /usr/bin; no alternatives mount is needed'}
    except RuntimeError as exc:
        evidence['cpp_linker'] = {'ok':False, 'detail':str(exc)}
    evidence['java_compiler'] = _capture(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-version'])
    evidence['local_session_ready'] = (not evidence['container_restrictions_detected']
        and not evidence['cgroup_read_only'] and evidence['namespaces']['ok']
        and evidence['user_bus']['ok'] and all(evidence['tools'].values())
        and bool(evidence['libseccomp']) and all(evidence['python_dependencies'].values())
        and evidence['java_compiler']['ok'] and evidence['cpp_linker']['ok'])
    return evidence


def current_cgroup():
    for line in _read('/proc/self/cgroup').splitlines():
        if line.startswith('0::'):
            group = (CGROUP / line[3:].lstrip('/')).resolve()
            if group != CGROUP and CGROUP in group.parents:
                return group
    raise RuntimeError('Cannot locate a non-root cgroup v2 scope')


def authenticate_delegation(group):
    """Use the user manager's authoritative properties, not optional xattrs."""
    if not re.fullmatch(r'code-breaker-[0-9a-f]{32}\.scope', group.name):
        raise RuntimeError('Run through local.sh; refusing to manage an unrelated cgroup')
    properties = ('Id', 'ControlGroup', 'Delegate', 'DelegateControllers', 'Transient',
                  'ActiveState', 'MemoryMax', 'MemorySwapMax', 'TasksMax')
    result = _capture(['systemctl', '--user', 'show', '--no-pager',
                       '--property=' + ','.join(properties), group.name])
    if not result['ok']:
        raise RuntimeError('Cannot authenticate delegation with the user manager: ' + result['detail'])
    values = {}
    for line in result['detail'].splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key in values:
                raise RuntimeError('Ambiguous systemd delegation properties')
            values[key] = value
    if (values.get('Id') != group.name or values.get('Delegate') != 'yes'
            or values.get('Transient') != 'yes' or values.get('ActiveState') != 'active'):
        raise RuntimeError('The exact active transient game scope has not been delegated by systemd')
    control_group = values.get('ControlGroup', '')
    if not control_group.startswith('/') or '..' in Path(control_group).parts:
        raise RuntimeError('Invalid systemd cgroup path')
    if (CGROUP / control_group.lstrip('/')).resolve() != group:
        raise RuntimeError('Systemd cgroup does not match the current game process')
    if not CONTROLLERS <= set(values.get('DelegateControllers', '').split()):
        raise RuntimeError('Systemd did not delegate all required controllers')
    for name, ceiling in (('MemoryMax', 1024**3), ('MemorySwapMax', 0), ('TasksMax', 128)):
        try:
            value = int(values[name])
        except (KeyError, ValueError):
            raise RuntimeError('Missing or unlimited systemd scope limit: ' + name) from None
        if value < 0 or value > ceiling or (value == 0 and name != 'MemorySwapMax'):
            raise RuntimeError('Unexpected systemd scope limit: ' + name)


def prepare_delegation():
    """Manage ONLY the subtree delegated to this newly created game scope."""
    group = current_cgroup()
    authenticate_delegation(group)
    if not CONTROLLERS <= set((group/'cgroup.controllers').read_text().split()):
        raise RuntimeError('User scope lacks cpu/memory/pids delegation; no host policy was changed')
    members = (group/'cgroup.procs').read_text().split()
    if members != [str(os.getpid())]:
        raise RuntimeError('Game scope contains other processes; refusing to move them')
    supervisor = group/'supervisor'
    supervisor.mkdir()
    (supervisor/'cgroup.procs').write_text(str(os.getpid()))
    if (group/'cgroup.procs').read_text().strip():
        raise RuntimeError('Scope is not empty after moving the game supervisor')
    # These are delegated unit-local settings, not global kernel/system settings.
    settings = ' '.join('+' + name for name in sorted(CONTROLLERS))
    (group/'cgroup.subtree_control').write_text(settings)
    jobs = group/'jobs'
    jobs.mkdir()
    (jobs/'cgroup.subtree_control').write_text(settings)
    if not CONTROLLERS <= set((jobs/'cgroup.subtree_control').read_text().split()):
        raise RuntimeError('Could not enable all required controllers in the game subtree')
    os.environ['CODE_BREAKER_CGROUP_ROOT'] = str(jobs)
    return jobs


def scope_command(action):
    return ['systemd-run', '--user', '--scope', '--collect', '--quiet',
            '--unit=code-breaker-' + uuid.uuid4().hex + '.scope',
            '--property=Delegate=cpu memory pids', '--property=MemoryMax=1G',
            '--property=MemorySwapMax=0', '--property=TasksMax=128',
            '--', sys.executable, str(Path(__file__).resolve()), '_session', action]


def session(action):
    if os.geteuid() == 0:
        raise RuntimeError('Run as your desktop user, not root')
    jobs = prepare_delegation()
    from execution_isolation import isolation_error
    isolation_error.cache_clear()
    error = isolation_error()
    if error:
        raise RuntimeError(error)
    print('Protected execution ready; delegated job subtree:', jobs, flush=True)
    if action == 'play':
        command = [sys.executable, str(ROOT/'main.py')]
    elif action == 'verify':
        command = [sys.executable, '-u', str(ROOT/'verify_playability.py')]
    else:
        os.environ['PYTHON'] = sys.executable
        command = ['bash', str(ROOT/'test_all.sh')]
    os.chdir(ROOT)
    os.execvp(command[0], command)


def setup_report(status, detail):
    # Replace old successful reports before a new verification attempt, so a
    # failed launch cannot leave a stale 'passed' report looking current.
    from verification_report import write_report
    write_report(ROOT, {'status': status, 'flows': [], 'detail': detail})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['doctor', 'play', 'verify', 'test', '_session'])
    parser.add_argument('session_action', nargs='?', choices=['play', 'verify', 'test'])
    args = parser.parse_args()
    try:
        if args.action == 'verify':
            setup_report('pending', 'Local protected setup has not completed')
        if args.action == '_session':
            if not args.session_action:
                parser.error('Missing session action')
            session(args.session_action)
        else:
            evidence = diagnose()
            if args.action == 'doctor':
                print(json.dumps(evidence, indent=2))
                return 0 if evidence['local_session_ready'] else 2
            if not evidence['local_session_ready']:
                if args.action == 'verify':
                    setup_report('blocked', 'Local host diagnostics did not pass; run bash local.sh doctor')
                print(json.dumps(evidence, indent=2))
                print('Launch blocked. Run these commands in your normal Fedora terminal, outside Codex. '
                      'See LOCAL_SETUP.md. Protections remain enabled.', file=sys.stderr)
                return 2
            os.execvp('systemd-run', scope_command(args.action))
    except (OSError, RuntimeError) as exc:
        if args.action == 'verify' or (args.action == '_session' and args.session_action == 'verify'):
            try:
                setup_report('blocked', str(exc))
            except OSError:
                pass
        print('Protected setup failed: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
