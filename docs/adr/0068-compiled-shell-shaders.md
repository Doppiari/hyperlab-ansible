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
redirected file and any digest that differs. Where the recorded `qsb`
version is installed, it rebuilds every shader into a temporary directory
and requires the committed bytes. With another version, or without `qsb`,
it prints that the rebuild was skipped and why, and keeps the digest check:
it never passes silently. `verify.sh` level 0j runs it through
`tests/network_sphere_contract.py --manifest` and shows its report.

Every component that runs a shader has a complete still form drawn with
QtQuick Shapes, chosen under the software backend, on an effect error (a
missing or broken `.qsb`) and on request. The still form is never presented
as a shader render: a shader render is claimed only where Qt reports the
OpenGL API.

## Consequences

- A shader edit without `tools/build-shaders.sh` fails `verify.sh`; an edit
  of the `.qsb` alone fails too.
- A Qt Shader Tools upgrade on the build machine changes the version line.
  The rebuild is then skipped with that reason until the shaders are rebuilt
  and the new manifest committed. Should the host's Qt ever refuse the
  committed `.qsb`, the effect reports an error and the sphere draws its
  still form; the hardware gate shows which form runs.
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
