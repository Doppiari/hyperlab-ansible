# The sender capture harness invoked into a loop it had destroyed

Author: [importriri](https://github.com/importriri).

Status: corrected in the test harness; software-verified. The runtime patch
and the sender were right and are unchanged.

## Symptom

Seen in CI on `main` at c6d3a4d, 2026-11-24:
`tests/looking_glass_sender_capture_contract.py` failed with
`initial-failure-2: '' (exit -11)`. The sender's stderr showed the core
error and `The PipeWire capture failed before its initial format`, so
initialization had ended as it should; the harness then died of SIGSEGV
before it printed its result line.

## Cause

The initial-failure scenarios delivered the failure from a producer thread:
it slept 100 ms and then called `pw_loop_invoke(..., true, ...)`, which
blocks until the PipeWire thread has run the callback and acknowledged it.
The callback marks the capture failed and signals the waiting
initialization. Initialization then follows its cleanup path:
`pipewire_deinit()` stops and joins the PipeWire thread and destroys the
thread loop.

Nothing ordered that cleanup after the producer's return from
`pw_loop_invoke`. The PipeWire thread sends the acknowledgement before it
releases the loop lock, so initialization can wake, stop and destroy the
loop while the producer is still inside `pw_loop_invoke` on it. The
producer then touches freed memory; the heap is corrupted and a later
allocation crashes.

The sender itself has no such thread. Its failures come from PipeWire's own
events on the PipeWire thread, and initialization is the only thread that
waits on that loop.

On an 8-core machine with libpipewire 1.6.8, 16 parallel loops of the old
harness crashed (exit 139) in 11, 9 and 43 of 1500 runs of
`initial-failure-0`, `-1` and `-2`; 9 of 96 complete runs of the contract,
16 at a time, failed with the CI signature, three on each scenario. A probe recording whether the producer
had returned from `pw_loop_invoke` by the time initialization had finished
its cleanup found it had not in 5 of 400 runs. A SIGSEGV handler caught the
crash in the main thread, in `malloc` under the first `printf` after the
cleanup.

## Correction

The scenario now queues the failure from the initializing thread itself,
with a non-blocking `pw_loop_invoke`, while it holds the loop lock, and then
enters the initialization wait. The PipeWire thread can run the queued
callback only once the wait releases the lock, so the failure still
arrives while initialization waits, now without a timed sleep, and no other
thread is inside the loop when initialization destroys it. The producer
thread is gone.

The other scenarios were checked for the same pattern: every thread that
invokes into the loop is joined, or is the thread that runs the teardown,
before `pipewire_deinit()`.

## Regression proof

The same load ran 1500 runs of each initial-failure scenario with no
failure, and 96 complete runs of the contract, 16 at a time, all passed.
This is load evidence, not a proof by construction; the construction is the
ordering above.

The contract still fails for the reason it exists. With the runtime patch's
initial wait put back to ignore `streamFailed`, it reports
`initial-failure-0: the harness itself hung`; with initialization going on
after a failure, `initialization accepted a failure before the first
format`; with a core error no longer marking the capture failed,
`initial-failure-2: the harness itself hung`. The mutations are in
`tests/MUTATIONS.md`.
