# Shell refresh contract assumed synchronous stopping

## Observation

CI at `f38f1bf` failed in `shell_reload_after_apply_contract.py` while pausing
the real inert launcher: `RuntimeError: Shell did not stop every thread;
reapply`. The same check could pass locally without a change.

## Cause

The contract assumed that returning from `pidfd_send_signal(SIGSTOP)` meant
the target had already stopped. Signal submission and delivery are separate;
the next thread-state sample can still observe a running thread. See
[Linux signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html).

[ADR 0061](../docs/adr/0061-resident-desktop-updates.md) deliberately requires
one immediate all-thread sample. Incomplete stopping causes refusal and
resume, without a wait while host trust and provenance presentation is
frozen. The real fixture treated this valid refusal as a broken safety
contract. Its busy-child fixture had the opposite problem: it accepted any
runtime refusal, so an incomplete stop could pass without ever reaching
the paused cgroup inspection.

## Fix and verification

Keep installed refresh behavior and its single-sample, no-wait checks.
Only inert-process fixtures retry the exact incomplete-stop error from
context entry. The failed context resumes the process and closes its PID
descriptor before a short delay and another attempt. A five-second deadline
fails the contract if no attempt succeeds. Unrelated entry failures and
exceptions from inside the paused body are never retried.

A deterministic regression forces the first post-SIGSTOP sample to report
incomplete stopping for each real process. The launcher must subsequently
reach a genuine pause and pinned kill without executing its queued child.
The busy-child fixture must reach the paused cgroup sample, refuse for that
child, and leave both processes alive with the shell resumed. Separate
fixtures require bounded retries, resume before any retry wait, exact
process identity and propagation of entry and body failures. Mutations are
recorded under resident desktop updates in `tests/MUTATIONS.md`.

These are software checks. Installed Nitro and Predator refresh acceptance
remains open.
