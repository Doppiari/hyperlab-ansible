# The Sfere seal's clock does not know the session is locked

Author: [importriri](https://github.com/importriri).

Status: deferred; the clock stops on every other condition
([ADR 0069](../docs/adr/0069-sfere-seal.md)).

## Symptom

The seal's one 33 ms timer must stop whenever nobody can see the view:
another tab, a hidden or minimised window, or a locked session. The first
three stop it. Under a locked session the workspace window stays mapped
behind the locker, so a seal left open with ambient motion on, or with a lit
network, keeps its timer running until the session is unlocked.

## Root cause

The shell learns that the session is being locked (`sessionLocking()` in
`ShellSurfaces.qml`, called for the shell's own lock action and by
`privatestack-lock.sh` through `qs -c hyperlab ipc call session locking`)
and withdraws armed state, but it keeps no "locked" state and is never told
when the session is unlocked. The window's visibility does not
change under the locker either. The view therefore has nothing to bind its
clock to.

## Cost

The timer advances a few numbers and the scene redraws at most 30 times a
second behind the locker, at `textureScale` 0.5 when the GPU is lent. No
state is shown or changed.

## To close it

Keep a `sessionLocked` state in the shell, set by the lock notification and
cleared by an unlock notification from the lock helper, and add it to the
seal's `shown` condition. Both need changes outside the view.
