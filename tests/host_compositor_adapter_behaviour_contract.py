#!/usr/bin/env python3
"""Behavioural contract for the compositor adapter's shell-facing streams.

Runs the real adapter against inert fake `swaymsg` / `hyprctl` binaries in a
temporary directory. Nothing touches a real compositor, and nothing is
written outside that directory. It proves four things the shell relies on:

  * event watchers re-publish on a heartbeat, so a healthy but quiet stream
    never ages into "stale" and never disables workspace navigation;
  * the Hyprland watchers measure that heartbeat from the last published
    snapshot, so a busy stream of events they ignore (title changes, focus
    moving inside one workspace) cannot postpone it, and those events never
    publish by themselves;
  * every workspace snapshot names the focused output, which is how a
    keyboard-summoned launcher, panel or OSD finds its output;
  * an output name that is not a plain connector name is withheld;
  * `shell-window-focus` focuses only the window owned by the calling shell
    process, never a same-titled window from another process;
  * the shared lock helper notifies the shell without waiting for it.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "roles/host_desktop_common/files/privatestack-compositor-adapter.sh"
LOCK = ROOT / "roles/host_desktop_common/files/privatestack-lock.sh"

PRODUCT_NAME = json.loads((ROOT / "tools/product.yml").read_text())["name"]

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def fake_sway(bindir: Path, output: str) -> None:
    write_executable(bindir / "swaymsg", f"""#!/bin/bash
case "$*" in
  *subscribe*) sleep 30 ;;
  *get_workspaces*)
    echo '[{{"num":1,"focused":false,"output":"HDMI-A-1"}},{{"num":2,"focused":true,"output":{output},"urgent":true}}]' ;;
  *get_tree*)
    echo "{{\\"id\\":1,\\"nodes\\":[{{\\"id\\":42,\\"pid\\":$FAKE_OWNER,\\"name\\":\\"HyperLab · Machines\\",\\"nodes\\":[]}},{{\\"id\\":7,\\"pid\\":99999,\\"name\\":\\"HyperLab · guest\\"}}],\\"floating_nodes\\":[]}}" ;;
  *) echo "SWAY $*" ;;
esac
""".replace("HyperLab", PRODUCT_NAME))


def fake_hyprland(bindir: Path) -> None:
    write_executable(bindir / "hyprctl", """#!/bin/bash
if [[ $1 == clients ]]; then
  echo "[{\\"pid\\":99999,\\"title\\":\\"HyperLab · guest\\",\\"stableId\\":\\"1\\"},{\\"pid\\":$FAKE_OWNER,\\"title\\":\\"HyperLab · Diagnostics\\",\\"stableId\\":\\"18000abc\\"}]"
else
  echo "DISPATCH $*"
fi
""".replace("HyperLab", PRODUCT_NAME))


def watch_lines(env: dict, seconds: float) -> list[str]:
    process = subprocess.Popen(
        ["bash", str(ADAPTER), "workspace-watch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    time.sleep(seconds)
    process.terminate()
    try:
        out, _ = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        out, _ = process.communicate()
    return [line for line in out.splitlines() if line.strip()]


def heartbeat_and_output(base_env: dict, bindir: Path) -> None:
    fake_sway(bindir, '"eDP-1"')
    env = dict(base_env, HYPERLAB_COMPOSITOR_BACKEND="sway",
               HYPERLAB_WATCH_HEARTBEAT_SECONDS="1")
    lines = watch_lines(env, 3.5)
    check(len(lines) >= 3,
          "a quiet workspace stream did not re-publish on its heartbeat (%d lines)" % len(lines))
    check(all('"output":"eDP-1"' in line for line in lines),
          "workspace snapshots do not name the focused output: %r" % lines[:1])
    check(all('"active":2' in line and '"urgent":[2]' in line for line in lines),
          "workspace snapshot content changed: %r" % lines[:1])

    fake_sway(bindir, '"eDP-1;rm -rf /"')
    lines = watch_lines(env, 1.2)
    check(bool(lines) and all('"output":""' in line for line in lines),
          "an output name that is not a connector name was passed on: %r" % lines[:1])

    # An out-of-range override falls back to the reviewed interval rather
    # than spinning or disabling the heartbeat.
    fake_sway(bindir, '"eDP-1"')
    env_bad = dict(env, HYPERLAB_WATCH_HEARTBEAT_SECONDS="0")
    lines = watch_lines(env_bad, 1.5)
    check(len(lines) == 1,
          "an invalid heartbeat override changed the interval (%d lines)" % len(lines))


HYPR_SIGNATURE = "contract"

# Busy-stream fixture: heartbeat, duration and event period. Eleven seconds
# hold more than three heartbeats, and one unrelated event per second is
# always sooner than the heartbeat.
BUSY_HEARTBEAT = 3
BUSY_SECONDS = 11.0
BUSY_PERIOD = 1.0
# Slack for process start, three hyprctl calls and a loaded verifier host.
SLACK = 1.0

UNRELATED_EVENTS = {
    # Neither loop lists these; a terminal or a browser tab can send them
    # every second.
    "workspace-watch": "windowtitle>>0xabc",
    "focused-window-watch": "windowtitle>>0xabc",
}
LISTED_EVENTS = {
    "workspace-watch": "workspace>>2",
    "focused-window-watch": "activewindow>>kitty,shell",
}


def fake_hyprctl_state(bindir: Path) -> None:
    write_executable(bindir / "hyprctl", """#!/bin/bash
case "$1" in
  workspaces) echo '[{"id":1,"windows":1},{"id":2,"windows":0}]' ;;
  activeworkspace) echo '{"id":1,"monitor":"eDP-1"}' ;;
  clients) echo '[]' ;;
  activewindow) echo '{"pid":4242,"class":"kitty","address":"0xabc","title":"shell","fullscreen":0}' ;;
  *) exit 1 ;;
esac
""")


Feed = Callable[[socket.socket, float], None]


def hypr_watch(
    env_base: dict, scratch: Path, name: str, command: str,
    heartbeat: int, seconds: float, feed: Feed | None,
    adapter: Path = ADAPTER,
) -> tuple[list[float], list[str], int | None, str]:
    """Run one Hyprland watcher against a fake event socket.

    Returns the arrival time of every published line (seconds after start),
    the lines, the exit status when the watcher ended by itself (None when it
    had to be stopped) and its standard error. With `feed` None no socket
    exists at all.
    """
    runtime = scratch / name
    socket_dir = runtime / "hypr" / HYPR_SIGNATURE
    socket_dir.mkdir(parents=True)
    server = None
    if feed is not None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_dir / ".socket2.sock"))
        server.listen(1)
        server.settimeout(10)
    env = dict(env_base, HYPERLAB_COMPOSITOR_BACKEND="hyprland",
               HYPRLAND_INSTANCE_SIGNATURE=HYPR_SIGNATURE,
               XDG_RUNTIME_DIR=str(runtime),
               HYPERLAB_WATCH_HEARTBEAT_SECONDS=str(heartbeat))
    stderr_path = scratch / (name + ".stderr")
    stamps: list[float] = []
    lines: list[str] = []
    with stderr_path.open("w") as stderr:
        process = subprocess.Popen(
            ["bash", str(adapter), command],
            stdout=subprocess.PIPE, stderr=stderr, text=True, env=env,
            start_new_session=True,
        )
    started = time.monotonic()

    def read() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if line.strip():
                stamps.append(time.monotonic() - started)
                lines.append(line.strip())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    connection = None
    try:
        if server is not None and feed is not None:
            connection, _ = server.accept()
            feed(connection, started)
        deadline = started + seconds
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        status = process.poll()
        if status is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        else:
            # Reap anything the watcher left in its session.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        reader.join(timeout=5)
        if connection is not None:
            connection.close()
        if server is not None:
            server.close()
    return stamps, lines, status, stderr_path.read_text()


def send(connection: socket.socket, line: str) -> None:
    try:
        connection.sendall((line + "\n").encode())
    except OSError:
        pass


def busy_feed(event: str, seconds: float) -> Feed:
    def feed(connection: socket.socket, started: float) -> None:
        number = 0
        while time.monotonic() - started < seconds:
            number += 1
            send(connection, "%s,title %d" % (event, number))
            time.sleep(BUSY_PERIOD)
    return feed


def quiet_feed(connection: socket.socket, started: float) -> None:
    del connection, started


def listed_feed(unrelated: str, listed: str) -> Feed:
    def feed(connection: socket.socket, started: float) -> None:
        for at, line in ((0.5, unrelated), (1.0, listed), (2.0, unrelated)):
            time.sleep(max(0.0, started + at - time.monotonic()))
            send(connection, line)
    return feed


def ending_feed(connection: socket.socket, started: float) -> None:
    time.sleep(max(0.0, started + 0.5 - time.monotonic()))
    connection.shutdown(socket.SHUT_RDWR)


# The adapter's only clock read. The clock case stages a copy that reads a
# file instead, so the contract can move the wall clock.
CLOCK_READ = "now=${EPOCHREALTIME:-}"
FAKE_EPOCH = 1795000000


def clock_back_feed(clock: Path, unrelated: str) -> Feed:
    def feed(connection: socket.socket, started: float) -> None:
        time.sleep(max(0.0, started + 1.0 - time.monotonic()))
        clock.write_text("%d.000000\n" % (FAKE_EPOCH - 3600))
        send(connection, unrelated)
    return feed


def snapshots_parse(command: str, lines: list[str]) -> bool:
    try:
        payloads = [json.loads(line) for line in lines]
    except json.JSONDecodeError:
        return False
    if command == "workspace-watch":
        return all(payload.get("active") == 1 and payload.get("output") == "eDP-1"
                   for payload in payloads)
    return all(payload.get("app_id") == "kitty" for payload in payloads)


def busy_stream(env: dict, scratch: Path, command: str, results: dict) -> None:
    results[command] = hypr_watch(
        env, scratch, "busy-" + command, command, BUSY_HEARTBEAT, BUSY_SECONDS,
        busy_feed(UNRELATED_EVENTS[command], BUSY_SECONDS))


def hyprland_heartbeat(base_env: dict, scratch: Path) -> None:
    bindir = scratch / "hyprbin"
    bindir.mkdir()
    fake_hyprctl_state(bindir)
    env = dict(base_env, PATH=str(bindir) + os.pathsep + base_env["PATH"])
    commands = ("workspace-watch", "focused-window-watch")

    # A busy stream of events the loop ignores: the heartbeat still fires on
    # time, and those events add nothing of their own.
    results: dict = {}
    threads = [threading.Thread(target=busy_stream, args=(env, scratch, command, results))
               for command in commands]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    expected = int(BUSY_SECONDS // BUSY_HEARTBEAT) + 1
    for command in commands:
        stamps, lines, _, _ = results[command]
        print("%s: busy Hyprland stream, heartbeat %ds, %.0fs, one unrelated event "
              "per %.0fs: %d snapshots at %s"
              % (command, BUSY_HEARTBEAT, BUSY_SECONDS, BUSY_PERIOD, len(stamps),
                 ", ".join("%.1f" % stamp for stamp in stamps)))
        check(len(stamps) >= expected,
              "%s: a busy stream of unrelated events postponed the heartbeat "
              "(%d snapshots in %.0fs, expected at least %d)"
              % (command, len(stamps), BUSY_SECONDS, expected))
        check(len(stamps) <= expected + 1,
              "%s: unrelated events published snapshots of their own "
              "(%d snapshots in %.0fs)" % (command, len(stamps), BUSY_SECONDS))
        gaps = [later - earlier for earlier, later in zip(stamps, stamps[1:])]
        tail = BUSY_SECONDS - stamps[-1] if stamps else BUSY_SECONDS
        check(all(gap <= BUSY_HEARTBEAT + SLACK for gap in gaps + [tail]),
              "%s: more than one heartbeat passed without a snapshot: gaps %s, tail %.1f"
              % (command, ["%.1f" % gap for gap in gaps], tail))
        check(all(gap >= BUSY_HEARTBEAT - SLACK for gap in gaps),
              "%s: a snapshot came sooner than the heartbeat with only unrelated "
              "events: gaps %s" % (command, ["%.1f" % gap for gap in gaps]))
        check(snapshots_parse(command, lines),
              "%s: a busy-stream snapshot changed content: %r" % (command, lines[:1]))

    # The wall clock moves back an hour after the first snapshot: the time
    # left is still bounded by one heartbeat, not by the hour.
    source = ADAPTER.read_text(encoding="utf-8")
    check(source.count(CLOCK_READ) == 1,
          "the adapter no longer reads its clock exactly once as %r" % CLOCK_READ)
    staged = scratch / "adapter-fake-clock.sh"
    clock = scratch / "clock"
    clock.write_text("%d.000000\n" % FAKE_EPOCH)
    staged.write_text(source.replace(CLOCK_READ, 'now=$(<"%s")' % clock))
    stamps, _, _, _ = hypr_watch(
        env, scratch, "clock-back", "workspace-watch", 2, 4.5,
        clock_back_feed(clock, UNRELATED_EVENTS["workspace-watch"]), staged)
    check(len(stamps) >= 2 and stamps[1] <= 3.0 + SLACK,
          "a wall clock moved back stretched the heartbeat: snapshots at %s"
          % ["%.1f" % stamp for stamp in stamps])

    for command in commands:
        # A quiet Hyprland stream re-publishes on its heartbeat.
        stamps, lines, _, _ = hypr_watch(
            env, scratch, "quiet-" + command, command, 1, 3.5, quiet_feed)
        check(3 <= len(stamps) <= 5,
              "%s: a quiet Hyprland stream did not re-publish on its heartbeat "
              "(%d snapshots in 3.5s)" % (command, len(stamps)))
        check(snapshots_parse(command, lines),
              "%s: a quiet-stream snapshot changed content: %r" % (command, lines[:1]))

        # A listed event publishes at once; the unrelated ones around it do
        # not, and the long heartbeat stays out of the way.
        stamps, _, _, _ = hypr_watch(
            env, scratch, "listed-" + command, command, 30, 3.0,
            listed_feed(UNRELATED_EVENTS[command], LISTED_EVENTS[command]))
        check(len(stamps) == 2 and 1.0 <= stamps[1] <= 1.0 + SLACK,
              "%s: a listed event did not publish at once, or an unrelated one "
              "did: snapshots at %s" % (command, ["%.1f" % stamp for stamp in stamps]))

        # The end of the event stream ends the watcher.
        stamps, _, status, _ = hypr_watch(
            env, scratch, "end-" + command, command, 30, 3.0, ending_feed)
        check(status == 0 and len(stamps) == 1,
              "%s: the end of the event stream did not end the watch "
              "(status %r, %d snapshots)" % (command, status, len(stamps)))

        # No event socket: one snapshot, then the reviewed refusal.
        stamps, _, status, stderr = hypr_watch(
            env, scratch, "missing-" + command, command, 30, 3.0, None)
        check(status == 4 and len(stamps) == 1
              and "Hyprland event socket is unavailable" in stderr,
              "%s: a missing event socket was not refused as before "
              "(status %r, %d snapshots, %r)" % (command, status, len(stamps), stderr))


def owner_bound_focus(base_env: dict, bindir: Path, scratch: Path) -> None:
    # Model an apply from a newer tree than the operator's CLI checkout.
    write_executable(bindir / "hyperlabctl", "#!/bin/sh\nprintf '%s\\n' 'hyperlabctl 0.1.0'\n")
    product = scratch / "product.yml"
    product.write_bytes((ROOT / "tools/product.yml").read_bytes())
    staged_adapter = scratch / "adapter.sh"
    staged_adapter.write_text(ADAPTER.read_text().replace(
        "/etc/xdg/quickshell/hyperlab/product.yml", str(product)))
    fake_hyprland(bindir)
    fake_sway(bindir, '"eDP-1"')
    caller = scratch / "caller.sh"
    write_executable(caller, f"""#!/bin/bash
export FAKE_OWNER=$$
HYPERLAB_COMPOSITOR_BACKEND=$1 bash {staged_adapter} shell-window-focus
""")
    for backend, expected, foreign in (
        ("hyprland", 'hl.dsp.focus({ window = "stableid:18000abc" })', "stableid:1 "),
        ("sway", "[con_id=42] focus", "[con_id=7]"),
    ):
        result = subprocess.run(
            ["bash", str(caller), backend],
            capture_output=True, text=True, env=base_env, timeout=20, check=False,
        )
        check(result.returncode == 0,
              "%s: shell-window-focus failed: %s" % (backend, result.stderr.strip()))
        check(expected in result.stdout,
              "%s: the shell-owned workspace window was not focused: %r"
              % (backend, result.stdout))
        check(foreign not in result.stdout,
              "%s: a same-titled window from another process was focused" % backend)

    # Called from a process that owns no workspace window: nothing is focused.
    result = subprocess.run(
        ["bash", str(staged_adapter), "shell-window-focus"],
        capture_output=True, text=True,
        env=dict(base_env, HYPERLAB_COMPOSITOR_BACKEND="sway", FAKE_OWNER="1"),
        timeout=20, check=False,
    )
    check(result.returncode != 0 and "focus" not in result.stdout,
          "shell-window-focus focused something for a process that owns nothing")

    for raw in ("{}", '{"name":"A","name":"B","byline":"by C"}',
                '{"name":"A","byline":"by B","byline":"by C"}'):
        product.write_text(raw)
        for backend in ("sway", "hyprland"):
            result = subprocess.run(["bash", str(caller), backend], env=base_env,
                                    capture_output=True, text=True, timeout=10, check=False)
            check(result.returncode != 0 and not result.stdout,
                  "%s: focus dispatched with invalid identity" % backend)
    product.unlink()
    product.symlink_to(ROOT / "tools/product.yml")
    result = subprocess.run(["bash", str(caller), "sway"], env=base_env,
                            capture_output=True, text=True, timeout=10, check=False)
    check(result.returncode != 0 and not result.stdout, "focus accepted redirected identity")


def lock_does_not_wait(base_env: dict, bindir: Path, scratch: Path) -> None:
    # A shell that hangs on IPC must not delay the locker.
    write_executable(bindir / "qs", "#!/bin/bash\nsleep 20\n")
    write_executable(bindir / "hyprlock", "#!/bin/bash\necho LOCKED\n")
    write_executable(bindir / "pidof", "#!/bin/bash\nexit 1\n")
    adapter = scratch / "adapter"
    write_executable(adapter, "#!/bin/bash\necho hyprland\n")
    started = time.monotonic()
    result = subprocess.run(
        ["bash", str(LOCK)],
        capture_output=True, text=True, timeout=15, check=False,
        env=dict(base_env, HYPERLAB_COMPOSITOR_ADAPTER=str(adapter)),
    )
    elapsed = time.monotonic() - started
    check("LOCKED" in result.stdout, "the lock helper did not start the locker")
    check(elapsed < 1.5, "the lock helper waited for the shell (%.1fs)" % elapsed)
    source = LOCK.read_text(encoding="utf-8")
    check("ipc call session locking" in source and "timeout 2" in source,
          "the lock helper no longer notifies the shell through the fixed receiver")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hyperlab-adapter-") as scratch_name:
        scratch = Path(scratch_name)
        bindir = scratch / "bin"
        bindir.mkdir()
        base_env = dict(os.environ)
        base_env["PATH"] = str(bindir) + os.pathsep + base_env.get("PATH", "")
        base_env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        base_env.pop("SWAYSOCK", None)

        heartbeat_and_output(base_env, bindir)
        hyprland_heartbeat(base_env, scratch)
        owner_bound_focus(base_env, bindir, scratch)
        lock_does_not_wait(base_env, bindir, scratch)

    if FAILURES:
        for failure in FAILURES:
            print("FAIL:", failure)
        return 1

    print("HyperLab compositor adapter behaviour contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
