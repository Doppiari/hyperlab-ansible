# An offscreen OpenGL render silently used the software backend

Author: [importriri](https://github.com/importriri).

Status: corrected in the contract, software-verified.

## Symptom

The network sphere needed one render through Qt's RHI, so that its shader
could be seen outside the hardware gate. The natural recipe,
`QT_QPA_PLATFORM=offscreen` with `QSG_RHI_BACKEND=opengl` and Mesa
llvmpipe, ran without an error or a warning and wrote a capture. The capture
showed the still form: `GraphicsInfo.api` was `GraphicsInfo.Software`.

## Root cause

Qt's offscreen platform plugin offers OpenGL only through GLX, which needs an
X display. Without one the plugin reports no OpenGL capability, and Qt Quick
loads its software adaptation instead of failing, whatever
`QSG_RHI_BACKEND` asks for. A test that trusted its environment variables
would have presented the still form as a shader render.

## Fix

`tests/network_sphere_contract.py` starts an Xvfb server of its own
(`-displayfd`, no TCP listener), renders with the `xcb` platform and
`QSG_RHI_BACKEND=opengl` on it, and reads `GraphicsInfo.api` from the scene.
It calls the render a shader render only when that is `GraphicsInfo.OpenGL`
and no sphere chose the still form; otherwise it prints that the RHI render
was skipped and why. Without Xvfb it says so too, and the shader look stays
with the hardware gate.

## Regression proof

On a machine with Xvfb the contract reports `RHI render: OpenGL shader form,
fallbacks and the lit gate checked`; the sheet shows the shader's glass and
moving core, and a missing or corrupt `.qsb` falls back to the still form.
The mutation `no-shader-error-fallback` in `tests/MUTATIONS.md` turns that
RHI part red. Forcing the software backend in the RHI fixture reports the
skip, never a shader result.

## In the nested lab

The nested lab host has no Xvfb (the
[GTK display repair](gtk-contracts-required-an-unmanaged-display-server.md)
moved its other display checks to Broadway for that reason), so there the
contract cannot reach OpenGL and prints `RHI render skipped: Xvfb is not
installed`. Its first gate run hid that line: level 0e shows only `OK` for
a passing contract. `verify.sh` level 0j now runs the whole sphere contract
and prints its verdicts, so the lab log says which parts ran. In the lab the
shader's look, `no-shader-error-fallback` and `dark-gate-opened-in-qml` stay
with the RHI render on a machine with Xvfb and with the hardware gate; the
manifest, source and software checks run there in full.
