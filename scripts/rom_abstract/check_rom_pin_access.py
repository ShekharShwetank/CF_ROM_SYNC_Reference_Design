#!/usr/bin/env python3
"""Route every CF_ROM_SYNC signal pin in a one-macro design.

Each ROM pin gets its own top-level pin on the die edge: DO and the control
pins from the south on met2, A from the west on met3. OpenROAD in the
LibreLane image runs global and detailed routing. The check fails on
DRT-0073 (no access point), on any detailed-routing DRC violation, or when
a routed li1/met1/met2 shape touches the core keepout that
check_rom_keepout.py uses on the final GDS.

    python3 scripts/rom_abstract/check_rom_pin_access.py
    python3 scripts/rom_abstract/check_rom_pin_access.py --lef ip/CF_ROM_SYNC/layout/lef/CF_ROM_SYNC.lef
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import make_rom_lef as rom

IMAGE_DEFAULT = "ghcr.io/librelane/librelane:2.4.6"
TCL = Path(__file__).resolve().parent / "rom_pin_access.tcl"
ROM_ORIGIN = (130000, 100000)
DIE = (420000, 300000)
WIRE_WIDTH = {"li1": 170, "met1": 140, "met2": 140, "met3": 300, "met4": 300, "met5": 1600}

DbuRect = tuple[int, int, int, int]


def snap(value: float, offset: float, pitch: float) -> int:
    return int(round((round((value - offset) / pitch) * pitch + offset) * 1000))


def write_def(path: Path, pins: list[dict]) -> None:
    lines = [
        "VERSION 5.8 ;",
        'DIVIDERCHAR "/" ;',
        'BUSBITCHARS "[]" ;',
        "DESIGN rom_pin_access ;",
        "UNITS DISTANCE MICRONS 1000 ;",
        f"DIEAREA ( 0 0 ) ( {DIE[0]} {DIE[1]} ) ;",
        "COMPONENTS 1 ;",
        f"- u_rom CF_ROM_SYNC + FIXED ( {ROM_ORIGIN[0]} {ROM_ORIGIN[1]} ) N ;",
        "END COMPONENTS",
    ]
    ports = []
    south_x = 120.0
    west_y = 90.0
    for pin in sorted(pins, key=lambda item: item["name"]):
        tag = pin["name"].replace("[", "").replace("]", "")
        if pin["name"].startswith("A["):
            ports.append((tag, pin["name"], "met3", "( 0 -150 ) ( 1000 150 )", 0, snap(west_y, 0.34, 0.68)))
            west_y += 6.0
        else:
            ports.append((tag, pin["name"], "met2", "( -140 0 ) ( 140 1000 )", snap(south_x, 0.23, 0.46), 0))
            south_x += 8.0
    lines.append(f"PINS {len(ports)} ;")
    for tag, _name, layer, rect, x, y in ports:
        lines.append(
            f"- p_{tag} + NET n_{tag} + DIRECTION INOUT + USE SIGNAL\n"
            f"  + PORT\n    + LAYER {layer} {rect}\n    + PLACED ( {x} {y} ) N ;"
        )
    lines.append("END PINS")
    lines.append(f"NETS {len(ports)} ;")
    for tag, name, *_rest in ports:
        lines.append(f"- n_{tag} ( PIN p_{tag} ) ( u_rom {name} ) + USE SIGNAL ;")
    lines += ["END NETS", "END DESIGN", ""]
    path.write_text("\n".join(lines))


def tech_vias(tlef: Path) -> dict[str, list[tuple[str, DbuRect]]]:
    vias: dict[str, list[tuple[str, DbuRect]]] = {}
    current = None
    layer = None
    for raw in tlef.read_text().splitlines():
        line = raw.strip()
        match = re.match(r"VIA (\S+)", line)
        if match:
            current = match.group(1)
            vias[current] = []
        elif current and line.startswith("END " + current):
            current = None
        elif current and line.startswith("LAYER"):
            layer = line.split()[1]
        elif current and layer and line.startswith("RECT"):
            x0, y0, x1, y1 = (int(Decimal(v) * 1000) for v in line.split()[1:5])
            vias[current].append((layer, (x0, y0, x1, y1)))
    return vias


def routed_shapes(def_text: str, vias: dict[str, list[tuple[str, DbuRect]]]) -> list[tuple[str, DbuRect]]:
    nets = def_text[def_text.index("\nNETS "):def_text.index("END NETS")]
    shapes: list[tuple[str, DbuRect]] = []
    for stmt in nets.split(";"):
        if "ROUTED" not in stmt:
            continue
        for part in re.split(r"\+ ROUTED|\bNEW\b", stmt)[1:]:
            tokens = part.split()
            layer = tokens[0]
            coords = []
            px = py = None
            for x, y in re.findall(r"\(\s*([-\d*]+)\s+([-\d*]+)(?:\s+[-\d]+)?\s*\)", part):
                px = px if x == "*" else int(x)
                py = py if y == "*" else int(y)
                coords.append((px, py))
            patch = re.search(r"RECT\s*\(\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*\)", part)
            if patch and coords:
                x, y = coords[0]
                dx0, dy0, dx1, dy1 = map(int, patch.groups())
                shapes.append((layer, (x + dx0, y + dy0, x + dx1, y + dy1)))
                continue
            half = WIRE_WIDTH.get(layer, 140) // 2
            for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
                shapes.append((layer, (min(x0, x1) - half, min(y0, y1) - half, max(x0, x1) + half, max(y0, y1) + half)))
            via = next((token for token in tokens if token in vias), None)
            if via and coords:
                x, y = coords[-1]
                for via_layer, (a, b, c, d) in vias[via]:
                    shapes.append((via_layer, (x + a, y + b, x + c, y + d)))
    return shapes


def keepout_hits(shapes: list[tuple[str, DbuRect]], pins: list[dict]) -> list[str]:
    _core_pins, core_obs = rom.parse_macro(rom.CORE_LEF.read_text(), "CF_ROM_SYNC_core")
    shifted = rom.core_obs_in_wrap(core_obs)
    hits = []
    for layer in rom.OBS_LAYERS:
        cuts = [pin["rect"] for pin in pins if pin["layer"] == layer]
        region = [
            tuple(int(v * 1000) + ROM_ORIGIN[i % 2] for i, v in enumerate(rect))
            for rect in rom.subtract_many(shifted[layer], cuts)
        ]
        for shape_layer, (x0, y0, x1, y1) in shapes:
            if shape_layer != layer:
                continue
            for kx0, ky0, kx1, ky1 in region:
                if x0 < kx1 and kx0 < x1 and y0 < ky1 and ky0 < y1:
                    hits.append(f"{layer} ({x0 / 1000}, {y0 / 1000})-({x1 / 1000}, {y1 / 1000})")
                    break
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lef", type=Path, default=rom.OUT_LEF)
    parser.add_argument("--out", type=Path, default=rom.ROOT / "build" / "rom_pin_access")
    parser.add_argument("--image", default=os.environ.get("LIBRELANE_IMAGE", IMAGE_DEFAULT))
    args = parser.parse_args()

    lef = args.lef.resolve()
    out = args.out.resolve()
    pdk = (rom.ROOT / "dependencies" / "pdks" / "sky130A").resolve()
    out.mkdir(parents=True, exist_ok=True)
    pins, _obs = rom.parse_macro(rom.WRAP_LEF.read_text(), "CF_ROM_SYNC")
    write_def(out / "tiny.def", pins)

    mounts = {rom.ROOT.resolve(), pdk, lef.parent, out, TCL.parent}
    command = ["docker", "run", "--rm", "--entrypoint", "openroad", "-u", f"{os.getuid()}:{os.getgid()}"]
    for mount in sorted(mounts):
        command += ["-v", f"{mount}:{mount}"]
    command += [
        "-e", f"ROM_PA_PDK={pdk}",
        "-e", f"ROM_PA_LEF={lef}",
        "-e", f"ROM_PA_DEF={out / 'tiny.def'}",
        "-e", f"ROM_PA_OUT={out}",
        args.image,
        "-exit", str(TCL),
    ]
    log_path = out / "openroad.log"
    with log_path.open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    log = log_path.read_text()

    failures = re.findall(r"\[ERROR [A-Z]+-\d+\].*", log)
    counts = re.findall(r"Number of violations = (\d+)", log)
    routed = out / "routed.def"
    if not failures and (not counts or "Complete detail routing" not in log or not routed.is_file()):
        failures.append(f"detailed routing did not finish, see {log_path}")
    if counts and int(counts[-1]) != 0:
        failures.append(f"{counts[-1]} detailed-routing DRC violations, see {out / 'drc.rpt'}")
    if not failures:
        tlef = pdk / "libs.ref" / "sky130_fd_sc_hd" / "techlef" / "sky130_fd_sc_hd__nom.tlef"
        hits = keepout_hits(routed_shapes(routed.read_text(), tech_vias(tlef)), pins)
        failures += [f"routed shape on core keepout: {hit}" for hit in hits[:10]]

    if failures:
        for item in failures:
            print(f"FAIL {item}")
        raise SystemExit(1)
    print(f"pin access clean: {len(pins)} ROM pins routed, 0 DRC, 0 keepout hits ({lef.name})")


if __name__ == "__main__":
    main()
