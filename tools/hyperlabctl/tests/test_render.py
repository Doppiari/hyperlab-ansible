"""waybar reads four keys and nothing else. Text output must never raise."""

import json
import importlib.util
from pathlib import Path

import world
from harness import check, equals
from hyperlabctl import document
from hyperlabctl.render import DomainSpheres, _nearest_256, as_text, as_waybar

RUNNING_VFIO = [{"name": "win11clean-valley", "state": "running",
                 "memory_mb": 6144, "vfio": True}]


def test_waybar_payload_has_exactly_the_four_keys():
    payload = as_waybar(document.build(world.build(domains=RUNNING_VFIO, trust=3)))
    equals("waybar_keys", sorted(payload), ["alt", "class", "text", "tooltip"])


def test_waybar_payload_is_one_json_line():
    payload = as_waybar(document.build(world.build(trust=None)))
    encoded = json.dumps(payload)
    equals("single_line", encoded.count("\n"), 0)


def test_waybar_text_names_the_trust_domain_when_claimed():
    payload = as_waybar(document.build(world.build(domains=RUNNING_VFIO, trust=3)))
    equals("waybar_text", payload["text"], "clean 3")


def test_waybar_text_says_unclaimed_before_the_first_start():
    payload = as_waybar(document.build(world.build(trust=None)))
    equals("waybar_unclaimed", payload["text"], "unclaimed")


def test_waybar_class_escalates_to_error():
    ctx = world.build(domains=[{"name": "rogue-vfio", "state": "running",
                                "memory_mb": 2048, "vfio": True}], trust=None)
    payload = as_waybar(document.build(ctx))
    equals("waybar_class_error", payload["class"], "error")


def test_waybar_class_is_ok_on_a_clean_host():
    ctx = world.build(domains=[], trust=None)
    built = document.build(ctx)
    built["problems"] = []
    equals("waybar_class_ok", as_waybar(built)["class"], "ok")


def test_text_render_never_colours_when_disabled():
    text = as_text(document.build(world.build(domains=RUNNING_VFIO, trust=3)), color=False)
    check("no_escape_codes", "\033" not in text)


def test_text_render_survives_a_fully_degraded_document():
    built = document.build(world.build(trust=None, profile_report=False))
    text = as_text(built, color=False)
    check("degraded_text_not_empty", len(text) > 0)


def test_disabled_domain_spheres_do_not_require_a_checkout():
    spheres = DomainSpheres(None, False, {})
    equals("disabled_domain_prefix", spheres.prefix("dev"), "")
    equals("disabled_external_prefix", spheres.prefix(None), "")


def test_domain_256_conversion_uses_fixed_slots_and_nearest_rgb():
    # Exact greys and cube endpoints, plus a colour whose nearest grey beats
    # every cube entry. The first sixteen slots are terminal appearance.
    for colour, expected in (((0, 0, 0), 16), ((255, 255, 255), 231),
                             ((128, 128, 128), 244), ((95, 135, 175), 67),
                             ((12, 12, 12), 232), ((13, 13, 13), 232)):
        equals("fixed_256_%s" % (colour,), _nearest_256(colour), expected)


def test_status_renderers_still_support_loading_by_filename():
    path = Path(__file__).resolve().parents[1] / "hyperlabctl/render.py"
    spec = importlib.util.spec_from_file_location("standalone_render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    equals("standalone_status_text", module.as_text({}, color=False),
           "hyperlab  ?  profile unknown")
