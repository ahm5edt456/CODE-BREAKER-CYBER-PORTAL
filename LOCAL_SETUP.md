# Play locally on Fedora with isolation enabled

Run the commands below in your normal Fedora desktop terminal, **outside the
Codex execution environment**, as `alahmed`. Do not use `sudo` to launch the game.

## 1. Diagnose the actual host

```bash
cd /home/alahmed/CODE_BREAKER_CAMPAIGN/CODE_BREAKER_IEEE
bash local.sh doctor
```

This read-only diagnostic checks namespace creation with a fixed `/usr/bin/true`
command, user-service bus availability, cgroup mount permissions, toolchains,
libseccomp, and Python dependencies. It prints selected security metadata, not
shell environment variables or personal files. `local_session_ready: true`
means the launcher can attempt a protected local session; it does not substitute
for the full isolation probe or real Run/Submit verification.

The Codex process observed here has a remapped user namespace, active seccomp,
`NoNewPrivs=1`, a read-only cgroup mount, and a denied user bus. Its namespace
probe fails with `Failed to create NETLINK_ROUTE socket: Operation not permitted`.
These observations establish restrictions in **Codex's current execution
context**, not a restriction on your normal Fedora session. Only running this
same diagnostic in that normal session determines the host's capabilities.
The launcher refuses to use the user bus to escape a restricted agent context.

If the diagnostic reports missing `pygame` or `pygame_gui`, create the existing
project-local virtual environment:

```bash
bash setup.sh
bash local.sh doctor
```

The setup installs Python dependencies into `.venv_portal`; it does not change
security settings. Bubblewrap, libseccomp, g++, and OpenJDK's actual compiler
module were already present in the inspected environment. The local javac
launcher uses that installed compiler; no replacement compilation results exist.

### Fedora linker prerequisite

Fedora's `/usr/bin/ld` may be a symlink through `/etc/alternatives/ld`, which is
intentionally hidden inside the sandbox. The runner explicitly selects the
installed BFD linker (`-fuse-ld=bfd`) and checks `/usr/bin/ld.bfd`; it does not
mount `/etc/alternatives` or expose other host directories. `doctor` reports this
as `cpp_linker`. On the inspected host, Fedora's `binutils` package and the real
executable were already installed, so no package installation is needed.

After this fix, run `bash local.sh verify` again to check all Python, C++ and Java
Run/Submit modes. Toolchain planning/unit checks inside Codex do not establish
successful native compilation in the protected local session.

## 2. Verify real game execution

```bash
bash local.sh verify
```

The launcher requests a **new transient user scope** with `Delegate=cpu memory
pids`. It creates a supervisor leaf, enables controllers only in that delegated
scope, and supplies a private jobs subtree to the existing isolation backend.
Before modifying the delegation it queries the user manager and matches the
exact active transient unit, cgroup path, delegated controllers and resource
ceilings. A missing `user.delegate` xattr is supported; a denied/mismatched
manager result fails closed. It never writes sysctls, system units, `/etc`, SELinux settings, shell startup
files, or another application's cgroups. No persistent unit is installed.

The scope has a 1 GiB total memory ceiling, no swap, and a 128-task ceiling.
Each player job retains all existing stricter limits, including 512 MiB aggregate
memory, 64 tasks, no network, no personal/project files, and bounded time/output.
Preflight may print `Isolation sanitization removed environment variable names`
followed by a JSON list such as `["PWD"]`. Bubblewrap creates that variable even
with `--clearenv`; the driver removes it before compilation/execution. Diagnostics
list names only. Do not paste environment values or run `env`/`printenv` to debug.
The fixed compiler/program environment and strict self-check remain enabled.

The real isolation self-check must verify separate namespaces, hidden host
paths, denied network/process syscalls, read-only inputs and hard limits before
the verifier or game starts.
Source restrictions and fail-closed behavior remain enabled.

The verifier opens an actual campaign challenge for **Python, C++, and Java** in
Debug, Complete Code, and Predict Output modes. It generates reference output,
uses the actual `run_code(False)` and `run_code(True)` flow, checks correct output,
checks that Run does not change lives or open a gate, and checks that Submit
opens the gate and awards points. Predict Output's Run retains its original
notification behavior; its Submit checks the chosen reference output. Native
answers end with a trailing comment to exercise wrapper boundaries.

Tests use a temporary player-data directory and never save test player results.
`local-verification.json` is atomically replaced without following symlinks;
verification checks remain active under Python optimization. It records passed
flows, errors/blocks, and whether the
real saved-data checksums remained unchanged. **Only `status: passed` verifies
playability.** A blocked report is not a language-test pass.

For the complete security, language, gameplay and persistence suites:

```bash
bash local.sh test
```

Both the scope and its cgroups are transient. They are cleaned up on exit. If a
scope is unexpectedly left running, find only the game's scopes and stop the
specific name displayed (replace the example with the actual name):

```bash
systemctl --user list-units 'code-breaker-*.scope'
systemctl --user stop code-breaker-ACTUAL_NAME.scope
```

## 3. Play

```bash
bash start.sh
```

`start.sh` now uses the same delegated local launcher and real isolation probe.
The GUI inherits your desktop display/audio session; player processes get their
separate cleared environment and restricted filesystem. Normal game saves still
use the existing `data` directory. Question generation and difficulty are unchanged.

## If local setup is blocked

- A read-only cgroup mount or denied user bus in Codex: use your normal desktop
  terminal. The script intentionally cannot obtain execution outside Codex.
- Missing controllers, delegation permission errors, or a host namespace denial:
  keep the diagnostic/error output. The launcher stops instead of bypassing a
  requirement. A local host check is needed before deciding on another supported
  isolated worker or VM; do not disable SELinux, seccomp, or namespace restrictions.
- Run/Submit or compilation failures after setup: inspect
  `local-verification.json` and the printed error. The protected path has not
  been fully verified from Codex, so a successful local test is still required.

The delegation design follows systemd's [Control Group APIs and Delegation](https://github.com/systemd/systemd/blob/main/docs/CGROUP_DELEGATION.md)
and the transient user scope behavior in [systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html).
