#!/usr/bin/python3
"""Validate prepare XML and the one reviewed Looking Glass argv extension."""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

QEMU = "http://libvirt.org/schemas/domain/qemu/1.0"
POLICY_OWNER = 0
MAX_XML_BYTES = 1024 * 1024


class Refusal(ValueError):
    """The prepare input is absent, ambiguous or outside reviewed policy."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Refusal(message)


class DomainTree(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise Refusal("invalid domain XML: document types are not allowed")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "invalid Looking Glass policy: duplicate key")
        result[key] = value
    return result


def read_policy(path: Path) -> tuple[str, int]:
    # O_NONBLOCK keeps a substituted FIFO from hanging a prepare. Check the
    # opened inode too: pathname checks alone do not establish what was read.
    require(not any(parent.is_symlink() for parent in path.parents),
            "unsafe Looking Glass policy: redirected directory")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == POLICY_OWNER
                and info.st_mode & 0o022 == 0 and info.st_mode & 0o444 != 0,
                "unsafe Looking Glass policy: expected a readable root-owned regular file")
        raw = handle.read(4097)
    require(len(raw) <= 4096, "invalid Looking Glass policy: too large")
    policy = json.loads(raw, object_pairs_hook=unique_object)
    require(type(policy) is dict and set(policy) == {"device", "size_bytes"},
            "invalid Looking Glass policy: expected device and size_bytes only")
    device, size = policy["device"], policy["size_bytes"]
    require(isinstance(device, str) and re.fullmatch(r"/dev/kvmfr[0-9]+", device) is not None,
            "invalid Looking Glass policy: expected kvmfr transport")
    require(type(size) is int and size > 0 and size % 1048576 == 0,
            "invalid Looking Glass policy: expected whole positive MiB size")
    return device, size


def validate_xml(raw: bytes, domain: str, mapped: bool, device: str, size: int) -> None:
    require(0 < len(raw) <= MAX_XML_BYTES, "invalid domain XML: missing or too large")
    try:
        root = ET.fromstring(raw, parser=ET.XMLParser(target=DomainTree()))
    except ET.ParseError as error:
        raise Refusal("invalid domain XML: malformed document") from error
    require(root.tag == "domain", "invalid domain XML: expected domain root")
    names = root.findall("./name")
    require(len(names) == 1 and names[0].text == domain, "domain name mismatch")

    extensions = [node for node in root.iter() if node.tag.startswith(f"{{{QEMU}}}")]
    if not mapped:
        require(not extensions, "QEMU command-line without a reviewed GPU handoff policy")
        require(not any(node.tag == "hostdev" and node.get("type") == "pci"
                        or node.tag == "interface" and node.get("type") == "hostdev"
                        for node in root.iter()),
                "PCI passthrough without a reviewed GPU handoff policy")
        return
    if not extensions:
        return

    blocks = root.findall(f"./{{{QEMU}}}commandline")
    require(len(blocks) == 1, "unreviewed QEMU command-line: expected one block")
    block = blocks[0]
    args = list(block)
    require(not block.attrib and not (block.text or "").strip()
            and len(args) == 4 and extensions == [block, *args]
            and all(node.tag == f"{{{QEMU}}}arg" and set(node.attrib) == {"value"}
                    and len(node) == 0 and not (node.text or "").strip()
                    and not (node.tail or "").strip() for node in args),
            "unreviewed QEMU command-line: expected four arguments only")
    # Compare literal values, never evaluate the QEMU object syntax. These
    # four values are the reviewed domain.xml.j2 form; all IDs, properties,
    # ordering and transport limits are fixed independently of incoming XML.
    expected = [
        "-device",
        "{'driver':'ivshmem-plain','id':'shmem0','memdev':'looking-glass'}",
        "-object",
        "{'qom-type':'memory-backend-file','id':'looking-glass',"
        f"'mem-path':'{device}','size':{size},'share':true}}",
    ]
    require([node.get("value") for node in args] == expected,
            "unreviewed QEMU command-line: Looking Glass arguments differ")


def main() -> int:
    try:
        require(len(sys.argv) == 4, "XML preflight requires domain, profile and policy")
        domain, profile, policy_path = sys.argv[1:]
        try:
            device, size = read_policy(Path(policy_path))
        except OSError as error:
            raise Refusal(f"unsafe Looking Glass policy: {error}") from error
        except (UnicodeError, ValueError) as error:
            raise Refusal(f"invalid Looking Glass policy: {error}") from error
        raw = sys.stdin.buffer.read(MAX_XML_BYTES + 1)
        validate_xml(raw, domain, bool(profile), device, size)
    except (OSError, ValueError) as error:
        print(f"gpu-handoff: XML preflight refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
