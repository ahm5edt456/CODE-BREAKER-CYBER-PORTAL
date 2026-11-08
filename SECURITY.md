# Player execution security

The runner's Python AST checks, builtin allowlist, and C++/Java event-mode
substring restrictions have been restored. These are **not a secure sandbox**.
They deliberately reject imports, Python attribute access, filesystem/process
APIs, player-supplied C++ includes, and other operations outside event mode.
The reference solutions for all 13 question types pass these checks in every
language. Question generation, tier progression, history, and saved scores are
independent of execution isolation.

## Mandatory OS isolation

`runner.execute()` requires a successful real isolation probe before compiling
or executing any submitted or reference code. It never falls back to direct host
execution. The former `--worker` and `--native` host entrypoints are disabled.
This implementation supports non-root x86_64 Linux with bubblewrap, libseccomp,
a systemd-delegated cgroup v2 directory with memory/pids/cpu controllers,
and permission to create the required user, mount, PID, IPC, UTS, cgroup and
network namespaces. The local launcher authenticates its exact active transient
unit through read-only systemd properties (Id, ControlGroup, Delegate,
DelegateControllers, Transient, ActiveState and scope resource ceilings). The
optional `user.delegate` xattr is not required or accepted as sole authority.
`CODE_BREAKER_CGROUP_ROOT` is only a path hint: the runner requires its jobs
subtree to be a sibling of the current supervisor in that exact game scope.
It does not change host security settings.

`execution_isolation.py` provides the following additional boundaries:

- A private filesystem root; only read-only system toolchains/libraries, a few
  named public JDK configuration files, and generated read-only job inputs are
  mounted. Home directories, project files, saved scores, host `/tmp`, and the
  rest of `/etc` are absent. The root is read-only. `/proc` describes the private
  PID namespace. No host environment variables or ambient file descriptors are
  passed to the job.
- A new network namespace plus a seccomp filter denying socket creation and
  network syscalls, including Unix sockets. Additional filters deny namespace,
  tracing, kernel-management, and other sensitive syscalls.
- Compilation and execution share one disposable namespace. Source, binaries,
  and classes stay in a 64 MiB tmpfs; `/tmp` is another 16 MiB tmpfs. Player code
  cannot write back to the project or its host-side input directory.
- Aggregate job cgroup limits: 512 MiB resident/charged memory including tmpfs,
  no swap, 64 total tasks/threads, and a one-CPU bandwidth quota. A trusted
  launcher joins this cgroup before bubblewrap starts. CPU usage is monitored
  across the entire job (10 seconds for compile/run, 2 seconds for interpreted
  execution). Cgroup kill removes every remaining task during cleanup.
- Per-process hard limits: 2 GiB virtual address space, 64 processes/threads for
  the non-root UID, 64 file descriptors, no core dumps, and 8 KiB files during
  execution (32 MiB during compilation). JVM heap is additionally capped at
  64 MiB, with bounded stacks/metaspace/code cache and two active processors.
- CPU limits: 8 seconds for each compiler process and 2 seconds for the player
  process. Wall-clock limits: 15 seconds for compilation plus execution, or
  3 seconds for interpreted execution. Combined stdout/stderr is capped at
  8 KiB while being read, rather than captured without bounds then truncated.
- Player execution cannot fork child processes. Filtered `clone` permits threads
  without new namespaces for the JVM; `clone3` falls back to filtered `clone`.
  Compilers may spawn bounded toolchain processes. Java annotation processing
  is disabled. Only the job's cgroup is killed on completion/failure; cleanup
  never signals a numeric process-group ID that could have been reused. Waits
  are bounded, and PID namespace teardown is another cleanup boundary.

On this Fedora system `/usr/bin/ld` points through `/etc/alternatives/ld`.
The sandbox deliberately does not expose that alternatives directory. C++ builds
select the already installed `/usr/bin/ld.bfd` using GCC's `-fuse-ld=bfd` option.
The helper checks that the resolved tool is executable within `/usr/bin`;
missing or external targets fail with an explicit toolchain error. This adds no
mounts, host search paths, environment variables, or filesystem access. The
assembler and linker are supplied by the existing read-only `/usr` mount and
fixed `/usr/bin:/bin` path. The local diagnostic also checks this prerequisite.

Before any challenge code runs, a fixed trusted self-check inside the full
backend verifies distinct network/mount/PID/user/IPC/UTS/cgroup namespaces,
hidden home/project/host paths, a cleared environment, denied sockets/fork,
read-only input and writable disposable storage, and hard resource limits.
Every job limit is read back from cgroupfs; cgroup kill permission is tested
while the fresh job is empty. A missing or failed check disables execution.

Bubblewrap recreates `PWD` after `--clearenv`; it is not a permitted player
variable. The trusted driver records **variable names only** in its disposable
work directory, clears its environment, and passes a fresh fixed mapping of
`PATH`, `HOME`, `LANG` and `TMPDIR` to both compiler and execution wrappers.
The final compiler/program `execve` again uses that exact mapping. No inherited
values, including locale, Python, JVM, loader or credential variables, are copied.
The host-side cgroup launcher also uses an explicit empty environment when
executing Bubblewrap. The self-check's existing narrow allowlist is unchanged;
Python's possible `LC_CTYPE` locale-coercion variable remains the sole optional
name. Unexpected names at the self-check cause failure with **names only** in
the error, never their values. A successful preflight prints the names removed
at sandbox entry, so host-specific additions can be diagnosed without exposing
secrets. The entry snapshot is diagnostic metadata, not authorization or a
replacement for the final environment self-check.

Verification reports use explicit checks even under Python optimization. They
are replaced atomically with mode 0600 and never written through an existing
report-file symlink, protecting saved results from accidental link targets.
The regression launcher removes inherited Python optimization settings.

## Local Fedora setup

Use `bash local.sh doctor` in the normal desktop terminal to distinguish host
capabilities from a restricted agent container. `bash local.sh verify`,
`bash local.sh test`, and `bash start.sh` request a transient delegated user
scope and prepare controllers only inside that scope. They do not alter host
security policy or bypass the namespace/cgroup requirements. See
[LOCAL_SETUP.md](LOCAL_SETUP.md) for exact commands, isolation requirements and
verification-report semantics. The game does not require a permanent cgroup at
`/sys/fs/cgroup/code-breaker`; the launcher supplies its private jobs subtree.

## Confirmed local playability

The actual local Fedora report at `2026-11-08T17:55:48.508044+00:00` records
`status: passed` for all nine Python/C++/Java × Debug/Complete Code/Predict Output
reference, Run and Submit flows, with saved player data unchanged. See
[VALIDATION.md](VALIDATION.md) and `local-verification.json` for scope and evidence.
This local smoke verification does not imply that all regression or adversarial
integration tests have passed, or replace an independent security audit.

## Verification and limitations in this workspace

Run `bash test_all.sh`. It runs the security tests first and refuses to continue
with language execution tests when the real isolation probe fails. There is no
flag to bypass that requirement. The local `tools/bin/javac` launcher invokes
the genuine compiler module already installed with OpenJDK 25.0.4.1; it does not
substitute compilation results.

The current environment has no delegated cgroup, so the real runner preflight
reports `A delegated cgroup v2 directory is required`. A separate minimal
bubblewrap namespace probe also reports:

```
bwrap: loopback: Failed to create NETLINK_ROUTE socket: Operation not permitted
```

Therefore Python, C++, and Java compilation/execution are disabled. Security
checks verify that all three fail closed, the old restrictions are active, old
host execution entrypoints are rejected, the syscall filter denies sockets and
fork in a small trusted helper, and question progression/rotation survive.
Filesystem isolation, resource exhaustion inside namespaces, and successful
language execution **have not been verified here**. The integration test for
those checks is explicitly skipped; language regressions are blocked, not passed.

This backend has not received an independent security audit. Namespaces and
seccomp share the host kernel; they are not a VM. The backend and its cgroup integration cannot be fully
verified in this environment. For hostile public submissions, use a separately
administered worker/VM with minimal runtime images and an independently audited
policy. Do not relax the fail-closed
behavior, host namespace policy, or source protections to make tests pass.
