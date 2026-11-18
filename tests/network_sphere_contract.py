#!/usr/bin/env python3
"""The glass network sphere: compiled shader, manifest and still form.

NetworkSphere.qml draws one network as a glass sphere. Where Qt renders
through RHI it runs shaders/sphere.frag.qsb in a ShaderEffect; it falls back
to its still form (SphereStill.qml, QtQuick Shapes and gradients) under the
software backend, when the effect reports an error (a missing or broken
.qsb), for a character outside the reviewed six, and when forceStill is set.

Checks, in order:

1. Manifest. tools/build-shaders.sh --check accepts the committed shaders and
   prints whether it rebuilt them byte for byte or why it skipped; fixtures
   in a temporary copy show that it refuses stale, missing, duplicated,
   unlisted and redirected inputs. `--manifest` stops here (verify.sh 0j).
2. Source. No colour literal, colour constructor or colour name in either
   component; no timer or animation; the shader's uniform block is exactly
   the reviewed one, `colour` is its only colour input, and `time` is read
   once, behind the lit gate.
3. Software render (QT_QUICK_BACKEND=software, what the runtime contracts
   use): every sphere chooses the still form, every one is drawn, the six
   characters differ lit and dark at three sizes, the colour follows its
   input, and a dark sphere ignores time.
4. RHI render (OpenGL on a private Xvfb display, Mesa llvmpipe), when Xvfb is
   installed: the shader form is chosen; forceStill, a missing and a corrupt
   .qsb choose the still form; a dark sphere ignores time and a lit one
   moves. Without Xvfb the contract says that it skipped this part.

`--sheet PATH` writes the software fixture sheet, `--rhi-sheet PATH` the
shader sheet (only when the RHI render runs).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from host_quickshell_qml_wiring_contract import strip_noise
from machine_sphere_contract import string_literals
from trust_pool_v3_generated_contract import png_pixels

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "roles/host_desktop_common/files/quickshell/hyperlab"
COMPONENT = QML / "NetworkSphere.qml"
STILL = QML / "SphereStill.qml"
SHADERS = QML / "shaders"
SOURCE = SHADERS / "sphere.frag"
COMPILED = SHADERS / "sphere.frag.qsb"
MANIFEST = SHADERS / "SHADERS.sha256"
BUILD = ROOT / "tools/build-shaders.sh"
PALETTE = ROOT / "themes/trust-model/rendered/hyperlab-palette-quickshell.json"

# character -> the network whose palette colour the fixture sheet uses.
CHARACTERS = ("host", "clean", "dev", "services", "dirty", "lab")
SIZES = (48, 96, 192)
# A sphere covers about pi * (1 / 2.4)^2 of its square; the still form must
# draw at least this share of it (halo excluded), or it reads as blank.
DRAWN_SHARE = 0.4
TIME0 = 3.0
TIME1 = 41.5

# Every quoted literal either component may contain. A colour name such as
# "white" or "transparent" is a refusal, not a default.
LITERALS = {
    COMPONENT.name: {"shaders/sphere.frag.qsb", "software", "forced", "shader-error",
                     "unknown-character", ""},
    STILL.name: set(),
}
UNIFORMS = (
    ("mat4", "qt_Matrix"), ("float", "qt_Opacity"), ("float", "time"), ("float", "lit"),
    ("float", "character"), ("float", "turn"), ("float", "selected"),
    ("float", "radiusShare"), ("float", "pixelRadius"), ("vec4", "colour"), ("vec2", "light"),
)
TIME_GATE = "float t = lit > 0.0 ? time : 0.0;"

SCENE = r'''
import QtQuick
import QtQuick.Window

Window {
    id: window
    visible: true
    width: @@WIDTH@@
    height: @@HEIGHT@@
    color: @@GROUND@@
    property var samples: []
    property int frame: 0
    Rectangle { anchors.fill: parent; color: @@GROUND@@ }
    Component { id: sphere; NetworkSphere {} }
    Component.onCompleted: {
        for (const row of @@ROWS@@) {
            const item = sphere.createObject(window.contentItem, {
                colour: row.colour, character: row.character, lit: row.lit,
                selected: row.selected || false, forceStill: row.forceStill || false,
                textureScale: row.textureScale || 1, turn: row.turn || 0,
                time: @@TIME0@@, x: row.x, y: row.y, width: row.size, height: row.size
            });
            if (!item) throw new Error("sphere did not instantiate");
            window.samples.push(item);
        }
        capture.start();
    }
    Timer {
        id: capture
        interval: 400
        onTriggered: {
            window.contentItem.grabToImage(function(result) {
                if (!result.saveToFile(@@OUTPUT@@ + window.frame + ".png"))
                    throw new Error("capture failed");
                window.frame += 1;
                if (window.frame < 2) {
                    for (const item of window.samples)
                        item.time = @@TIME1@@;
                    capture.start();
                    return;
                }
                console.log("SPHERES " + JSON.stringify({
                    api: window.contentItem.GraphicsInfo.api,
                    software: GraphicsInfo.Software, opengl: GraphicsInfo.OpenGL,
                    samples: window.samples.map(item => ({
                        still: item.stillForm, reason: item.stillReason,
                        width: item.width, height: item.height
                    }))
                }));
                Qt.quit();
            });
        }
    }
}
'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Network sphere contract: " + message)


# ---------------------------------------------------------------- manifest

def run_build(*arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    require(bash is not None, "bash is required")
    return subprocess.run(
        [str(bash), str(BUILD), *arguments], capture_output=True, text=True, check=False,
        timeout=300, env={**os.environ, **(env or {})},
    )


def report(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in (result.stdout + result.stderr).splitlines() if line.strip()]


def recorded_version() -> str:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    require(bool(lines) and lines[0].startswith("qsb "), "manifest has no qsb version line")
    return lines[0]


def local_qsb() -> str | None:
    found = shutil.which("qsb") or shutil.which("qsb", path="/usr/lib/qt6/bin")
    return found


def manifest_contract() -> list[str]:
    require(BUILD.is_file() and not BUILD.is_symlink(), "tools/build-shaders.sh is missing")
    for path in (SOURCE, COMPILED, MANIFEST):
        require(path.is_file() and not path.is_symlink(), f"{path.relative_to(ROOT)} is missing")
    result = run_build("--check")
    lines = report(result)
    require(result.returncode == 0, f"the committed shaders do not match their manifest: {lines[-6:]}")
    verdicts = [line for line in lines if line.startswith(("rebuild: ", "rebuild skipped: "))]
    require(len(verdicts) == 1, f"the check must say whether it rebuilt or why it skipped: {lines}")

    with tempfile.TemporaryDirectory(prefix="network-sphere-manifest-") as temporary:
        base = Path(temporary)

        def fixture(name: str) -> Path:
            target = base / name
            shutil.copytree(SHADERS, target)
            return target

        def refused(directory: Path, why: str, **env: str) -> None:
            outcome = run_build("--check", str(directory), env=env)
            require(outcome.returncode != 0, f"the shader check accepted {why}: {report(outcome)[-4:]}")

        stale = fixture("stale-source")
        (stale / "sphere.frag").write_text(SOURCE.read_text(encoding="utf-8") + "\n// edited\n",
                                           encoding="utf-8")
        refused(stale, "a source edited without a rebuild")

        compiled = fixture("stale-qsb")
        (compiled / "sphere.frag.qsb").write_bytes(COMPILED.read_bytes() + b"\0")
        refused(compiled, "a .qsb that is not the recorded one")

        missing = fixture("no-manifest")
        (missing / "SHADERS.sha256").unlink()
        refused(missing, "a missing manifest")

        absent = fixture("no-qsb")
        (absent / "sphere.frag.qsb").unlink()
        refused(absent, "a missing .qsb")

        duplicated = fixture("duplicated")
        text = (duplicated / "SHADERS.sha256").read_text(encoding="utf-8")
        (duplicated / "SHADERS.sha256").write_text(text + text.splitlines()[1] + "\n", encoding="utf-8")
        refused(duplicated, "a duplicated manifest line")

        unlisted = fixture("unlisted")
        shutil.copyfile(SOURCE, unlisted / "extra.frag")
        refused(unlisted, "a shader source the manifest does not list")

        redirected = fixture("redirected")
        (redirected / "sphere.frag.qsb").unlink()
        (redirected / "sphere.frag.qsb").symlink_to(COMPILED)
        refused(redirected, "a .qsb redirected through a symlink")

        unversioned = fixture("unversioned")
        lines_in = (unversioned / "SHADERS.sha256").read_text(encoding="utf-8").splitlines()
        (unversioned / "SHADERS.sha256").write_text("\n".join(lines_in[1:]) + "\n", encoding="utf-8")
        refused(unversioned, "a manifest without the qsb version")

        broken = base / "broken-qsb"
        broken.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
        broken.chmod(0o755)
        refused(SHADERS, "an HYPERLAB_QSB that does not run", HYPERLAB_QSB=str(broken))

        # A qsb of another version: the rebuild is skipped, and the check says so.
        other = base / "other-qsb"
        other.write_text("#!/bin/sh\nprintf 'qsb 0.0.0\\n'\n", encoding="utf-8")
        other.chmod(0o755)
        outcome = run_build("--check", env={"HYPERLAB_QSB": str(other)})
        require(outcome.returncode == 0 and any(
            line.startswith("rebuild skipped: ") and "qsb 0.0.0" in line for line in report(outcome)),
            f"a different qsb must skip the rebuild and say why: {report(outcome)}")

        # Where the recorded qsb exists, the rebuild must reproduce the bytes:
        # a manifest re-recorded over a stale .qsb is still a refusal.
        qsb = local_qsb()
        if qsb and subprocess.run([qsb, "--version"], capture_output=True, text=True,
                                  check=False).stdout.strip() == recorded_version():
            rerecorded = fixture("rerecorded")
            # A change the compiler sees; a comment would compile to the same bytes.
            source = SOURCE.read_text(encoding="utf-8")
            require(source.count("0.86 + 0.14 * fresnel") == 1, "the rebuild fixture lost its edit point")
            edited = source.replace("0.86 + 0.14 * fresnel", "0.85 + 0.14 * fresnel")
            (rerecorded / "sphere.frag").write_text(edited, encoding="utf-8")
            digest = subprocess.run(["sha256sum", "sphere.frag"], cwd=rerecorded, capture_output=True,
                                    text=True, check=True).stdout.split()[0]
            manifest = (rerecorded / "SHADERS.sha256").read_text(encoding="utf-8").splitlines()
            manifest = [f"{digest}  sphere.frag" if line.endswith("  sphere.frag") else line
                        for line in manifest]
            (rerecorded / "SHADERS.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
            refused(rerecorded, "a .qsb that the recorded qsb does not rebuild from its source")
        else:
            verdicts.append("manifest fixtures: the byte-identical refusal needs the recorded "
                            f"{recorded_version()}, not found here")
    return verdicts


# ------------------------------------------------------------------ source

def source_contract() -> None:
    for path in (COMPONENT, STILL):
        require(path.is_file() and not path.is_symlink(), f"{path.name} is missing")
        source = path.read_text(encoding="utf-8")
        require(not re.search(r"#[0-9a-fA-F]{3,8}\b", source), f"colour literal in {path.name}")
        stray = sorted(set(string_literals(source)) - LITERALS[path.name])
        require(not stray, f"literal outside the reviewed vocabulary in {path.name} (colour name?): {stray}")
        code = strip_noise(source)
        require(not re.search(r"\bQt\.(?:rgba?|hsla?|hsva?|color|tint)\s*\(", code),
                f"colour constructor bypasses the palette in {path.name}")
        require(not re.search(r"\b(?:Timer|FrameAnimation|Behavior|\w*Animation|AnimationController)\b",
                              code),
                f"{path.name} runs its own clock; time comes only from its parent")
        require(not re.search(r"\b(?:Process|FileView|MouseArea|TapHandler|States?)\s*\{", code),
                f"{path.name} presents its inputs; it observes, acts and changes state on nothing")
        require(not re.search(r"\bimport\s+Quickshell", code), f"{path.name} must not import host services")
    component = strip_noise(COMPONENT.read_text(encoding="utf-8"))
    require(re.search(r"\brequired\s+property\s+color\s+colour\b", component) is not None,
            "the colour must be a required input of NetworkSphere")
    require(len(re.findall(r"\bShaderEffect\s*\{", component)) == 1, "NetworkSphere has one ShaderEffect")

    shader = SOURCE.read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", shader, flags=re.S))
    require(code.lstrip().startswith("#version 440\n"), "the shader is Vulkan-style GLSL 440")
    require("gl_FragCoord" not in code and "gl_FragColor" not in code,
            "the shader works in qt_TexCoord0, one sphere per item")
    require(re.findall(r"layout\s*\(([^)]*)\)\s*(in|out)\s+(\w+)\s+(\w+)\s*;", code)
            == [("location = 0", "in", "vec2", "qt_TexCoord0"), ("location = 0", "out", "vec4", "fragColor")],
            "the shader's inputs and outputs are not qt_TexCoord0 and fragColor")
    blocks = re.findall(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*0\s*\)\s*uniform\s+buf\s*\{([^}]*)\}\s*;",
                        code)
    require(len(blocks) == 1 and code.count("uniform") == 1, "the shader has one std140 uniform block")
    members = tuple(tuple(member.split()) for member in blocks[0].split(";") if member.strip())
    require(members == UNIFORMS, f"the uniform block is not the reviewed one: {members}")
    body = code.replace(blocks[0], "")
    require(len(re.findall(r"\btime\b", body)) == 1 and body.count(TIME_GATE) == 1,
            "time is read once, behind the lit gate: a dark sphere is still")
    require(not re.search(r"\bt\s*=", body.replace(TIME_GATE, "")), "the gated clock is assigned once")


# ------------------------------------------------------------------ render

def prepare(directory: Path, *, qsb: bool = True, corrupt: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for path in (COMPONENT, STILL):
        shutil.copyfile(path, directory / path.name)
    (directory / "shaders").mkdir(exist_ok=True)
    shutil.copyfile(SOURCE, directory / "shaders" / SOURCE.name)
    target = directory / "shaders" / COMPILED.name
    target.unlink(missing_ok=True)
    if corrupt:
        target.write_bytes(b"\x00\x01not a qsb" * 64)
    elif qsb:
        shutil.copyfile(COMPILED, target)
    return directory


def render(directory: Path, rows: list[dict], ground: str, *, display: str | None = None,
           name: str = "capture") -> tuple[dict, list[bytes], int, int]:
    runner = shutil.which("qmlscene", path="/usr/lib/qt6/bin") or shutil.which("qmlscene6")
    require(bool(runner), "Qt 6 qmlscene is required")
    width = max(row["x"] + row["size"] for row in rows) + 4
    height = max(row["y"] + row["size"] for row in rows) + 4
    scene = SCENE
    for key, value in {
        "WIDTH": str(width), "HEIGHT": str(height), "GROUND": json.dumps(ground),
        "ROWS": json.dumps(rows), "OUTPUT": json.dumps(str(directory / name)),
        "TIME0": repr(TIME0), "TIME1": repr(TIME1),
    }.items():
        scene = scene.replace("@@" + key + "@@", value)
    path = directory / "check.qml"
    path.write_text(scene, encoding="utf-8")
    for frame in (0, 1):
        (directory / f"{name}{frame}.png").unlink(missing_ok=True)
    env = {key: value for key, value in os.environ.items()
           if key not in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QUICK_BACKEND", "QSG_RHI_BACKEND",
                          "QT_QPA_PLATFORM", "XAUTHORITY")}
    env.update({"QT_FORCE_STDERR_LOGGING": "1", "QML_DISABLE_DISK_CACHE": "1",
                "XDG_CACHE_HOME": str(directory / "cache")})
    if display is None:
        env.update({"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"})
    else:
        env.update({"QT_QPA_PLATFORM": "xcb", "QSG_RHI_BACKEND": "opengl", "DISPLAY": display,
                    "LIBGL_ALWAYS_SOFTWARE": "1"})
    result = subprocess.run([str(runner), str(path)], capture_output=True, text=True, check=False,
                            timeout=120, env=env)
    lines = (result.stdout + result.stderr).splitlines()
    records = [line.split("SPHERES ", 1)[1] for line in lines if "SPHERES " in line]
    # A missing or corrupt .qsb is expected to make Qt complain: that is the
    # case under test. Anything else is noise and a failure.
    noise = [line for line in lines if line.strip() and "SPHERES " not in line
             and not line.startswith(("qt.tools.qmlscene.deprecated:", "QStandardPaths:"))
             and not (display and re.match(
                 r"(qUncompress:|Attempted to deserialize QShader|ShaderEffect: |Failed to find shader)",
                 line))]
    require(result.returncode == 0 and len(records) == 1 and not noise,
            f"Qt execution failed ({result.returncode}): {noise[:4]}")
    images = [png_pixels(directory / f"{name}{frame}.png", (width, height)) for frame in (0, 1)]
    return json.loads(records[0]), images, width, height


def crop(image: bytes, width: int, row: dict) -> bytes:
    size = row["size"]
    return b"".join(image[((row["y"] + y) * width + row["x"]) * 3:
                          ((row["y"] + y) * width + row["x"] + size) * 3]
                    for y in range(size))


def drawn_share(picture: bytes, size: int, ground: bytes) -> float:
    """Share of the sphere's own disc (radius size / 2.4) that is not ground."""
    centre, radius = size / 2, size / 2.4
    inside = drawn = 0
    for y in range(size):
        for x in range(size):
            if (x + 0.5 - centre) ** 2 + (y + 0.5 - centre) ** 2 <= radius * radius:
                inside += 1
                offset = (y * size + x) * 3
                drawn += picture[offset:offset + 3] != ground
    return drawn / inside


def rgb(colour: str) -> bytes:
    require(re.fullmatch(r"#[0-9a-fA-F]{6}", colour) is not None, f"palette colour {colour!r}")
    return bytes(int(colour[index:index + 2], 16) for index in (1, 3, 5))


def sheet_rows(palette: dict, *, colour: str | None = None, extra: dict | None = None) -> list[dict]:
    """Six characters across, lit then dark, at every size."""
    rows, y = [], 4
    for size in SIZES:
        for lit in (1, 0):
            for character, network in enumerate(CHARACTERS):
                rows.append(dict(colour=colour or palette["dom_" + network], character=character,
                                 lit=lit, size=size, x=4 + character * (size + 8), y=y,
                                 turn=character * 1.3, **(extra or {})))
            y += size + 8
    return rows


def probe(palette: dict, x: int, character: int = 2, **extra: object) -> dict:
    """One 96-pixel lit dev sphere at x."""
    return {"colour": palette["dom_dev"], "character": character, "lit": 1, "size": 96,
            "x": x, "y": 4, **extra}


def check_sheet(rows: list[dict], frames: list[bytes], width: int, ground: bytes, where: str, *,
                moving_when_lit: bool) -> list[bytes]:
    first = [crop(frames[0], width, row) for row in rows]
    second = [crop(frames[1], width, row) for row in rows]
    for row, picture, later in zip(rows, first, second, strict=True):
        label = f"{where}: character {row['character']}, lit {row['lit']}, {row['size']} px"
        require(drawn_share(picture, row["size"], ground) >= DRAWN_SHARE, f"blank sphere: {label}")
        if row["lit"] == 0:
            require(picture == later, f"a dark sphere moved with time: {label}")
        elif moving_when_lit:
            require(picture != later, f"a lit sphere ignored time: {label}")
        else:
            require(picture == later, f"the still form moved: {label}")
    for size in SIZES:
        for lit in (1, 0):
            group = [picture for row, picture in zip(rows, first, strict=True)
                     if row["size"] == size and row["lit"] == lit]
            require(len(group) == len(CHARACTERS) and len(set(group)) == len(CHARACTERS),
                    f"{where}: two characters share one drawing at {size} px, lit {lit}")
    for index, row in enumerate(rows):
        if row["lit"] == 1:
            dark = next(i for i, other in enumerate(rows) if other["size"] == row["size"]
                        and other["lit"] == 0 and other["character"] == row["character"])
            require(first[index] != first[dark], f"{where}: lit and dark spheres look the same: {row}")
    return first


def software_contract(directory: Path, palette: dict, sheet: Path | None) -> None:
    ground = palette["base"]
    rows = sheet_rows(palette)
    record, frames, width, _ = render(directory, rows, ground)
    require(record["api"] == record["software"], f"the fixture is not the software backend: {record}")
    require(all(sample["still"] and sample["reason"] == "software" for sample in record["samples"]),
            f"the software backend must choose the still form: {record['samples'][:3]}")
    check_sheet(rows, frames, width, rgb(ground), "software", moving_when_lit=False)
    if sheet:
        shutil.copyfile(directory / "capture0.png", sheet)

    # The characters differ by their pattern, not only by their colour.
    single = sheet_rows(palette, colour=palette["dom_dev"])
    _, frames, width, _ = render(directory, single, ground)
    pictures = check_sheet(single, frames, width, rgb(ground), "one colour", moving_when_lit=False)

    # The colour is the input: another palette colour, another sphere; the
    # same colour, the same sphere.
    others = [palette["dom_" + network] for network in CHARACTERS if network != "dev"]
    require(palette["dom_dev"] not in others, "the fixture palette repeats the dev colour")
    shifted = [dict(row, colour=others[index % len(others)])
               for index, row in enumerate(single[:len(CHARACTERS)])]
    _, frames, width, _ = render(directory, shifted, ground)
    for row, base in zip(shifted, pictures, strict=False):
        require(crop(frames[0], width, row) != base, f"the colour input did not reach the drawing: {row}")

    # Selected, forced and unknown inputs.
    probes = [
        probe(palette, 4),
        probe(palette, 104, selected=True),
        probe(palette, 204, character=9),
        probe(palette, 304, character=-1),
        probe(palette, 404, textureScale=0.5),
    ]
    record, frames, width, _ = render(directory, probes, ground)
    plain, selected, unknown, negative, half = (crop(frames[0], width, row) for row in probes)
    require(plain != selected, "selected draws nothing")
    require(unknown == negative and unknown not in pictures,
            "a character outside the six must draw the same patternless dark sphere")
    require([sample["reason"] for sample in record["samples"]] ==
            ["software", "software", "unknown-character", "unknown-character", "software"],
            f"still form reasons: {record['samples']}")
    require(half == plain, "textureScale is a shader hook; the still form ignores it")


# --------------------------------------------------------------------- RHI

class PrivateDisplay:
    """An Xvfb server of our own, for an OpenGL (llvmpipe) RHI render."""

    def __init__(self, binary: str) -> None:
        reader, writer = os.pipe()
        self.process = subprocess.Popen(
            [binary, "-displayfd", str(writer), "-nolisten", "tcp", "-screen", "0", "1600x1200x24"],
            pass_fds=(writer,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        os.close(writer)
        with os.fdopen(reader) as stream:
            number = stream.readline().strip()
        require(number.isdigit(), "Xvfb did not report its display")
        self.display = ":" + number

    def close(self) -> None:
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=20)


def rhi_contract(directory: Path, palette: dict, sheet: Path | None) -> str:
    binary = shutil.which("Xvfb")
    if binary is None:
        return "RHI render skipped: Xvfb is not installed (the shader look stays with the hardware gate)"
    ground = palette["base"]
    screen = PrivateDisplay(binary)
    try:
        rows = sheet_rows(palette)
        record, frames, width, _ = render(prepare(directory / "rhi"), rows, ground, display=screen.display)
        if record["api"] != record["opengl"]:
            return f"RHI render skipped: Qt chose graphics API {record['api']}, not OpenGL"
        require(not any(sample["still"] for sample in record["samples"]),
                f"OpenGL must run the shader: {record['samples'][:3]}")
        check_sheet(rows, frames, width, rgb(ground), "shader", moving_when_lit=True)
        if sheet:
            shutil.copyfile(directory / "rhi" / "capture0.png", sheet)

        probes = [
            probe(palette, 4, forceStill=True),
            probe(palette, 104, textureScale=0.5),
        ]
        record, frames, width, _ = render(directory / "rhi", probes, ground, display=screen.display)
        require([(s["still"], s["reason"]) for s in record["samples"]] == [(True, "forced"), (False, "")],
                f"forceStill or textureScale: {record['samples']}")
        require(drawn_share(crop(frames[0], width, probes[1]), 96, rgb(ground)) >= DRAWN_SHARE,
                "the half-size layer drew nothing")

        for label, prepared in (("missing", prepare(directory / "missing", qsb=False)),
                                ("corrupt", prepare(directory / "corrupt", corrupt=True))):
            record, frames, width, _ = render(prepared, rows[:len(CHARACTERS)], ground,
                                              display=screen.display)
            require(all(s["still"] and s["reason"] == "shader-error" for s in record["samples"]),
                    f"a {label} .qsb must choose the still form: {record['samples']}")
            for row in rows[:len(CHARACTERS)]:
                require(drawn_share(crop(frames[0], width, row), row["size"], rgb(ground)) >= DRAWN_SHARE,
                        f"a {label} .qsb left a blank sphere: {row}")
    finally:
        screen.close()
    return "RHI render: OpenGL shader form, fallbacks and the lit gate checked"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="store_true", help="check the compiled shaders only")
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--rhi-sheet", type=Path)
    args = parser.parse_args()

    verdicts = manifest_contract()
    if args.manifest:
        for line in verdicts:
            print(line)
        print("Network sphere contract: OK (compiled shaders match their manifest)")
        return 0
    source_contract()
    palette = json.loads(PALETTE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="network-sphere-") as temporary:
        directory = Path(temporary)
        software_contract(prepare(directory / "software"), palette, args.sheet)
        verdicts.append(rhi_contract(directory, palette, args.rhi_sheet))
    for line in verdicts:
        print(line)
    print("Network sphere contract: OK (manifest, palette-only colour, still form under the "
          "software backend, six characters, dark spheres ignore time)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
