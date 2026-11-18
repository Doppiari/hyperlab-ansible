#!/usr/bin/env python3
"""Terminal domain dots follow the palette and preserve every pipe byte."""

from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/hyperlabctl"
sys.path.insert(0, str(TOOL))

from hyperlabctl import cli
from hyperlabctl.commands import machine
from hyperlabctl.errors import Unavailable
from hyperlabctl.render import DomainSpheres, _nearest_256

DOMAINS = ("clean", "dev", "services", "dirty", "lab")
COMMANDS = (("vm", "list"), ("machine", "list"), ("net", "list"), ("trust",))
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
# SHA-256 of the existing UTF-8 text on this fixed, provider-independent fixture.
PIPE_DIGESTS = {
    ("vm", "list"): "faca2883097c04da494c1550c029f21062a65570b94151fb464cd9c89e300c51",
    ("machine", "list"): "1ff63178b3dc9ffc198fac9d23988a31c29b7cb453f69f33efb86c71a27ebbef",
    ("net", "list"): "7de6122c0f7bbd4312608ae3bafdf185dc3361af0b73c8e973874eb2f119df5b",
    ("trust",): "fac41f48c5100adcf539cb5bcff69f59baca75c95d60f6e6a190a29f65c20538",
}
# Legacy net status paint already occupies the state field's padding on a TTY.
NET_TTY_BODY_DIGEST = "f4c400ee743ef4c502db2338c139a5c2e0b8ad60b724f5a5fc87a2a9a8de97f6"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Output(io.StringIO):
    def __init__(self, terminal: bool) -> None:
        super().__init__()
        self.terminal = terminal

    def isatty(self) -> bool:
        return self.terminal


def fixture() -> tuple[list[dict], dict]:
    records, runtime = [], []
    for index, domain in enumerate((*DOMAINS, "dev")):
        name = f"sample-{index}"
        record = {
            "id": name, "display_name": name, "lifecycle": "permanent",
            "device_capability": "standard", "network_profile": domain,
            "gpu_handoff_profile": None, "resources": {"memory_mb": 512, "vcpus": 1},
            "image": {"id": "sample", "sha256": "a" * 64},
            "template": {"id": "sample", "version": "1"},
        }
        records.append(record)
        runtime.append({
            "name": name, "state": "running" if index % 2 else "shut off",
            "memory_mb": 512, "vcpus": 1, "network": domain, "networks": [domain],
            "managed": True, "product_managed": True, "vfio": False,
            "lifecycle": "permanent", "device_profile": "standard",
            "network_profile": domain, "trust_profile": domain if index < 5 else None,
            "gpu_handoff_profile": None, "gpu_trust_profile": None,
            "gpu_policy_state": "not-required", "image": "sample",
            "image_sha256": "a" * 64,
            "blocked": {"short_mb": 128} if index == 5 else None,
        })
    external = dict(runtime[0], name="external", managed=False, product_managed=False,
                    trust_profile="clean", trust_source="gpu-domain-profile")
    runtime.append(external)
    built = {
        "domains": runtime, "gpu": {"held_by": None},
        "trust": {"claimed": True, "level": 2, "name": "dev",
                  "ladder": {"clean": 3, "dev": 2, "dirty": 1, "lab": 0}},
        "networks": {"missing": [], "inactive": ["lab"]}, "problems": [],
    }
    return records, built


def invoke(root: Path, argv: tuple[str, ...], *, terminal: bool = False,
           environ: dict[str, str] | None = None,
           registry_error: bool = False,
           runtime_state: str = "observed") -> tuple[int, str, str]:
    records, built = fixture()
    if runtime_state == "unavailable":
        built["domains"] = None
    elif runtime_state == "not-created":
        built["domains"] = []
    else:
        require(runtime_state == "observed", "unknown runtime fixture")
    registry_failure = None
    if registry_error:
        registry_failure = Unavailable("unreadable registry")
        if argv[:2] == ("machine", "list"):
            # Listing intent succeeds; the extra provenance read fails.
            registry_failure = [copy.deepcopy(records), registry_failure]
    variables = {
        "network_domains": [{"name": name} for name in (*DOMAINS, "unclassified")],
        "gpu_trust_levels": built["trust"]["ladder"],
    }
    ctx = SimpleNamespace(
        config=SimpleNamespace(repo_root=root, var=lambda name, default: variables.get(name, default)),
        environ={"TERM": "xterm-256color", "COLORTERM": "truecolor"}
        if environ is None else environ,
        # net list reads each live definition; here libvirt never answers,
        # so gateway and DHCP are reported unknown.
        virsh=lambda *args: SimpleNamespace(ok=False, stdout="", stderr="libvirt unavailable"),
    )
    output, errors = Output(terminal), io.StringIO()
    with (patch("hyperlabctl.document.build", return_value=copy.deepcopy(built)),
          patch.object(machine, "list_machines", return_value=copy.deepcopy(records),
                       side_effect=registry_failure),
          redirect_stdout(output), redirect_stderr(errors)):
        try:
            code = cli.main(list(argv), ctx=ctx)
        except SystemExit as exc:
            code = exc.code
    return code, output.getvalue(), errors.getvalue()


def rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[start:start + 2], 16) for start in (1, 3, 5))


def indexed_colour(index: int) -> tuple[int, int, int]:
    if index >= 232:
        return (8 + 10 * (index - 232),) * 3
    value = index - 16
    steps = (0, 95, 135, 175, 215, 255)
    return steps[value // 36], steps[value // 6 % 6], steps[value % 6]


def prefix(palette: dict, domain: str | None, truecolor: bool) -> str:
    if domain not in DOMAINS:
        return "○ "
    colour = rgb(palette["domains"]["dom_" + domain])
    if truecolor:
        opening = "\x1b[38;2;%d;%d;%dm" % colour
    else:
        nearest = min(range(16, 256), key=lambda index: sum(
            (actual - target) ** 2
            for actual, target in zip(indexed_colour(index), colour, strict=True)))
        opening = f"\x1b[38;5;{nearest}m"
    return opening + "●\x1b[0m "


def literal_contract() -> None:
    # The existing status-tone table is unrelated to semantic domain identity.
    legacy = {"ok": "\x1b[32m", "warn": "\x1b[33m", "error": "\x1b[31m",
              "dim": "\x1b[90m", "off": "\x1b[0m"}
    paths = [TOOL / "hyperlabctl" / filename for filename in
             ("cli.py", "render.py", "commands/vm.py", "commands/machine.py",
              "commands/net.py", "commands/trust.py")]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (path.name == "render.py" and isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "COLORS"
                            for target in node.targets)):
                require(ast.literal_eval(node.value) == legacy, "status tones changed")
                node.value = ast.Constant(None)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                require(re.search(r"#[0-9a-fA-F]{6}\b", node.value) is None
                        and ESCAPE.search(node.value) is None,
                        f"typed colour in CLI: {path.relative_to(ROOT)}:{node.lineno}")


def output_contract(root: Path, palette: dict) -> None:
    identities = {
        ("vm", "list"): [*DOMAINS, None, None],
        ("machine", "list"): [*DOMAINS, None],
        ("net", "list"): [*DOMAINS, None],
        ("trust",): ["clean", "dev", "dirty", "lab"],
    }
    for option in ("--color=sometimes", "--color"):
        code, output, errors = invoke(root, ("net", "list", option))
        require(code == 2 and not output and "--color" in errors,
                f"invalid colour option accepted: {option}")
    for command in COMMANDS:
        code, plain, errors = invoke(root, command)
        require(code == 0 and not errors, f"pipe command failed: {command}: {errors}")
        require(hashlib.sha256(plain.encode()).hexdigest() == PIPE_DIGESTS[command],
                f"pipe bytes changed: {command}")
        for options in ((), ("--color=auto",), ("--color=always",), ("--color=never",),
                        ("--no-color",)):
            code, output, errors = invoke(root, (*command, *options))
            require(code == 0 and not errors and output == plain and "\x1b" not in output
                    and "●" not in output and "○" not in output,
                    f"pipe colour or changed bytes: {command} {options}: {errors}")
        for environment in ({"TERM": "xterm-256color", "NO_COLOR": ""},
                            {"TERM": "dumb"}):
            code, output, errors = invoke(root, command, terminal=True, environ=environment)
            require(code == 0 and output == plain and not errors,
                    f"auto environment suppression: {command} {environment}")
        for options in (("--color=never",), ("--no-color",),
                        ("--color=always", "--no-color"),
                        ("--no-color", "--color=never")):
            code, output, errors = invoke(root, (*command, *options), terminal=True)
            require(code == 0 and output == plain and not errors,
                    f"never/alias suppression: {command} {options}")
        for environment, truecolor in (({"COLORTERM": "truecolor"}, True),
                                       ({"COLORTERM": "24bit"}, True),
                                       ({"TERM": "xterm-256color"}, False)):
            code, output, errors = invoke(root, command, terminal=True, environ=environment)
            require(code == 0 and not errors, f"terminal command failed: {command}: {errors}")
            actual, expected = output.splitlines(), plain.splitlines()
            offset = 1 if command == ("trust",) else 0
            require(actual[:offset] == expected[:offset] and len(actual) == len(expected),
                    f"heading or row count changed: {command}")
            bodies = actual[:offset]
            for index, domain in enumerate(identities[command], start=offset):
                marker = prefix(palette, domain, truecolor)
                require(actual[index].startswith(marker),
                        f"domain prefix: {command} row {index}: {actual[index]!r}")
                body = actual[index][len(marker):]
                body = ESCAPE.sub("", body)
                require(body.split() == expected[index].split(),
                        f"row body changed: {command} row {index}")
                bodies.append(body)
            digest = hashlib.sha256(("\n".join(bodies) + "\n").encode()).hexdigest()
            require(digest == (NET_TTY_BODY_DIGEST if command == ("net", "list")
                               else PIPE_DIGESTS[command]), f"terminal row spacing: {command}")
        for options in (("--color=always",), ("--no-color", "--color", "always")):
            code, output, errors = invoke(root, (*options, *command), terminal=True,
                                          environ={"TERM": "dumb", "NO_COLOR": ""})
            require(code == 0 and "●" in output and not errors,
                    f"explicit TTY always override: {command} {options}")
        code, plain_json, errors = invoke(root, (*command, "--json"))
        require(code == 0 and not errors, f"JSON command failed: {command}")
        json.loads(plain_json)
        code, tty_json, errors = invoke(root, (*command, "--json", "--color=always"), terminal=True)
        require(code == 0 and tty_json == plain_json and "\x1b" not in tty_json and not errors,
                f"JSON decoration: {command}")

    for command in (("vm", "list"), ("machine", "list")):
        code, output, errors = invoke(root, command, terminal=True, registry_error=True)
        require(code == 0 and not errors and output
                and all(line.startswith("○ ") for line in output.splitlines()),
                f"unknown membership gained an identity: {command}")
    code, output, errors = invoke(root, ("vm", "list"), registry_error=True)
    require(code == 0 and not errors and hashlib.sha256(output.encode()).hexdigest()
            == PIPE_DIGESTS[("vm", "list")], "pipe depends on registry membership")
    for state in ("unavailable", "not-created"):
        code, output, errors = invoke(root, ("machine", "list"), terminal=True,
                                      runtime_state=state)
        require(code == 0 and not errors and len(output.splitlines()) == len(fixture()[0])
                and all(line.startswith("○ ") for line in output.splitlines()),
                f"unconfirmed Machine runtime gained an identity: {state}")


def read_boundary_contract(root: Path) -> None:
    for command in (("vm", "list"), ("machine", "list")):
        for terminal, options, environment in (
            (False, (), {}),
            (False, ("--color=always",), {}),
            (True, ("--color=never",), {}),
            (True, ("--no-color",), {}),
            (True, (), {"NO_COLOR": ""}),
            (True, (), {"TERM": "dumb"}),
            (True, ("--json", "--color=always"), {}),
        ):
            with patch.object(machine, "build_product_inventory",
                              side_effect=AssertionError("plain output read product inventory")):
                code, output, errors = invoke(root, (*command, *options), terminal=terminal,
                                              environ=environment)
            require(code == 0 and output and not errors,
                    f"plain output failed: {command} {options}")
    for command in COMMANDS:
        with patch("hyperlabctl.render._domain_palette",
                   side_effect=AssertionError("JSON read the domain palette")):
            code, output, errors = invoke(root, (*command, "--json", "--color=always"),
                                          terminal=True)
        require(code == 0 and not errors, f"JSON read boundary failed: {command}")
        json.loads(output)


def unsafe_palette_contract(root: Path, original: str) -> None:
    path = root / "tools/palette/palette.yml"
    palette = yaml.safe_load(original)
    malformed = [original + "domains: {}\n", original.replace("  dom_dev:", "  dom_clean:"),
                 original + yaml.safe_dump({"domains": palette["domains"]}),
                 original.replace("variants:\n", "  dom_dev: "
                                  + repr(palette["domains"]["dom_dev"]) + "\nvariants:\n", 1),
                 yaml.safe_dump({**palette, "domains": {"dom_dev": "#123456"}}),
                 yaml.safe_dump({**palette, "domains": {**palette["domains"],
                                                       "dom_unknown": palette["domains"]["dom_dev"]}}),
                 original.replace("'#5b8cff'", "'invalid'", 1),
                 original.replace("  dom_clean: '#72f2a5'", "  dom_clean: &clean '#72f2a5'")
                 .replace("  dom_dev: '#5b8cff'", "  dom_dev: *clean"),
                 "[]\n", "domains: [\n", "? [ambiguous, key]\n: value\n"]
    for text in malformed:
        path.write_text(text, encoding="utf-8")
        code, output, errors = invoke(root, ("net", "list"), terminal=True)
        require(code == 2 and not output and "palette" in errors,
                "ambiguous/incomplete palette was accepted")
    path.write_text(original, encoding="utf-8")
    for mode in ("unreadable", "missing", "symlink", "parent-symlink"):
        moved = path.with_suffix(".saved")
        directory = path.parent
        if mode == "unreadable":
            path.chmod(0)
        elif mode == "parent-symlink":
            directory.rename(directory.with_name("palette-saved"))
            directory.symlink_to("palette-saved", target_is_directory=True)
        else:
            path.rename(moved)
            if mode == "symlink":
                path.symlink_to(moved.name)
        try:
            code, output, errors = invoke(root, ("net", "list"), terminal=True)
            require(code == 2 and not output and "palette" in errors,
                    f"unsafe palette accepted: {mode}")
            code, output, errors = invoke(root, ("net", "list"))
            require(code == 0 and not errors and hashlib.sha256(output.encode()).hexdigest()
                    == PIPE_DIGESTS[("net", "list")], f"pipe depends on palette: {mode}")
        finally:
            if mode == "unreadable":
                path.chmod(0o644)
            elif mode == "parent-symlink":
                directory.unlink()
                directory.with_name("palette-saved").rename(directory)
            else:
                if mode == "symlink":
                    path.unlink()
                moved.rename(path)


def main() -> int:
    literal_contract()
    require(_nearest_256((13, 13, 13)) == 232, "256 colour tie did not choose lowest index")
    original = (ROOT / "tools/palette/palette.yml").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="cli-spheres-") as temporary:
        root = Path(temporary)
        path = root / "tools/palette/palette.yml"
        path.parent.mkdir(parents=True)
        path.write_text(original, encoding="utf-8")
        palette = yaml.safe_load(original)
        spheres = DomainSpheres(root, True, {"COLORTERM": "truecolor"})
        for domain in ("host", "Host", "HOST", "Dev", "external", "unclassified", None):
            require(spheres.prefix(domain) == "○ ", f"reserved/noncanonical domain coloured: {domain}")
        read_boundary_contract(root)
        output_contract(root, palette)
        shifted = copy.deepcopy(palette)
        for index, domain in enumerate(DOMAINS):
            shifted["domains"]["dom_" + domain] = palette["domains"][
                "dom_" + DOMAINS[(index + 1) % len(DOMAINS)]]
        path.write_text(yaml.safe_dump(shifted), encoding="utf-8")
        output_contract(root, shifted)
        unsafe_palette_contract(root, original)
    print("CLI domain spheres contract: OK (TTY dots, palette, RGB/256, plain pipes/JSON)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
