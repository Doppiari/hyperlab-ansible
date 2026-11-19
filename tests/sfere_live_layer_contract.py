#!/usr/bin/env python3
"""Execute the Sfere seal's live layer over inert transports (ADR 0070).

Everything that moves on the seal shows a fact that is true now, read from a
source the shell already trusts:

  1. no motion without a confirmed state: a running electron travels its
     ring at the one shared speed, whatever its load; a shut-off one never
     moves; a trail exists only with a load reading and is 0.4 + 1.8 x load
     long; particles only with a traffic reading above zero, never on a
     broken spoke; a rule pulse only for a rule ShellState declares; reduced
     motion moves nothing;
  2. the GPU beam ends on the electron of the Machine GPU ownership names,
     and the token sits on the host when the host holds the GPU;
  3. the focus wave follows the reviewed provenance answer, and there is none
     when focus is unrecognised;
  4. load and traffic are rates ShellState computes between two consecutive
     inventory samples: the first sample, a reset, a changed vCPU count or
     interface set, a long gap or an invalid object give no reading, never
     0, and the counters never move the inventory generation;
  5. ShellState's declared rules equal the flows between two different
     networks that the rendered isolation ruleset accepts: none today.

Colour literals and the one-timer rule are the seal contract's source checks
(tests/sfere_view_contract.py), which cover the same files.

`--renders DIR` keeps the five 1920x1080 captures; `declared-rule` draws a
rule no real host declares and is a fixture only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil

import jinja2
import yaml

import host_quickshell_runtime_contract as runtime
import sfere_view_contract as seal
from product_symbol_geometry_contract import EXPECTED as GEOMETRY_B
from trust_pool_v3_generated_contract import png_pixels

ROOT = runtime.ROOT
FIXTURE = ROOT / "tests/fixtures/sfere-live-layer.json"
POLL_NS = 30 * 10**9


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Sfere live layer contract: " + message)


TEMPLATE = ROOT / "roles/lab_isolation/templates/lab-isolation.nft.j2"
# One forward rule this derivation can read: an optional input and output
# interface name (nft allows one trailing `*`), an optional counter, and a
# verdict. Anything else (a set, a map, an address, a state) is refused.
FORWARD_RULE = re.compile(r'(?:iifname "([\w.-]+\*?)" )?(?:oifname "([\w.-]+\*?)" )?(?:counter )?(accept|drop)')


def matches(pattern: str | None, name: str) -> bool:
    if pattern is None:
        return True
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def declared_rules(template_text: str | None = None) -> list[dict]:
    """The flows between two different guest networks the ruleset accepts,
    by first match over the rendered forward chain, then its policy."""
    networks = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())
    guests = networks["network_domains"] + networks["lab_host_networks"]
    lab = next(entry for entry in networks["network_domains"] if entry["forward"] == "isolated")["bridge"]
    template = jinja2.Template(TEMPLATE.read_text() if template_text is None else template_text)
    ruleset = template.render(lab_isolation_guest_networks=guests, lab_isolation_table="inet lab_isolation",
                              lab_isolation_lab_bridge=lab)
    require(ruleset.count("chain forward {") == 1, "the isolation ruleset must have one forward chain")
    forward = ruleset.split("chain forward {", 1)[1].split("\n    }", 1)[0]
    policy = None
    rules = []
    for line in (line.strip() for line in forward.splitlines()):
        if not line or line.startswith("#"):
            continue
        if line.startswith("type "):
            hook = re.fullmatch(r"type filter hook forward priority -?\d+; policy (accept|drop);", line)
            require(hook is not None and policy is None, "the forward chain's hook or policy is unreadable")
            policy = hook[1]
            continue
        rule = FORWARD_RULE.fullmatch(line)
        require(rule is not None, f"a forward rule the derivation of declared rules cannot read: {line}")
        rules.append((rule[1], rule[2], rule[3], line))
    require(policy is not None, "the forward chain has no policy")
    declared = []
    for source in guests:
        for target in guests:
            if source["name"] == target["name"]:
                continue
            verdict, name = policy, "policy " + policy
            for iif, oif, action, line in rules:
                if matches(iif, source["bridge"]) and matches(oif, target["bridge"]):
                    verdict, name = action, line
                    break
            if verdict == "accept":
                declared.append({"from": source["name"], "to": target["name"], "name": name})
    return declared


def derivation_self_test() -> None:
    """The derivation sees an accept only where nft would apply it, and
    refuses what it cannot read."""
    text = TEMPLATE.read_text()
    anchor = "type filter hook forward priority -10; policy accept;\n"
    require(text.count(anchor) == 1, "the forward chain's hook line moved")
    early = '        iifname "virbr-dev" oifname "virbr-services" accept\n'
    late = '        iifname "virbr-dev" oifname "virbr-services" accept\n    }\n\n    chain input {'
    found = declared_rules(text.replace(anchor, anchor + early))
    require([(rule["from"], rule["to"]) for rule in found] == [("dev", "services")],
            "an accept before every drop is not seen as declared")
    require(declared_rules(text.replace("\n    }\n\n    chain input {", "\n" + late, 1)) == [],
            "an accept after the matching drop is counted as declared")
    require(declared_rules(text.replace('        iifname "virbr*" oifname "virbr*" counter drop\n', "")
                           .replace('        iifname "{{ a.bridge }}" oifname "{{ b.bridge }}" counter drop\n', "")) != [],
            "with no drop, the accept policy declares nothing")
    for unreadable in ('        iifname { "virbr-dev" } oifname "virbr-services" accept\n',
                       '        iifname @guests oifname "virbr-services" accept\n',
                       '        ip saddr 10.10.3.0/24 oifname "virbr-services" accept\n'):
        try:
            declared_rules(text.replace(anchor, anchor + unreadable))
        except SystemExit:
            continue
        require(False, f"a forward rule the derivation cannot read was ignored: {unreadable.strip()}")


def rows_for(case: dict) -> list[dict]:
    owner = case["gpu"]["owner"] if case["gpu"]["known"] else ""
    return [dict(runtime.MACHINE_TEMPLATE, name=row["name"], provenance=row["domain"],
                 state=row["state"], networks=row["networks"], network=row["networks"][0],
                 lifecycle="disposable" if row["disposable"] else "permanent",
                 gpu_relation="held" if row["name"] == owner else "none", gpu="", vfio=False)
            for row in case["machines"]]


def samples(case: dict) -> list[dict]:
    """Two consecutive inventory counter samples, 30 s apart, that give the
    case's loads and traffic. A running Machine without a load appears only
    in the second sample (its first poll); a network without a traffic
    reading appears in neither."""
    live = case["live"]
    running = [row for row in case["machines"] if row["state"] == "running"]
    vcpus = runtime.MACHINE_TEMPLATE["vcpus"]
    out = []
    for step in (0, 1):
        machines = {}
        for index, row in enumerate(running):
            start = (index + 3) * 7 * 10**9
            if row["name"] in live["loads"]:
                machines[row["name"]] = {"cpu_time_ns": start + step * round(live["loads"][row["name"]] * 30e9 * vcpus),
                                         "vcpus": vcpus}
            elif step == 1:
                machines[row["name"]] = {"cpu_time_ns": start, "vcpus": vcpus}
        networks = {}
        for name, rate in live["traffic"].items():
            members = sorted(f"{row['name']}/vnet{index}" for index, row in enumerate(running)
                             if name in row["networks"])
            require(members != [], f"{case['id']}: {name} has a traffic reading but no running interface")
            networks[name] = {"rx_bytes": 4000000 + step * round(rate * 30 * 0.75),
                              "tx_bytes": 900000 + step * round(rate * 30 * 0.25), "interfaces": members}
        out.append({"available": True, "sampled_ns": 5 * 10**12 + step * POLL_NS,
                    "machines": machines, "networks": networks})
    return out


LIVE_SETUP = r'''
            const live = @@LIVE@@;
            const declaredRules = @@DECLARED@@;
            const counterSamples = @@SAMPLES@@;
            const gpu = @@GPU@@;
            // The real host's rule source, before any fixture speaks.
            check(JSON.stringify(sharedState.networkRules) === JSON.stringify(declaredRules),
                  "ShellState declares a rule the rendered isolation ruleset does not accept, or misses one");
            function answerInventory(counters) {
                sharedState.applyMachinePayload(JSON.stringify({machines_available: true,
                    machines: sharedState.machines, counters: counters}));
            }
            answerInventory(counterSamples[0]);
            check(Object.keys(sharedState.machineLoad).length === 0
                  && Object.keys(sharedState.networkTraffic).length === 0,
                  "the first poll gave a load or a traffic rate");
            const generation = sharedState.machinesGeneration;
            answerInventory(counterSamples[1]);
            check(sharedState.machinesGeneration === generation, "counters moved the inventory generation");
            // Focus, from the reviewed provenance answer only.
            sharedState.focusSourceState = "ok";
            sharedState.focusObservedAt = Date.now();
            if (live.focus.kind === "host")
                sharedState.provenanceObservation = sharedState.provenanceResult(
                    "resolved", "host", "host-native", "", "unregistered-host-process", "Host process");
            else if (live.focus.kind === "machine")
                sharedState.provenanceObservation = sharedState.provenanceResult(
                    "resolved", live.focus.identity, "host-owned-vm-spec", live.focus.name,
                    "managed-surface-resolved", "Registered managed surface");
            else
                sharedState.provenanceObservation = sharedState.provenanceResult(
                    "unresolved", "", "", "", "registered-domain-spec-drift", "VM specification changed since launch");
            if (live.rules.length > 0) sharedState.networkRules = live.rules;
            keyEvents.wait(30);
'''

LIVE_CHECKS = r'''
            const scene = find(view, "sfere-scene");
            const listed = networks.map(row => row.name);
            const running = row => machinesCurrent && row.state === "running";
            const loadKnown = row => running(row) && Object.prototype.hasOwnProperty.call(live.loads, row.name);
            check(managed.every(row => loadKnown(row)
                      ? Math.abs(sharedState.machineLoad[row.name] - live.loads[row.name]) < 1e-6
                      : !Object.prototype.hasOwnProperty.call(sharedState.machineLoad, row.name)),
                  "a Machine's load differs from its two counter samples");
            check(listed.every(name => Object.prototype.hasOwnProperty.call(live.traffic, name)
                      ? Math.abs(sharedState.networkTraffic[name] - live.traffic[name]) < 1e-3
                      : !Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, name)),
                  "a network's traffic differs from its two counter samples");
            // Every electron on a ring, with its ring item.
            const rings = nodes(view, item => item.objectName.indexOf("sfere-ring-") === 0 && !item.more)
                .map(item => ({ item: item, row: managed.find(row => row.name === item.modelData.name) }));
            check(rings.every(entry => entry.row !== undefined), "an electron is not a managed Machine");
            // 1. Motion: one speed for every running Machine, none for any other,
            // read back from what is drawn: the visible dot's centre, un-tilted
            // by the drawn ring's rotation, gives the electron's angle on the
            // ring's ellipse.
            function drawnAt(entry) {
                const dots = nodes(entry.item.parent, item => item.objectName === "sfere-electron-" + entry.row.name
                                                             && item.visible);
                const orbits = nodes(entry.item, item => item.objectName === "sfere-orbit");
                if (dots.length !== 1 || orbits.length !== 1)
                    return null;
                const net = entry.item.parent;
                const centre = dots[0].mapToItem(entry.item, dots[0].width / 2, dots[0].height / 2);
                const tilt = orbits[0].rotation * Math.PI / 180;
                const ex = (centre.x * Math.cos(tilt) + centre.y * Math.sin(tilt)) / net.ringX;
                const ey = (centre.y * Math.cos(tilt) - centre.x * Math.sin(tilt)) / net.ringY;
                return { angle: Math.atan2(ey, ex), onRing: Math.abs(Math.hypot(ex, ey) - 1) < 1e-3 };
            }
            // The signed difference of two angles, in -pi..pi.
            const turned = (from, to) => ((to - from) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI;
            const t0 = view.liveTime;
            const before = rings.map(drawnAt);
            check(before.every(spot => spot !== null), "a Machine is not exactly one visible electron on one ring");
            check(before.every(spot => spot.onRing), "an electron is not drawn on its ring");
            check(rings.every((entry, i) => Math.abs(turned(entry.item.angle, before[i].angle)) < 1e-3),
                  "an electron is not drawn at its angle");
            view.liveTime = t0 + 2;
            const after = rings.map(drawnAt);
            check(after.every(spot => spot !== null && spot.onRing), "an electron left its ring");
            const moved = rings.map((entry, i) => turned(before[i].angle, after[i].angle));
            check(rings.every((entry, i) => !running(entry.row) || Math.abs(moved[i] - 2 * view.orbitRate) < 1e-3),
                  "a running electron's speed is not the one shared speed");
            check(rings.every((entry, i) => running(entry.row) || Math.abs(moved[i]) < 1e-9), "a shut-off electron moved");
            check(view.orbitRate > 0 && 2 * view.orbitRate < Math.PI, "running electrons do not move, or too fast to measure");
            if (window.firstFailure >= 0) { Qt.exit(40 + window.firstFailure); return; }
            // Trails: only with a load reading, as long as the load says.
            for (const entry of rings) {
                const span = loadKnown(entry.row) ? 0.4 + 1.8 * live.loads[entry.row.name] : 0;
                const trails = nodes(entry.item.parent, item => item.outline !== undefined
                                                               && item.machine === entry.row.name);
                const painted = trails.some(trail => trail.outline.length > 2
                    && drawn(trail, "sfere-path-trail").some(path => path.fillColor.a > 0));
                check(span > 0 || (entry.item.trailSpan === 0 && !painted),
                      "a trail is drawn without a load reading");
                check(Math.abs(entry.item.trailSpan - span) < 1e-9,
                      "a trail's length is not 0.4 + 1.8 x its Machine's load");
                check(span === 0 || painted, "a running Machine with a load reading has no trail");
            }
            view.liveTime = t0;
            // Traffic: particles only with bytes moving, never on a broken spoke.
            const spokes = named("sfere-spoke-");
            for (let i = 1; i < 12; i++)
                check(spokes[0].particlesEachWay(Math.pow(10, i)) >= spokes[0].particlesEachWay(Math.pow(10, i - 1)),
                      "more traffic drew fewer particles");
            for (let i = 0; i < networks.length; i++) {
                const name = networks[i].name, isolated = networks[i].forward === "isolated";
                const particles = nodes(spokes[i], item => item.objectName === "sfere-particle-" + name && item.visible);
                const rate = live.traffic[name];
                if (isolated)
                    check(particles.length === 0, "a broken spoke carries traffic");
                else if (rate === undefined || !machinesCurrent)
                    check(particles.length === 0, "particles without a traffic reading");
                else
                    check(particles.length === (rate > 0 ? 2 * Math.min(4, 1 + Math.floor(Math.log10(Math.max(1, rate / 1000)))) : 0),
                          "traffic particles do not follow the network's bytes");
                const panelled = view.selected && view.selected.name === name;
                if (panelled)
                    check(find(view, "sfere-fact-Traffic").text === (rate === undefined || !machinesCurrent ? "unknown"
                              : view.rateWords(rate)), "the panel's traffic differs from the network's reading");
            }
            // 2. The GPU beam and token, from GPU ownership.
            const beam = find(view, "sfere-gpu-beam");
            const holder = gpu.known ? gpu.owner : "";
            const holderRing = rings.find(entry => entry.row.name === holder);
            for (const time of [t0, t0 + 3.7]) {
                view.liveTime = time;
                if (holderRing) {
                    const dot = nodes(holderRing.item.parent, item => item.objectName === "sfere-electron-" + holder
                                                                     && item.visible)[0];
                    const centre = dot.mapToItem(scene, dot.width / 2, dot.height / 2);
                    check(beam.visible && Math.hypot(beam.to.x - centre.x, beam.to.y - centre.y) < 1.5
                          && beam.from.x === view.hostX && beam.from.y === view.hostY
                          && drawn(beam, "sfere-path-beam")[0].strokeColor.a > 0,
                          "the GPU beam does not end on the holder");
                    const tokens = named("sfere-gpu-token-" + holder).filter(item => item.visible);
                    check(tokens.length === 1 && find(view, "sfere-gpu-beam-label").text === "GPU",
                          "the GPU holder has no token or the beam no label");
                } else {
                    check(!beam.visible, "a GPU beam without a holder on the seal");
                    if (holder)
                        check(visibleText(find(view, "sfere-outside"), holder + " · not managed · outside the seal · holds the GPU"),
                              "a GPU holder outside the seal is not named there");
                }
            }
            view.liveTime = t0;
            const hostToken = find(view, "sfere-gpu-token-host");
            check((hostToken !== null && hostToken.visible) === (gpu.known && gpu.owner === ""),
                  "the host's GPU token differs from GPU ownership");
            check(named("sfere-gpu-token-").filter(item => item.visible).length === (gpu.known && (gpu.owner === "" || holderRing) ? 1 : 0),
                  "the GPU token is drawn more than once, or for an unknown holder");
            // 3. Focus: the wave follows the provenance answer.
            const waves = named("sfere-wave-").filter(item => item.visible);
            const focusRow = live.focus.kind === "machine" ? rings.find(entry => entry.row.name === live.focus.name) : undefined;
            if (focusRow) {
                check(waves.length === 2 && waves.every(item => item.objectName === "sfere-wave-" + focusRow.row.networks[0]),
                      "the focus wave is not round the focused Machine's network");
                const shown = named("sfere-focus-ring-").filter(item => item.visible);
                check(shown.length === 1 && shown[0].objectName === "sfere-focus-ring-" + live.focus.name,
                      "the focused Machine's electron has no focus ring, or another has one");
            } else if (live.focus.kind === "host")
                check(waves.length === 2 && waves.every(item => item.objectName === "sfere-wave-host"),
                      "host focus has no wave round the host");
            else
                check(waves.length === 0 && named("sfere-focus-ring-").filter(item => item.visible).length === 0,
                      "a focus wave without a recognised focus");
            // Rule pulses: one for each declared rule, through the host.
            const declared = sharedState.networkRules.filter(rule => listed.indexOf(rule.from) >= 0
                                                                   && listed.indexOf(rule.to) >= 0);
            const pulses = named("sfere-pulse-");
            check(pulses.length <= declared.length, "a rule pulse is drawn without a declared rule");
            check(pulses.length === declared.length, "a declared rule draws no pulse");
            for (const pulse of pulses) {
                const route = pulse.modelData.route;
                check(route.length === 5 && route[2].x === view.hostX && route[2].y === view.hostY,
                      "a rule pulse does not pass through the host");
                const caption = nodes(pulse, item => item.objectName === "sfere-rule-caption")[0];
                const stage = find(view, "sfere-stage");
                const corner = caption.mapToItem(stage, 0, 0), far = caption.mapToItem(stage, caption.width, caption.height);
                check(caption.visible && corner.x >= 0 && corner.y >= 0 && far.x <= stage.width && far.y <= stage.height,
                      "a rule's caption leaves the stage");
                check(declared.some(rule => pulse.modelData.words === rule.from + " → " + rule.to + " · "
                                            + rule.name + " · via host"), "a rule pulse's caption does not name its rule");
            }
            // Words: the hidden list, the tooltips and the cards say what moves.
            const spoken = nodes(find(view, "sfere-list"), item => item.Accessible.role === Accessible.ListItem)
                .map(item => item.Accessible.name);
            for (const entry of rings) {
                const row = entry.row;
                const want = [running(row) ? (loadKnown(row) ? "load " + Math.round(live.loads[row.name] * 100) + "%"
                                                              : "load unavailable") : null,
                              row.name === holder ? "holds the GPU" : null,
                              focusRow && focusRow.row.name === row.name ? "has focus" : null].filter(Boolean);
                const line = spoken.find(text => text.indexOf(row.name + ", ") === 0) || "";
                check(want.every(word => line.indexOf(word) > 0) && line.indexOf(row.state) > 0
                      && (line.indexOf("load") > 0) === running(row)
                      && (line.indexOf("holds the GPU") > 0) === (row.name === holder)
                      && (line.indexOf("has focus") > 0) === want.includes("has focus"),
                      "a Machine's spoken line does not say its state, load, GPU and focus");
                const tip = nodes(entry.item.parent, item => item.objectName === "sfere-tip-" + row.name)[0];
                const tipText = tip ? tip.children[0].text : "";
                check(want.every(word => tipText.indexOf(word) > 0) && tipText.indexOf(row.name + " · ") === 0,
                      "a Machine's tooltip does not say its state, load, GPU and focus");
            }
            for (const card of nodes(find(view, "sfere-panel-cards"), item => item.objectName.indexOf("sfere-card-live-") === 0)) {
                const row = managed.find(item => "sfere-card-live-" + item.name === card.objectName);
                check(row !== undefined && card.text === view.machineFacts(sharedState.machineById(row.name)).join(" · ")
                      && (!running(row) || card.text.indexOf("load") > 0), "a card does not carry its Machine's live words");
            }
            // The host's whole line, word for word: GPU, focus, then freshness.
            const hostGpu = !gpu.known ? "GPU holder unknown" : gpu.owner === "" ? "holds the GPU"
                : "GPU lent to " + gpu.owner + (holderRing ? "" : ", outside the seal");
            check(spoken[0] === "Host, every path passes here, " + hostGpu
                      + (live.focus.kind === "host" ? ", has focus" : "") + ", " + find(view, "sfere-freshness").text,
                  "the host's spoken line does not say who holds the GPU or that it has focus");
            // The host's live words never run into a network's words.
            const hostLive = find(view, "sfere-host-live");
            const box = item => { const a = item.mapToItem(scene, 0, 0), b = item.mapToItem(scene, item.width, item.height);
                                  return {left: a.x, top: a.y, right: b.x, bottom: b.y}; };
            const own = box(hostLive);
            const apart = other => own.right <= other.left || other.right <= own.left
                || own.bottom <= other.top || other.bottom <= own.top;
            // A sphere is its circle, not its item's square.
            const clear = sphere => {
                const centre = sphere.mapToItem(scene, sphere.width / 2, sphere.height / 2);
                const radius = sphere.width / 2 * sphere.radiusShare;
                const nearX = Math.max(own.left, Math.min(centre.x, own.right));
                const nearY = Math.max(own.top, Math.min(centre.y, own.bottom));
                return Math.hypot(nearX - centre.x, nearY - centre.y) >= radius;
            };
            check(hostLive.visible && named("sfere-words-").every(words => apart(box(words)))
                  && named("sfere-sphere-").every(clear) && apart(box(keystone)),
                  "the host's GPU or focus words overlap a network, its words or the host");
            // Reduced motion moves nothing; motion stops and starts with it.
            const frozen = view.liveTime;
            keyEvents.wait(200);
            check(!view.liveMoving && view.liveTime === frozen, "reduced motion moved the live layer");
            sharedTokens.reducedMotion = false;
            keyEvents.wait(250);
            const anyLive = rings.some(entry => running(entry.row)) || waves.length > 0 || pulses.length > 0;
            check(view.liveMoving === anyLive && (view.liveTime > frozen) === anyLive,
                  "the live layer does not move exactly while something live is on the seal");
            sharedTokens.reducedMotion = true;
            keyEvents.wait(60);
'''

# Focus and the GPU move between Machines of one network: no electron moves.
STEADY = r'''
            function placed() {
                const out = {};
                for (const ring of nodes(view, item => item.objectName.indexOf("sfere-ring-") === 0 && !item.more)) {
                    const dots = nodes(ring.parent, item => item.objectName === "sfere-electron-" + ring.modelData.name
                                                           && item.visible);
                    const centre = dots.length === 1 ? dots[0].mapToItem(scene, dots[0].width / 2, dots[0].height / 2)
                                                     : null;
                    const orbit = nodes(ring, item => item.objectName === "sfere-orbit")[0];
                    out[ring.modelData.name] = { angle: ring.angle, tilt: orbit.rotation,
                                                 x: centre ? centre.x : NaN, y: centre ? centre.y : NaN };
                }
                return out;
            }
            const steadyTime = view.liveTime;
            const steadyBefore = placed();
            const steadyNames = Object.keys(steadyBefore);
            check(["dev-desk", "dev-build", "dev-runner"].every(name => steadyNames.indexOf(name) >= 0),
                  "the five-networks fixture lost a dev Machine");
            sharedState.provenanceObservation = sharedState.provenanceResult(
                "resolved", "dev", "host-owned-vm-spec", "dev-runner",
                "managed-surface-resolved", "Registered managed surface");
            sharedState.applyGpuPayload(JSON.stringify({ known: true, owner: "dev-build", bound: true }));
            keyEvents.wait(30);
            check(view.focusName === "dev-runner" && view.gpuHolder === "dev-build" && view.liveTime === steadyTime,
                  "the steady step did not move focus and the GPU at a fixed time");
            const steadyAfter = placed();
            check(JSON.stringify(Object.keys(steadyAfter).sort()) === JSON.stringify(steadyNames.slice().sort())
                  && steadyNames.every(name => ["angle", "tilt", "x", "y"].every(key =>
                      Math.abs(steadyAfter[name][key] - steadyBefore[name][key]) < 1e-6)),
                  "moving focus or the GPU between Machines moved an electron");
            sharedState.provenanceObservation = sharedState.provenanceResult(
                "resolved", live.focus.identity, "host-owned-vm-spec", live.focus.name,
                "managed-surface-resolved", "Registered managed surface");
            sharedState.applyGpuPayload(JSON.stringify({ known: true, owner: gpu.owner, bound: true }));
            keyEvents.wait(30);
'''

RATES = r'''
            // 4. Rates need two samples of the same thing.
            const base = counterSamples[1];
            function again(change) {
                const next = JSON.parse(JSON.stringify(base));
                next.sampled_ns += 30e9;
                change(next);
                answerInventory(counterSamples[1]);
                answerInventory(next);
            }
            again(next => next.machines["dev-desk"].cpu_time_ns -= 1);
            check(!Object.prototype.hasOwnProperty.call(sharedState.machineLoad, "dev-desk")
                  && Object.prototype.hasOwnProperty.call(sharedState.machineLoad, "dirty-web"),
                  "a CPU counter that fell gave a load");
            again(next => next.machines["dev-desk"].vcpus = 2);
            check(!Object.prototype.hasOwnProperty.call(sharedState.machineLoad, "dev-desk"),
                  "a changed vCPU count gave a load");
            again(next => next.networks.dev.interfaces = ["dev-desk/vnet9"]);
            check(!Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, "dev")
                  && Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, "dirty"),
                  "a changed interface set gave a traffic rate");
            again(next => next.networks.dirty.tx_bytes = 0);
            check(!Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, "dirty"),
                  "a traffic counter that fell gave a rate");
            // A network with no interface: nothing observed, no rate.
            const quiet = JSON.parse(JSON.stringify(base));
            quiet.networks.clean = { rx_bytes: 0, tx_bytes: 0, interfaces: [] };
            answerInventory(quiet);
            const quieter = JSON.parse(JSON.stringify(quiet));
            quieter.sampled_ns += 30e9;
            answerInventory(quieter);
            check(!Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, "clean")
                  && Object.prototype.hasOwnProperty.call(sharedState.networkTraffic, "dev"),
                  "a network with no interface gave a traffic rate");
            view.select(view.networks.findIndex(network => network.name === "clean"));
            keyEvents.wait(30);
            check(find(view, "sfere-fact-Traffic").text === "unknown",
                  "the panel calls the traffic of a network with no interface anything but unknown");
            again(next => next.sampled_ns += 600e9);
            check(Object.keys(sharedState.machineLoad).length === 0, "a sample after a long gap gave a load");
            again(next => next.sampled_ns -= 60e9);
            check(Object.keys(sharedState.machineLoad).length === 0, "a sample older than the last gave a load");
            for (const broken of [null, {available: false}, Object.assign({}, base, {sampled_ns: -1}),
                                  Object.assign({}, base, {machines: {"dev-desk": {cpu_time_ns: "1", vcpus: 4}}}),
                                  Object.assign({}, base, {networks: {dev: {rx_bytes: 1, tx_bytes: -1, interfaces: []}}})]) {
                answerInventory(counterSamples[1]);
                sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: sharedState.machines,
                                                                counters: broken}));
                check(Object.keys(sharedState.machineLoad).length === 0
                      && Object.keys(sharedState.networkTraffic).length === 0, "invalid counters gave a reading");
            }
            // An unknown reading is never a zero: the load says unavailable.
            check(find(view, "sfere-tip-dev-desk").children[0].text.indexOf("load unavailable") > 0,
                  "a running Machine without a load reading does not say so");
            // A stale inventory: no load, no traffic, nothing moves.
            answerInventory(counterSamples[0]);
            answerInventory(counterSamples[1]);
            check(Object.keys(sharedState.machineLoad).length > 0, "restoring the samples gave no load");
            sharedState.machinesObservedAt = Date.now() - 600000;
            sharedState.observationNow = Date.now();
            keyEvents.wait(30);
            check(Object.keys(sharedState.machineLoad).length === 0 && Object.keys(sharedState.networkTraffic).length === 0
                  && nodes(view, item => item.objectName.indexOf("sfere-particle-") === 0 && item.visible).length === 0
                  && nodes(view, item => item.objectName.indexOf("sfere-ring-") === 0 && item.trailSpan > 0).length === 0,
                  "a stale inventory kept a load, a trail or traffic");
            const staleAngles = nodes(view, item => item.objectName.indexOf("sfere-ring-") === 0).map(item => item.angle);
            view.liveTime += 5;
            check(nodes(view, item => item.objectName.indexOf("sfere-ring-") === 0)
                      .every((item, i) => item.angle === staleAngles[i]), "an electron moved on a stale inventory");
            // GPU ownership unknown: no beam, no token anywhere.
            sharedState.applyGpuPayload("unreadable");
            keyEvents.wait(30);
            check(!find(view, "sfere-gpu-beam").visible
                  && named("sfere-gpu-token-").filter(item => item.visible).length === 0,
                  "an unknown GPU holder drew a beam or a token");
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renders", type=Path)
    args = parser.parse_args()
    derivation_self_test()
    declared = declared_rules()
    require(declared == [], "the isolation ruleset now accepts a flow between two networks: "
            "ShellState.networkRules must read it from the same data, and this check must change with it")
    networks = seal.network_rows()
    palette = json.loads(runtime.PALETTE.read_text())
    levels = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())["gpu_trust_levels"]
    ladder = [{"name": name, "level": level} for name, level in levels.items()]
    cases = json.loads(FIXTURE.read_text())["cases"]
    require([case["id"] for case in cases] == ["no-machines", "five-networks", "thirty", "isolated", "declared-rule"]
            and [case["id"] for case in cases if case.get("fixture_only")] == ["declared-rule"]
            and all(not case["live"]["rules"] for case in cases if not case.get("fixture_only")),
            "only the fixture-only case may declare a rule")
    thirty = next(case for case in cases if case["id"] == "thirty")
    require(len(thirty["machines"]) == 30 and sum(row["state"] == "running" for row in thirty["machines"]) == 12,
            "the thirty fixture must hold 30 Machines, 12 running")
    runner = shutil.which("qmlscene6") or shutil.which("qmlscene")
    require(runner is not None, "Qt QML runner is required")
    if args.renders:
        args.renders.mkdir(parents=True, exist_ok=True)
    root = (runtime.QML / "shell.qml").read_text()
    binding = re.search(r"networksMapVisible:\s*(.*?)\n\s*networksPageVisible:", root, re.S)
    require(binding is not None, "missing map visibility binding")
    directory = runtime.stage()
    try:
        for case in cases:
            base = dict(case, stale=None)
            setup = (seal.SETUP.replace("@@CASE@@", json.dumps(base)).replace("@@NETWORKS@@", json.dumps(networks))
                     .replace("@@PALETTE@@", json.dumps(palette)).replace("@@LADDER@@", json.dumps(ladder))
                     .replace("@@GEOMETRY@@", json.dumps(GEOMETRY_B)))
            setup += (LIVE_SETUP.replace("@@LIVE@@", json.dumps(case["live"]))
                      .replace("@@DECLARED@@", json.dumps(declared))
                      .replace("@@SAMPLES@@", json.dumps(samples(case)))
                      .replace("@@GPU@@", json.dumps(case["gpu"])))
            if case.get("enter"):
                setup += f'''
            view.enter(view.networks.findIndex(network => network.name === "{case["enter"]}"));
            keyEvents.wait(30);
'''
            setup += '''
            const machinesCurrent = true;
'''
            body = setup + LIVE_CHECKS + (STEADY + RATES if case["id"] == "five-networks" else "")
            gpu = dict(case["gpu"], bound=bool(case["gpu"]["owner"]))
            for label, scenario, destination in (("checks", body, ""), ("render", setup,
                    str(args.renders.resolve() / f"{case['id']}-1920x1080.png") if args.renders else "")):
                if label == "render" and not args.renders:
                    continue
                source, messages = runtime.scenario_source(1920, 1080, rows_for(case), scenario, gpu=gpu,
                    trust={"known": True, "claimed": True, "identity": "dev", "level": 2}, out=destination)
                source = source.replace("import QtQuick.Window", "import QtQuick.Window\nimport QtTest")
                source = source.replace("ShellState { id: sharedState }", "ShellState { id: sharedState\n"
                    "networksMapVisible: " + binding[1] + "\n}"
                    "\nTestCase { id: keyEvents; when: false }")
                runtime.run(runner, directory, case["id"] + " " + label, source, messages)
                if destination:
                    require(len(set(png_pixels(Path(destination), (1920, 1080)))) > 32, "render is blank")
    finally:
        shutil.rmtree(directory)
    print("Sfere live layer contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
