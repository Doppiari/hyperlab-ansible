#!/usr/bin/python3 -I
"""Provision one created and projected Machine inside its operation terminal.

The operation runner starts this as the reviewed command of
machine.provision, with the Machine's name as its only argument; by hand,
`--from N` resumes a failed or interrupted run at step N. The steps
come from `hyperlabctl machine provision-steps` in the reviewed checkout,
which refuses a Machine whose generated spec is not its record's
projection. Every step must have the reviewed shape that the Machine
record's own Template calls for, and every playbook must be a regular file
in the checkout's playbooks directory, before the first step runs. Each -K playbook asks for the become password in this terminal. A
workstation password is asked here without echo, turned into a SHA-512
crypt hash, written to a private runtime file for the first profile pass and
deleted in every outcome, SIGINT, SIGTERM and SIGHUP included (ADR 0017).

Every run that starts its steps leaves, below
$XDG_STATE_HOME/hyperlab/provisioning/, a receipt (NAME.json: each step's
result, then finished, failed or interrupted) and the whole output of its
steps (NAME.log, the previous one kept as NAME.log.1), while it holds
NAME.lock. Only a run whose every step ended with 0 writes "finished";
`hyperlabctl machine show` and the Machines view read anything else as
incomplete. A workstation's last step proves the result: sudo asks for the
password and, for VFIO Linux Looking Glass, the sender reaches capture.
"""
from __future__ import annotations

import contextlib
import fcntl
import getpass
import json
import os
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CLI = "/usr/local/bin/hyperlabctl"
ANSIBLE = "/usr/bin/ansible-playbook"
OPENSSL = "/usr/bin/openssl"
POINTER = Path("/etc/hyperlabctl/checkout")
MACHINE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
HASH_RE = re.compile(r"^\$6\$[^$]{1,16}\$[./A-Za-z0-9]{86}$")
KEY_RE = re.compile(r"^ssh-ed25519 AAAAC3NzaC1lZDI1NTE5[A-Za-z0-9+/]+={0,2}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
FROM_RE = re.compile(r"^[1-9][0-9]?$")
HOST_PLAYBOOKS = {"create-domain": "playbooks/vm-create.yml",
                  "inventory": "playbooks/vm-guest-inventory.yml"}
CLOSE_PLAYBOOK = "playbooks/guest-close-access.yml"
# The profile playbook of each workstation Template, as hyperlabctl maps
# them (PROFILE_PLAYBOOKS in machine_provision.py); a contract keeps both
# equal. A Template in the server workspace has no profile.
PROFILE_PLAYBOOKS = {
    "workstation-dev": "playbooks/guest-arch-dev-vfio.yml",
    "workstation-dev-standard": "playbooks/guest-arch-dev.yml",
    "gaming-clean": "playbooks/guest-arch-gaming-clean.yml",
    "gaming-dirty": "playbooks/guest-arch-gaming-dirty.yml",
}
SERVER_WORKSPACE = "server"
ACCESS_FILE = "{access_file}"
# A server has no profile and ends by closing its provisioning access. A
# workstation then proves it: `hyperlabctl machine verify-provisioning`.
SERVER_STEPS = ["create-domain", "inventory", "close-access"]
WORKSTATION_STEPS = ["create-domain", "inventory", "profile-first", "profile-second", "close-access",
                     "verify"]
# Receipts, logs and locks, below the state home hyperlabctl's registry uses
# ($XDG_STATE_HOME, else ~/.local/state); a contract keeps the two equal.
# None follows the environment.
STATE_HOME: Path | None = None
RECEIPTS = ("hyperlab", "provisioning")
RECEIPT_SCHEMA = 1
# The log keeps every byte of the steps' output up to this size.
LOG_LIMIT = 32 << 20
PASSWORD_MIN = 8
# Seconds a cancelled playbook gets to end before it is killed. The runner
# waits longer for this program (PROVISION_STOP_GRACE there), so the hash
# file is removed before anything can kill the provisioner.
PLAYBOOK_GRACE = 10
# Signals that end the run; the hash file is never left behind by them.
CANCELLING = (signal.SIGTERM, signal.SIGHUP)


class Refused(ValueError):
    pass


class Cancelled(BaseException):
    """SIGTERM or SIGHUP: the unit is stopped or the terminal is gone."""

    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


class Stop:
    """The first ending signal, the only one that ends the run.

    A stopped runner sends more than one: its PTY hangs up, then it
    terminates this program, and systemd may signal the whole unit. A later
    one must not cut short the cleanup that the first started.
    """

    def __init__(self) -> None:
        self.signum: int | None = None
        self.deferring = False

    def handle(self, signum: int, frame: object) -> None:
        if self.signum is not None:
            return
        self.signum = signum
        if not self.deferring:
            self.end()

    def end(self) -> None:
        if self.signum == signal.SIGINT:
            raise KeyboardInterrupt
        raise Cancelled(self.signum)

    @contextlib.contextmanager
    def deferred(self):
        """Note an ending signal that arrives inside, and raise it only once
        the block is over. No signal is blocked, so a playbook started
        inside inherits no mask and still ends on its own signals."""
        self.deferring = True
        try:
            yield
        finally:
            self.deferring = False
            if self.signum is not None:
                self.end()


STOP = Stop()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Refused(reason)


@contextlib.contextmanager
def held():
    """Defer the ending signals while a hash file is created or removed."""
    blocked = {signal.SIGINT, *CANCELLING}
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def checkout() -> Path:
    repo = Path(POINTER.read_text(encoding="utf-8").strip())
    require(repo.is_absolute() and repo.is_dir(), "invalid HyperLab checkout")
    return repo.resolve()


def runtime_dir() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    info = runtime.lstat()
    require(runtime.is_absolute() and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700, "unsafe runtime directory")
    return runtime


def private_dir(runtime: Path) -> Path:
    path = runtime
    for name in ("hyperlab", "provision"):
        path = path / name
        with contextlib.suppress(FileExistsError):
            path.mkdir(mode=0o700)
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o700, "unsafe provisioning directory")
    return path


def reviewed_argv(step_id: str, profile: str | None, spec: str, inventory: str,
                  machine: str) -> list[str] | None:
    """The one argv a step may have, except the create step's key argument."""
    if step_id in HOST_PLAYBOOKS:
        argv = ["ansible-playbook", HOST_PLAYBOOKS[step_id], "-K", "-e", f"guest_spec={spec}"]
        if step_id == "create-domain":
            argv += ["-e", "guest_start_after_create=true", "-e"]
        return argv
    guest = ["ansible-playbook", "-i", "inventory.ini", "-i", inventory]
    if step_id == "close-access":
        return [*guest, CLOSE_PLAYBOOK]
    if profile is None:
        return None
    if step_id == "verify":
        return ["hyperlabctl", "machine", "verify-provisioning", machine]
    if step_id == "profile-first":
        return [*guest, profile, "-e", "@" + ACCESS_FILE]
    return [*guest, profile]


def guest_key_argument(value: str) -> bool:
    """The create step's last argument: exactly one guest public key."""
    try:
        document = json.loads(value)
    except ValueError:
        return False
    keys = document.get("guest_cloud_init_ssh_public_keys") if isinstance(document, dict) else None
    return (set(document) == {"guest_cloud_init_ssh_public_keys"} and isinstance(keys, list)
            and len(keys) == 1 and isinstance(keys[0], str) and KEY_RE.fullmatch(keys[0]) is not None)


def valid_step(step: object, step_id: str, profile: str | None, spec: str, inventory: str,
               machine: str) -> dict:
    require(isinstance(step, dict) and set(step) == {"id", "label", "password", "argv"}
            and step["id"] == step_id and isinstance(step["label"], str)
            and step["password"] is (step_id == "profile-first"), "invalid provisioning step")
    argv = step["argv"]
    require(isinstance(argv, list) and all(isinstance(part, str) and part
                                           and not any(ord(c) < 32 for c in part) for part in argv),
            "invalid provisioning command")
    expected = reviewed_argv(step_id, profile, spec, inventory, machine)
    require(expected is not None, "unreviewed profile playbook in a provisioning step")
    if step_id == "create-domain":
        require(len(argv) == len(expected) + 1 and argv[:-1] == expected and guest_key_argument(argv[-1]),
                "the create-domain step is not the reviewed command")
    else:
        require(argv == expected, f"the {step_id} step is not the reviewed command")
    return step


def playbook(step: dict) -> str:
    return next(part for part in step["argv"][1:] if part.startswith("playbooks/"))


def playbook_file(repo: Path, relative: str) -> None:
    """An existing regular file directly in the checkout's real playbooks/."""
    directory, name = relative.split("/")
    info = (repo / directory).lstat()
    require(stat.S_ISDIR(info.st_mode), f"{directory}/ is not a real directory in the checkout")
    try:
        info = (repo / directory / name).lstat()
    except FileNotFoundError:
        raise Refused(f"{relative} is missing from the checkout") from None
    require(stat.S_ISREG(info.st_mode), f"{relative} is not a regular file")


def cli_json(repo: Path, *args: str, unavailable: str) -> object:
    result = subprocess.run([CLI, "--repo", str(repo), *args],
                            capture_output=True, text=True, timeout=60, check=False)
    require(result.returncode == 0, (result.stderr.strip() or unavailable)[:400])
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise Refused(unavailable) from None


def machine_record(repo: Path, machine: str) -> tuple[str | None, dict]:
    """The profile playbook the Machine record's Template maps to (None for
    a server) and what hyperlabctl reads of its provisioning, with the
    record's digest; read from the registry before anything runs or is asked."""
    record = cli_json(repo, "machine", "show", machine, unavailable="the Machine record is unavailable")
    template = record.get("template") if isinstance(record, dict) else None
    presentation = record.get("presentation") if isinstance(record, dict) else None
    provisioning = record.get("provisioning") if isinstance(record, dict) else None
    require(isinstance(record, dict) and record.get("id") == machine
            and isinstance(template, dict) and isinstance(template.get("id"), str)
            and isinstance(presentation, dict) and isinstance(presentation.get("workspace_profile"), str),
            "invalid Machine record")
    require(isinstance(provisioning, dict) and isinstance(provisioning.get("record_sha256"), str)
            and DIGEST_RE.fullmatch(provisioning["record_sha256"]) is not None,
            "the Machine record's digest is unavailable")
    if presentation["workspace_profile"] == SERVER_WORKSPACE:
        return None, provisioning
    profile = PROFILE_PLAYBOOKS.get(template["id"])
    require(profile is not None, "no reviewed profile playbook for this Template")
    return profile, provisioning


def steps_for(repo: Path, machine: str, spec: str, runtime: Path, profile: str | None) -> list[dict]:
    """The whole plan, validated before anything runs or is asked. The
    record, not the plan, says which profile both passes run."""
    plan = cli_json(repo, "machine", "provision-steps", machine, unavailable="provisioning steps unavailable")
    require(isinstance(plan, dict) and plan.get("schema") == 1 and plan.get("machine") == machine
            and plan.get("spec") == spec and isinstance(plan.get("steps"), list), "invalid provisioning plan")
    ids = [step.get("id") if isinstance(step, dict) else None for step in plan["steps"]]
    require(ids == (SERVER_STEPS if profile is None else WORKSTATION_STEPS),
            "the provisioning steps are not the ones the Machine's Template calls for")
    inventory = str(runtime / f"{machine}.ini")
    steps = [valid_step(step, step_id, profile, spec, inventory, machine)
             for step, step_id in zip(plan["steps"], ids, strict=True)]
    for step in steps:
        if step["argv"][0] == "ansible-playbook":
            playbook_file(repo, playbook(step))
    return steps


def resumable(provisioning: object, steps: list[dict], first: int) -> None:
    """`--from N` continues a receipt hyperlabctl read as failed or
    interrupted for these very steps, at or before its first unfinished one."""
    require(isinstance(provisioning, dict) and provisioning.get("status") == "incomplete"
            and provisioning.get("receipt") in ("failed", "interrupted"),
            "only a failed or interrupted provisioning can be resumed; "
            "run without --from to provision from the first step")
    require(provisioning.get("step_ids") == [step["id"] for step in steps],
            "the receipt's steps are not this Machine's plan")
    unfinished = provisioning.get("step")
    require(isinstance(unfinished, int) and not isinstance(unfinished, bool)
            and 1 <= first <= unfinished <= len(steps),
            f"step {first} cannot be resumed: step {unfinished} has not ended with 0")


def state_dir() -> Path:
    """$XDG_STATE_HOME/hyperlab/provisioning, private to this user."""
    if STATE_HOME is not None:
        state = STATE_HOME
    else:
        configured = os.environ.get("XDG_STATE_HOME")
        state = Path(configured) if configured else Path.home() / ".local" / "state"
    require(state.is_absolute(), "the state home must be absolute")
    path = state
    for index, name in enumerate((None, *RECEIPTS)):
        if name is not None:
            path = path / name
        with contextlib.suppress(FileExistsError):
            path.mkdir(mode=0o700, parents=index == 0)
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and (name != RECEIPTS[-1] or stat.S_IMODE(info.st_mode) == 0o700),
                f"unsafe provisioning state directory {path}")
    return path


@contextlib.contextmanager
def run_lock(directory: Path, machine: str):
    """One provisioning of a Machine at a time; held for the whole run, so
    a reader can tell a live run from one that was killed."""
    fd = os.open(directory / f"{machine}.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, "unsafe provisioning lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused(f"another provisioning of {machine} is running") from None
        yield
    finally:
        os.close(fd)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Receipt:
    """What this run did, replaced atomically after every change."""

    def __init__(self, directory: Path, machine: str, digest: str, steps: list[dict], first: int) -> None:
        self.path = directory / f"{machine}.json"
        self.ended = False
        self.document = {
            "schema": RECEIPT_SCHEMA, "machine": machine, "record_sha256": digest, "state": "running",
            "started_at": utc_now(), "ended_at": None, "from_step": first, "reason": "",
            # Steps before `first` ended with 0 in the run this one resumes.
            "steps": [{"id": step["id"], "label": step["label"],
                       "result": "ok" if number < first else "pending",
                       "exit": 0 if number < first else None}
                      for number, step in enumerate(steps, 1)],
        }

    def step(self, number: int, result: str, code: int | None = None) -> None:
        self.document["steps"][number - 1].update(result=result, exit=code)

    def end(self, state: str, reason: str = "") -> None:
        self.document.update(state=state, ended_at=utc_now(), reason=reason[:1000])
        self.ended = True

    def stop(self, number: int, state: str, reason: str) -> None:
        """End a run cut short at step `number`, unless it already ended."""
        if self.ended:
            return
        if self.document["steps"][number - 1]["result"] in ("pending", "running"):
            self.step(number, "interrupted" if state == "interrupted" else "failed")
        self.end(state, reason)
        self.write()

    def write(self) -> None:
        data = (json.dumps(self.document, indent=2) + "\n").encode()
        with held():
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.stem}.",
                                             suffix=".tmp")
            try:
                try:
                    view = memoryview(data)
                    while view:
                        view = view[os.write(fd, view):]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(temporary, self.path)
            except BaseException:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temporary)
                raise
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)


class Log:
    """The terminal, and the same bytes in NAME.log. Prompts never pass
    here: getpass and the become prompt use the terminal directly."""

    def __init__(self, directory: Path, machine: str) -> None:
        self.path = directory / f"{machine}.log"
        with contextlib.suppress(FileNotFoundError):
            require(stat.S_ISREG(self.path.lstat().st_mode), "unsafe provisioning log")
            os.replace(self.path, directory / f"{machine}.log.1")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.stream = os.fdopen(fd, "wb", buffering=0)
        self.size = 0

    def write(self, data: bytes) -> None:
        # A terminal that hung up does not stop the run or its record.
        with contextlib.suppress(OSError, ValueError):
            terminal = getattr(sys.stdout, "buffer", None)
            if terminal is not None:
                terminal.write(data)
            else:
                sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()
        if self.size < LOG_LIMIT:
            kept = data[:LOG_LIMIT - self.size]
            self.stream.write(kept)
            self.size += len(kept)
            if self.size >= LOG_LIMIT:
                self.stream.write(b"\n[HyperLab: the log stops here, at its size limit]\n")

    def say(self, text: str) -> None:
        self.write((text + "\n").encode())

    def close(self) -> None:
        self.stream.close()


def ask_password(machine: str) -> str:
    print(f"\nThe account on {machine} needs a password for the lock screen and the console.")
    print("It is hashed here and never stored; the hash file is deleted after the first pass.")
    for _ in range(3):
        first = getpass.getpass("New password for the Machine account: ")
        second = getpass.getpass("Repeat it: ")
        if first != second:
            print("The passwords differ.")
        elif len(first) < PASSWORD_MIN:
            print(f"Use at least {PASSWORD_MIN} characters.")
        elif "\n" in first or "\r" in first:
            print("The password must be one line.")
        else:
            return first
    raise Refused("no password was confirmed")


def password_hash(password: str) -> str:
    result = subprocess.run([OPENSSL, "passwd", "-6", "-stdin"], input=password + "\n",
                            capture_output=True, text=True, timeout=30, check=False)
    value = result.stdout.strip()
    require(result.returncode == 0 and HASH_RE.fullmatch(value) is not None, "could not hash the password")
    return value


def write_access_file(path: Path, value: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        require(stat.S_ISREG(path.lstat().st_mode), "unsafe stale access file")
        path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(f"workstation_access_password_hash: '{value}'\n")


def remove_access_file(path: Path | None) -> None:
    if path is not None:
        with held(), contextlib.suppress(FileNotFoundError):
            path.unlink()


def relay(child: subprocess.Popen, log: Log) -> None:
    """Copy the step's output until it closes or the step has ended. An
    ending signal is raised out of select or read by its handler."""
    fd = child.stdout.fileno()
    while True:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            data = os.read(fd, 65536)
            if not data:
                return
            log.write(data)
        elif child.poll() is not None:
            # Ended; a process it left behind may hold the pipe open.
            return


def run_step(repo: Path, argv: list[str], log: Log) -> int:
    program = [ANSIBLE] if argv[0] == "ansible-playbook" else [CLI, "--repo", str(repo)]
    child = None
    try:
        # A signal while the playbook is being started is raised only once
        # `child` names it, so every started playbook reaches the cleanup.
        # Its input stays the terminal, where the become prompt goes.
        with STOP.deferred():
            child = subprocess.Popen([*program, *argv[1:]], cwd=repo,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        relay(child, log)
        return child.wait()
    except BaseException:
        # Cancelled: the playbook ends, and is reaped, before its hash file
        # is removed. A playbook that could not be started has nothing to end.
        if child is not None:
            with held():
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=PLAYBOOK_GRACE)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
        raise
    finally:
        if child is not None:
            child.stdout.close()


def arguments(args: list[str]) -> tuple[str, int]:
    """MACHINE, or MACHINE --from N to resume at step N."""
    require((len(args) == 1 or (len(args) == 3 and args[1] == "--from" and FROM_RE.fullmatch(args[2])))
            and MACHINE_RE.fullmatch(args[0]) is not None,
            "usage: privatestack-machine-provision MACHINE [--from STEP]")
    return args[0], int(args[2]) if len(args) == 3 else 1


def resume_hint(repo: Path, machine: str, number: int) -> str:
    command = f"privatestack-machine-provision {machine}" + (f" --from {number}" if number > 1 else "")
    return f"cd {repo} && {command}"


def main(args: list[str]) -> int:
    os.umask(0o077)
    machine, first = arguments(args)
    # The provisioner derives the projection; nobody hands it a spec path.
    spec = f"vm-specs/.generated/{machine}.yml"
    repo = checkout()
    require(Path.cwd().resolve() == repo, "provisioning must run in the reviewed checkout")
    runtime = runtime_dir()
    profile, provisioning = machine_record(repo, machine)
    steps = steps_for(repo, machine, spec, runtime, profile)
    require(first <= len(steps), f"{machine} has {len(steps)} provisioning steps")
    if first > 1:
        resumable(provisioning, steps, first)
    directory = state_dir()
    with run_lock(directory, machine):
        if first > 1:
            # Read again under the lock: no other run may have moved it since.
            _profile, provisioning = machine_record(repo, machine)
            resumable(provisioning, steps, first)
        log = Log(directory, machine)
        try:
            return provision(repo, machine, spec, runtime, steps, first,
                             Receipt(directory, machine, provisioning["record_sha256"], steps, first), log)
        finally:
            log.close()


def provision(repo: Path, machine: str, spec: str, runtime: Path, steps: list[dict], first: int,
              receipt: Receipt, log: Log) -> int:
    access = None
    number = first
    try:
        receipt.write()
        log.say(f"Receipt {receipt.path}; the output of every step is kept in {log.path}.")
        for number, step in enumerate(steps, 1):
            if number < first:
                continue
            receipt.step(number, "running")
            receipt.write()
            log.say(f"\n=== Step {number}/{len(steps)}: {step['label']}")
            argv = list(step["argv"])
            if step["password"]:
                # An unsafe directory is refused before the password is asked.
                path = private_dir(runtime) / f"{machine}-access.yml"
                password = ask_password(machine)
                try:
                    value = password_hash(password)
                finally:
                    del password
                # Known before it exists, so no signal can leave it unnamed.
                with held():
                    access = path
                    write_access_file(path, value)
                argv = [part.replace(ACCESS_FILE, str(access)) for part in argv]
            try:
                rc = run_step(repo, argv, log)
            finally:
                remove_access_file(access)
                access = None
            if rc != 0:
                receipt.step(number, "failed", rc)
                receipt.end("failed", f"step {number} ended with exit status {rc}")
                receipt.write()
                log.say(f"\nStep {number} failed (exit {rc}): {step['label']}.")
                log.say(f"The Machine record and {spec} stay. Provisioning is incomplete; resume it with:")
                log.say(f"  {resume_hint(repo, machine, number)}")
                return rc
            receipt.step(number, "ok", 0)
            # The last step's result and "finished" are one write.
            if number == len(steps):
                receipt.end("finished")
            receipt.write()
    except (KeyboardInterrupt, EOFError, Cancelled) as exc:
        signum = exc.signum if isinstance(exc, Cancelled) else signal.SIGINT
        reason = ("the terminal closed" if isinstance(exc, EOFError)
                  else f"stopped by {signal.Signals(signum).name}")
        receipt.stop(number, "interrupted", reason)
        log.say(f"\nProvisioning interrupted at step {number}: {reason}. Resume it with:")
        log.say(f"  {resume_hint(repo, machine, number)}")
        raise
    except BaseException as exc:
        receipt.stop(number, "failed", str(exc) or type(exc).__name__)
        log.say(f"\nProvisioning failed at step {number}: {exc}. Resume it with:")
        log.say(f"  {resume_hint(repo, machine, number)}")
        raise
    finally:
        remove_access_file(access)

    log.say(f"\n{machine} is provisioned.")
    return 0


def entry(args: list[str]) -> int:
    # A stopped unit (SIGTERM) or a terminal that hangs up (SIGHUP) ends the
    # run like Ctrl-C: the running playbook is stopped, the hash file removed.
    for signum in (signal.SIGINT, *CANCELLING):
        signal.signal(signum, STOP.handle)
    try:
        return main(args)
    except (Refused, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"HyperLab provisioning refused: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nHyperLab provisioning cancelled.", file=sys.stderr)
        return 128 + signal.SIGINT
    except Cancelled as exc:
        print(f"\nHyperLab provisioning stopped by {signal.Signals(exc.signum).name}.", file=sys.stderr)
        return 128 + exc.signum


if __name__ == "__main__":
    raise SystemExit(entry(sys.argv[1:]))
