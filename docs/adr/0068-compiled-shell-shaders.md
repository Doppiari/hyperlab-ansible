# ADR 0068 - Compile the shell's shaders in the repository

Status: Proposed

## Context

The Sfere seal draws every network as a glass sphere with an energy core
(operator design decision of 2026-11-17). The look needs a fragment shader.
Qt 6 runs a `ShaderEffect` only from a `.qsb` package that Qt Shader Tools
(`qsb`, Arch package `qt6-shadertools`) compiles from Vulkan-style GLSL.
The host runs the shell from the files the role installs; it has never
needed a compiler, and the runtime contracts render with Qt's software
backend, where no shader runs.

## Decision

Keep the GLSL source and its compiled `.qsb` side by side in the shell's
`shaders/` directory and commit both. `tools/build-shaders.sh` is the only
way to produce them: it compiles every `*.frag` and `*.vert` with fixed
targets (`--glsl "100 es,120,150" --hlsl 50 --msl 12`) and records
`shaders/SHADERS.sha256`: the `qsb --version` line, then the SHA-256 of
every source and every `.qsb`. The role installs the directory as it
installs the QML; the host compiles nothing and needs no new package.

`tools/build-shaders.sh --check` refuses a missing, duplicated, unlisted or
redirected file and any digest that differs. Wherever a `qsb` is installed,
whatever its version, it rebuilds every shader into a temporary directory
and requires the committed bytes. With a version other than the recorded
one it names both when the bytes match, and when they differ it refuses and
asks for the shaders to be rebuilt with that `qsb` and committed. Only
without any `qsb` does it skip the rebuild; it says so and keeps the digest
check: it never passes silently. `verify.sh` level 0j runs
`tests/network_sphere_contract.py`, which includes this check, and shows
its verdicts.

Every component that runs a shader has a complete still form drawn with
QtQuick Shapes, chosen under the software backend, on an effect error (a
missing or broken `.qsb`) and on request. The still form is never presented
as a shader render: a shader render is claimed only where Qt reports the
OpenGL API.

## Consequences

- A shader edit without `tools/build-shaders.sh` fails `verify.sh`; an edit
  of the `.qsb` alone fails too.
- A Qt Shader Tools upgrade that changes the compiled bytes turns
  `verify.sh` red on every machine with the new `qsb`, the nested lab
  included, until the shaders are rebuilt with it and the new manifest is
  committed. A machine still on an older `qsb` then turns red in its turn
  until it is updated. A version check that skipped the rebuild instead would
  stop proving anything after the next upgrade. Should the host's Qt ever
  refuse the committed `.qsb`, the effect reports an error and the sphere
  draws its still form; the hardware gate shows which form runs.
- The shader's look is checked by software only where Xvfb gives an OpenGL
  render (Mesa llvmpipe); otherwise by the operator on hardware.

## Alternatives considered

- Compile on the host during apply: a compiler on the host for one effect,
  and an apply that can fail on a toolchain change.
- `.frag` only, compiled by Qt at runtime: Qt 6 does not compile GLSL at
  runtime for `ShaderEffect`.
- Fail the check whenever `qsb` is missing: CI and machines without Qt
  Shader Tools would be red for a file they cannot change; the digests still
  catch an edit there.
- Rebuild only with the recorded `qsb` version and skip otherwise: on a
  rolling distribution every machine soon has another version, and the
  check would only ever compare digests.
