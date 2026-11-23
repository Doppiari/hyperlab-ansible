#!/usr/bin/env python3
"""Exercise installed-path XML preflight on isolated hook and policy fixtures."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/hyperlabctl"))

from hyperlabctl.machine_factory import (  # noqa: E402
    materialize_machine,
    write_projected_vm_spec,
)

ROLE = ROOT / "roles/gpu_handoff"
QEMU = "http://libvirt.org/schemas/domain/qemu/1.0"
PLAIN = "<domain type='kvm'><name>ordinary</name><devices/></domain>"
VFIO = """<domain type='kvm'><name>arch-dev-vfio</name><devices>
<hostdev managed='yes' type = "pci" mode='subsystem'>
<source><address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/></source>
</hostdev></devices></domain>"""


class HookFixture:
    """Copy production artifacts; substitute only fixed paths and fixture uid."""

    def __init__(self, directory: Path, policy: str | None = None) -> None:
        self.root = directory
        self.state = directory / "state"
        self.helper = directory / "xml-preflight.py"
        # The policy has its own parent so that a redirected directory can be
        # substituted without touching the fixture's other inputs.
        self.policy_dir = directory / "policy"
        self.policy_dir.mkdir()
        self.policy = self.policy_dir / "looking-glass.json"
        self.hook = directory / "qemu"
        source = (ROLE / "files/qemu").read_text()
        for installed, fixture in (
            ("/etc/gpu-handoff/xml-preflight.py", self.helper),
            ("/etc/gpu-handoff/looking-glass.json", self.policy),
        ):
            assert source.count(installed) == 1, f"hook does not invoke fixed installed path {installed} once"
            source = source.replace(installed, str(fixture))
        self.hook.write_text(source)
        self.hook.chmod(0o755)
        source = (ROLE / "files/xml-preflight.py").read_text()
        assert source.count("POLICY_OWNER = 0") == 1
        self.helper.write_text(source.replace("POLICY_OWNER = 0", f"POLICY_OWNER = {os.getuid()}"))
        self.policy.write_text(policy or '{"device":"/dev/kvmfr0","size_bytes":67108864}\n')
        self.policy.chmod(0o644)
        (directory / "domains").write_text("arch-dev-vfio dev\n")
        (directory / "rotation").write_text("clean 3\ndev 2\ndirty 1\nlab 0\n")
        (directory / "domains.d").mkdir()
        self.env = {
            **os.environ,
            "GPU_HANDOFF_DOMAINS": str(directory / "domains"),
            "GPU_HANDOFF_ROTATION": str(directory / "rotation"),
            "GPU_HANDOFF_MANAGED_DIR": str(directory / "domains.d"),
            "GPU_HANDOFF_STATE_DIR": str(self.state),
        }

    def run(self, xml: str, domain: str = "arch-dev-vfio", phase: str = "prepare") -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.hook), domain, phase], input=xml, text=True,
                              capture_output=True, check=False, timeout=10, env=self.env)

    def reset_state(self, seeded: bool) -> None:
        if self.state.exists():
            shutil.rmtree(self.state)
        if seeded:
            self.state.mkdir()
            (self.state / "trust").write_bytes(b"3\n")

    def refuses(self, xml: str, reason: str, domain: str = "arch-dev-vfio") -> None:
        for seeded in (False, True):
            self.reset_state(seeded)
            result = self.run(xml, domain)
            assert result.returncode == 1 and reason in result.stderr, (
                f"{reason}: seeded={seeded}: {result.returncode}: {result.stderr}"
            )
            if seeded:
                assert (self.state / "trust").read_bytes() == b"3\n", "refusal changed trust bytes"
                assert sorted(p.name for p in self.state.iterdir()) == ["trust"], "preflight touched ladder"
            else:
                assert not self.state.exists(), "preflight refusal created ladder state"


def installation() -> str:
    """Evaluate the real Ansible task arguments and shared templated limits."""
    loader = DataLoader()
    variables = loader.load_from_file(str(ROOT / "group_vars/all/looking-glass.yml"))
    variables = {key: trust_as_template(value) if isinstance(value, str) else value
                 for key, value in variables.items()}
    templar = Templar(loader=loader, variables=variables)
    tasks = loader.load_from_file(str(ROLE / "tasks/main.yml"))
    operations: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, task in enumerate(tasks):
        for action in ("ansible.builtin.file", "ansible.builtin.copy", "ansible.builtin.template"):
            if action in task:
                args = templar.template(task[action])
                destination = args.get("dest", args.get("path"))
                assert destination not in operations, f"duplicate install destination {destination}"
                assert not task.get("when"), f"conditional XML policy installation: {task['name']}"
                operations[destination] = (index, args)
    for destination, mode in (
        ("/etc/gpu-handoff", "0755"),
        ("/etc/gpu-handoff/xml-preflight.py", "0644"),
        ("/etc/gpu-handoff/looking-glass.json", "0644"),
        ("/etc/libvirt/hooks/qemu", "0755"),
    ):
        assert destination in operations, f"missing installation: {destination}"
        args = operations[destination][1]
        assert (args["owner"], args["group"], args["mode"]) == ("root", "root", mode), args
    hook_index, hook_args = operations["/etc/libvirt/hooks/qemu"]
    helper_index, helper_args = operations["/etc/gpu-handoff/xml-preflight.py"]
    policy_index, policy_args = operations["/etc/gpu-handoff/looking-glass.json"]
    assert helper_index < hook_index and policy_index < hook_index, "hook published before prerequisites"
    assert hook_args["src"] == "qemu" and helper_args["src"] == "xml-preflight.py"
    env = Environment(loader=FileSystemLoader(str(ROLE / "templates")),
                      undefined=StrictUndefined, autoescape=False)
    # Render through Ansible too: the size expression is nested configuration,
    # not a literal test-only 64 MiB constant.
    template = env.loader.get_source(env, policy_args["src"])[0]
    rendered = templar.template(trust_as_template(template))
    assert json.loads(rendered) == {"device": "/dev/kvmfr0", "size_bytes": 67108864}
    for width, height, device, size in ((3840, 2160, "/dev/kvmfr1", 128 * 1048576),):
        changed = {**variables, "hyperlab_looking_glass_width": width,
                   "hyperlab_looking_glass_height": height, "hyperlab_looking_glass_device": device}
        actual = Templar(loader=loader, variables=changed).template(trust_as_template(template))
        assert json.loads(actual) == {"device": device, "size_bytes": size}, "transport policy is hard-coded"
    return rendered


def reviewed_xml() -> str:
    # Pinned to the existing template's four literal argv values. The reference
    # template itself is rendered and exercised by the hardware-gate contract.
    root = ET.fromstring(VFIO)
    block = ET.SubElement(root, f"{{{QEMU}}}commandline")
    for value in (
        "-device", "{'driver':'ivshmem-plain','id':'shmem0','memdev':'looking-glass'}",
        "-object", "{'qom-type':'memory-backend-file','id':'looking-glass',"
        "'mem-path':'/dev/kvmfr0','size':67108864,'share':true}",
    ):
        ET.SubElement(block, f"{{{QEMU}}}arg", {"value": value})
    return ET.tostring(root, encoding="unicode")


def template_domain_xml(directory: Path, transport: dict[str, Any]) -> tuple[str, str, str]:
    """Render a workstation-dev-standard Machine through the product path.

    ADR 0019 selects this Template for the first GPU lease; its default run
    is without the GPU. The Template stays draft and its image unsealed in
    the tree, so a copy marks both ready only to let the real Machine factory,
    VM spec projection, guest planner and domain template produce the XML
    that libvirt would hand the hook at prepare.
    """
    for name in ("images", "templates", "vm-specs", "group_vars", "schemas"):
        shutil.copytree(ROOT / name, directory / name,
                        ignore=shutil.ignore_patterns(".generated"))
    template_path = directory / "templates/workstation-dev-standard.yml"
    template = yaml.safe_load(template_path.read_text())
    assert template["presentation"]["looking_glass_mode"] == "disabled", template
    assert template["defaults"]["gpu_handoff_profile"] is None, template
    template["status"] = "ready"
    template_path.write_text(yaml.safe_dump(template, sort_keys=False))
    image_path = directory / f"images/{template['image']}.yml"
    image = yaml.safe_load(image_path.read_text())
    image.update(status="sealed", sha256="a" * 64, source_sha256="a" * 64)
    image_path.write_text(yaml.safe_dump(image, sort_keys=False))
    machine = materialize_machine(directory, template_id="workstation-dev-standard",
                                  machine_id="dev-02", owner="hyperlab",
                                  created_at="2026-11-22T00:00:00Z")
    assert machine["gpu_handoff_profile"] is None, machine
    spec = importlib.util.spec_from_file_location("guest_plan_for_hook", ROOT / "tools/guest_plan.py")
    assert spec is not None and spec.loader is not None
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    plan = planner.build_plan(directory, write_projected_vm_spec(directory, machine),
                              directory / "store")
    assert plan["device_profile"] == "standard" and not plan["looking_glass"], plan
    env = Environment(loader=FileSystemLoader(str(ROOT / "roles/guest/templates")),
                      undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    xml = env.get_template("domain.xml.j2").render(guest_plan=plan, guest_resolved_memory_mb=4096,
                                                   guest_vfio={})
    # Compatibility guard, not a lease shape: ADR 0019's two-shape planner is
    # unbuilt. The same Machine identity is rendered by the same template with
    # the VFIO branch and the reviewed Looking Glass block, its transport taken
    # from the host policy, so the hook's acceptance of the reviewed argv can
    # never depend on the reference domain's name.
    looking = yaml.safe_load((ROOT / "group_vars/all/looking-glass.yml").read_text())
    vfio = {
        "cpu_pinning": {"enabled": False},
        "devices": [{"xml_domain": "0x0000", "xml_bus": "0x01", "xml_slot": "0x00",
                     "xml_function": function} for function in ("0x0", "0x1")],
        "looking_glass_device": transport["device"],
        "looking_glass_shm_bytes": transport["size_bytes"],
    }
    with_gpu = env.get_template("domain.xml.j2").render(
        guest_plan={**plan, "device_profile": "vfio", "looking_glass": True},
        guest_resolved_memory_mb=4096, guest_vfio=vfio,
        hyperlab_looking_glass_spice_socket_dir=looking["hyperlab_looking_glass_spice_socket_dir"])
    return plan["name"], xml, with_gpu


def main() -> None:
    policy = installation()
    with tempfile.TemporaryDirectory() as temporary:
        fixture = HookFixture(Path(temporary), policy)
        xml = reviewed_xml()
        for valid in (VFIO, xml, xml.replace("ns0:", "renamed:").replace("xmlns:ns0", "xmlns:renamed")):
            fixture.reset_state(False)
            result = fixture.run(valid)
            assert result.returncode == 0, f"reviewed XML refused: {result.stderr}"
            assert (fixture.state / "trust").read_bytes() == b"2\n"
        fixture.policy.write_text('{"device":"/dev/kvmfr1","size_bytes":134217728}\n')
        configured_xml = xml.replace("/dev/kvmfr0", "/dev/kvmfr1").replace("67108864", "134217728")
        fixture.reset_state(False)
        result = fixture.run(configured_xml)
        assert result.returncode == 0, f"configured Looking Glass XML refused: {result.stderr}"
        assert (fixture.state / "trust").read_bytes() == b"2\n"
        fixture.refuses(xml, "unreviewed QEMU command-line")
        fixture.policy.write_text(policy)
        for seeded in (False, True):
            fixture.reset_state(seeded)
            result = fixture.run(PLAIN, "ordinary")
            assert result.returncode == 0, result.stderr
            if seeded:
                assert (fixture.state / "trust").read_bytes() == b"3\n"
            else:
                assert not fixture.state.exists()
        fixture.refuses(xml.replace("arch-dev-vfio", "ordinary"),
                        "QEMU command-line without a reviewed GPU handoff policy", "ordinary")
        for before, after in (
            ("ivshmem-plain", "vfio-pci"),
            ("/dev/kvmfr0", "/tmp/unreviewed"),
            ("67108864", "134217728"),
            ("'share':true", "'share':false"),
            ("'memdev':'looking-glass'", "'memdev':'other'"),
            ("'id':'looking-glass'", "'id':'other'"),
            ("'share':true", "'share':true,'host-nodes':[0]"),
            ("-object", "-chardev"),
        ):
            fixture.refuses(xml.replace(before, after), "unreviewed QEMU command-line")
        sentinel = fixture.root / "executed"
        payload = ET.fromstring(xml)
        payload.find(f"{{{QEMU}}}commandline")[1].set("value", f"$(touch {sentinel})")
        fixture.refuses(ET.tostring(payload, encoding="unicode"), "unreviewed QEMU command-line")
        assert not sentinel.exists(), "XML argument was executed"
        for extra in (
            f'<x:arg xmlns:x="{QEMU}" value="-device"/>',
            f'<x:arg xmlns:x="{QEMU}" value="vfio-pci,host=01:00.0"/>',
            f'<x:env xmlns:x="{QEMU}" name="LD_PRELOAD" value="/tmp/unreviewed"/>',
        ):
            bad = ET.fromstring(xml)
            bad.find(f"{{{QEMU}}}commandline").append(ET.fromstring(extra))
            fixture.refuses(ET.tostring(bad, encoding="unicode"), "unreviewed QEMU command-line")
        for change in ("empty", "attribute", "arg-attribute", "arg-child", "arg-text", "orphan"):
            bad = ET.fromstring(xml)
            block = bad.find(f"{{{QEMU}}}commandline")
            if change == "empty":
                block.clear()
            elif change == "attribute":
                block.set("unexpected", "yes")
            elif change == "arg-attribute":
                block[0].set("unexpected", "yes")
            elif change == "arg-child":
                ET.SubElement(block[0], "unexpected")
            elif change == "arg-text":
                block[0].text = "unexpected"
            else:
                bad.append(ET.Element(f"{{{QEMU}}}env", {"name": "UNREVIEWED", "value": "1"}))
            fixture.refuses(ET.tostring(bad, encoding="unicode"), "unreviewed QEMU command-line")
        bad = ET.fromstring(xml)
        bad.append(ET.fromstring(xml).find(f"{{{QEMU}}}commandline"))
        fixture.refuses(ET.tostring(bad, encoding="unicode"), "unreviewed QEMU command-line")
        for broken in ("", "<domain>", "<domain/><domain/>", "<not-domain/>",
                       "<!DOCTYPE domain [<!ENTITY name 'arch-dev-vfio'>]><domain><name>&name;</name></domain>"):
            fixture.refuses(broken, "invalid domain XML")
        fixture.refuses("<domain><name>arch-dev-vfio</name>" + " " * (1024 * 1024) + "</domain>",
                        "invalid domain XML")
        fixture.refuses(VFIO.replace("arch-dev-vfio", "other"), "domain name mismatch")
        for broken in ('{}', '{"device":"/dev/kvmfr0","device":"/dev/kvmfr0","size_bytes":67108864}',
                       '{"device":"/dev/kvmfr0","size_bytes":true}',
                       '{"device":"/dev/kvmfr0","size_bytes":67108864,"extra":0}', 'not JSON'):
            fixture.policy.write_text(broken)
            fixture.refuses(xml, "invalid Looking Glass policy")
        fixture.policy.write_text(policy)
        helper_source = fixture.helper.read_text()
        fixture.helper.write_text(helper_source.replace(f"POLICY_OWNER = {os.getuid()}",
                                                       f"POLICY_OWNER = {os.getuid() + 1}"))
        fixture.refuses(xml, "unsafe Looking Glass policy")
        fixture.helper.write_text(helper_source)
        for mode in (0o000, 0o666):
            fixture.policy.chmod(mode)
            fixture.refuses(xml, "unsafe Looking Glass policy")
        fixture.policy.chmod(0o644)
        fixture.policy.rename(fixture.root / "redirected.json")
        fixture.policy.symlink_to(fixture.root / "redirected.json")
        fixture.refuses(xml, "Looking Glass policy")
        fixture.policy.unlink()
        fixture.refuses(VFIO, "Looking Glass policy")
        fixture.policy.write_text(policy)
        fixture.policy.chmod(0o644)
        # The root hook runs the helper isolated: neither the environment nor
        # the helper's own directory may supply a module it imports.
        shadow = fixture.root / "shadow"
        shadow.mkdir()
        imported = fixture.root / "shadow-imported"
        for directory in (shadow, fixture.root):
            (directory / "json.py").write_text(f"open({str(imported)!r}, 'w').close()\n")
        clean_env = fixture.env
        fixture.env = {**clean_env, "PYTHONPATH": str(shadow)}
        fixture.reset_state(False)
        result = fixture.run(xml)
        assert result.returncode == 0, f"isolated helper refused reviewed XML: {result.stderr}"
        assert not imported.exists(), "helper imported a module from PYTHONPATH or its directory"
        fixture.env = clean_env
        for directory in (shadow, fixture.root):
            (directory / "json.py").unlink()
        # One fixture per guard that another refusal would otherwise mask.
        duplicate_name = VFIO.replace("<devices>", "<name>arch-dev-vfio</name><devices>", 1)
        fixture.refuses(duplicate_name, "domain name mismatch")
        tail = ET.fromstring(xml)
        tail.find(f"{{{QEMU}}}commandline")[3].tail = "-device vfio-pci,host=01:00.0"
        fixture.refuses(ET.tostring(tail, encoding="unicode"), "unreviewed QEMU command-line")
        fixture.helper.rename(fixture.root / "redirected-helper.py")
        fixture.helper.symlink_to(fixture.root / "redirected-helper.py")
        fixture.refuses(xml, "XML preflight missing, redirected or unreadable")
        fixture.helper.unlink()
        (fixture.root / "redirected-helper.py").rename(fixture.helper)
        fixture.policy_dir.rename(fixture.root / "redirected-policy")
        fixture.policy_dir.symlink_to(fixture.root / "redirected-policy")
        fixture.refuses(xml, "unsafe Looking Glass policy: redirected directory")
        fixture.policy_dir.unlink()
        (fixture.root / "redirected-policy").rename(fixture.policy_dir)
        compact = json.dumps(json.loads(policy), separators=(",", ":"))
        for size, accepted in ((4096, True), (4097, False)):
            fixture.policy.write_text(compact + " " * (size - len(compact)))
            assert fixture.policy.stat().st_size == size
            if accepted:
                fixture.reset_state(False)
                result = fixture.run(xml)
                assert result.returncode == 0, f"4096-byte policy refused: {result.stderr}"
            else:
                fixture.refuses(xml, "invalid Looking Glass policy: too large")
        fixture.policy.unlink()
        os.mkfifo(fixture.policy, 0o644)
        fixture.refuses(xml, "unsafe Looking Glass policy: expected a readable root-owned regular file")
        fixture.policy.unlink()
        fixture.policy.write_text(policy)
        fixture.policy.chmod(0o644)
        # ADR 0019's first lease Template: its rendered default run is an
        # unmapped standard domain, accepted without touching the ladder.
        rendered = fixture.root / "rendered"
        rendered.mkdir()
        name, standard, with_gpu = template_domain_xml(rendered, json.loads(policy))
        parsed = ET.fromstring(standard)
        assert not [node for node in parsed.iter() if node.tag.startswith(f"{{{QEMU}}}")
                    or node.tag == "hostdev"], "workstation-dev-standard renders passthrough"
        for seeded in (False, True):
            fixture.reset_state(seeded)
            result = fixture.run(standard, name)
            assert result.returncode == 0, f"rendered workstation-dev-standard refused: {result.stderr}"
            if seeded:
                assert (fixture.state / "trust").read_bytes() == b"3\n"
                assert sorted(p.name for p in fixture.state.iterdir()) == ["trust"]
            else:
                assert not fixture.state.exists(), "standard Template run created ladder state"
        fixture.refuses(standard.replace("<devices>", "<devices><hostdev type='pci'/>", 1),
                        "PCI passthrough without a reviewed GPU handoff policy", name)
        # The product Machine identity with the reviewed Looking Glass block:
        # refused while unmapped, accepted under a fixture-only reviewed
        # mapping, which then records its rung.
        blocks = ET.fromstring(with_gpu).findall(f"{{{QEMU}}}commandline")
        assert len(blocks) == 1 and len(list(blocks[0])) == 4, "template lost the Looking Glass block"
        fixture.refuses(with_gpu, "QEMU command-line without a reviewed GPU handoff policy", name)
        managed = fixture.root / "domains.d" / f"{name}.conf"
        managed.write_text(f"{name} dev\n")
        fixture.reset_state(False)
        result = fixture.run(with_gpu, name)
        assert result.returncode == 0, f"product Machine Looking Glass XML refused: {result.stderr}"
        assert (fixture.state / "trust").read_bytes() == b"2\n"
        managed.unlink()
        fixture.reset_state(False)
        assert fixture.run("", phase="release").returncode == 0
        assert not fixture.state.exists()
    print("GPU handoff XML contract: OK")


if __name__ == "__main__":
    main()
