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
