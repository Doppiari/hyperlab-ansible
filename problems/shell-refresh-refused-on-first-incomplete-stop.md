# Shell refresh refused on its first incomplete stop

## Observation

The host apply at `971ab67` failed in `host_desktop_common : Refresh the
running HyperLab shell`. The refresh script exited with
`RuntimeError: Shell did not stop every thread; reapply` and empty output,
so the task's `changed_when` also reported a `from_json` error on that
empty output. Every earlier task, including the shell copies, was `ok`:
the apply only had to replace the running shell.

## Cause

The installed refresh sent `SIGSTOP` once, sampled every thread once and
treated any thread not yet in state `T` as a final refusal. Group stop is
asynchronous: each thread stops only when it is next scheduled, and a thread
running on another CPU is often still seen running by a sample taken right
after the signal. See [Linux signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html).
[ADR 0061](../docs/adr/0061-resident-desktop-updates.md) expected this
refusal and left the retry to "a later apply", but a refused refresh fails
the apply, so every incomplete first sample failed a host apply.

On a development workstation, inert multithreaded processes stopped
completely at the first sample in 10 to 100 percent of attempts, depending
on how many threads kept running and how loaded the CPUs were. The
[earlier fixture defect](shell-refresh-contract-assumed-synchronous-stop.md)
was the same fact seen from the contract side.

## Fix and verification

`paused_shell` keeps its single sample and raises a dedicated
`IncompleteStop` for it. `replace_shell` retries only that failure raised
on pause entry. The pause has already resumed the shell, which then runs
for 50 ms; the live idle inspection repeats and the same pinned process
identity is paused again. Ten seconds after the first incomplete stop the
original refusal is reported. A busy child, a changed identity and any
failure inside the paused inspection are never retried, and there is
still no sleep or clock read while the shell is stopped.

With resumed retries under that deadline, all 760 trials on inert
processes, including seven threads kept running with every CPU loaded,
stopped completely; the slowest needed 78 attempts.

The replacement stage of `tests/shell_reload_after_apply_contract.py`
now covers a late stop (refresh after one resumed retry), a shell that
never stops (resume before every retry, bounded by the ten seconds), a
changed identity on retry and an incomplete-stop error raised inside the
paused inspection. Mutations V64-V70 in `tests/MUTATIONS.md` were each red
and green after restoration.

These are software checks. The real shell's incomplete-stop rate on the
Nitro is unmeasured; the next host apply that changes the shell is the
first real evidence.
