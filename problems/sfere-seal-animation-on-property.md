# The seal's source check let an animation on a property through

Author: [importriri](https://github.com/importriri).

## Symptom

The Sfere seal may move only on its one 33 ms clock: no QML animation, no
behaviour and no transition in any of its files. A break added to
`SealNetwork.qml` while the live layer's electrons were catalogued,

```qml
NumberAnimation on liveTime { from: 0; to: 1000; duration: 1000000; loops: Animation.Infinite }
```

turned an electron loop into an animation running beside the clock, and
`tests/sfere_view_contract.py` still printed OK.

## Root cause

The source check searched each seal file for a type name followed directly
by its opening brace (`NumberAnimation {`, `Behavior {`, ...). QML also
declares an animation as a property value source, `Type on property { ... }`,
and that form has the property name between the type and the brace, so the
pattern never matched it. A `Behavior on x { ... }` was refused only through
the animation nested inside it, never for itself.

## Fix

The check accepts an optional `on <property>` between the type name and the
brace, so the value-source form is refused like the plain one. The
`electron-animation` break in `tests/MUTATIONS.md` (section "Sfere seal:
the live layer") is red with "SealNetwork.qml gained an animation or a data
transport", and every seal file is still clean.

## Lesson

A source check over QML has to know every way the language spells the thing
it refuses. Each pattern of that kind needs one break per spelling, not one
break per type.
