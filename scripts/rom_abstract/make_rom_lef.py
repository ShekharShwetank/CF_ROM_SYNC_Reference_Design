#!/usr/bin/env python3
"""Build openlane/user_project_wrapper/CF_ROM_SYNC.lef from the IP LEFs.

The wrap LEF leaves the array open and blocks the met1 approach to DO.
The core LEF obstructs li1/met1/met2 over the array, except the pin slots.
This generator copies the wrap size, non-DO pins, and power/ground, then:

- Extends every DO pin PORT down to the south edge (y = 0), the same way
  OE/EN/CLK/RST already reach the edge. The wrap's DO ports are 0.195 x 0.43
  um rectangles floating at y = 14.95; TritonRoute reports DRT-0073 (no
  access point) on those shapes because met1 is horizontal-preferred and
  the south met2 halo is solid OBS.
- Rebuilds OBS as the wrap halo plus the core obstruction shifted by
  (+15, +15), with each signal pin (including the extended DO ports) cut
  out and a met1 corridor opened under every DO.

A[9:0] are met2 pins. met3 is open in both LEFs, so a via2 can land on the
pin. West met2 corridors are not opened unless --open-a-corridors is set.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAP_LEF = ROOT / "ip" / "CF_ROM_SYNC" / "layout" / "lef" / "CF_ROM_SYNC.lef"
CORE_LEF = ROOT / "ip" / "CF_ROM_SYNC" / "layout" / "lef" / "CF_ROM_SYNC_core.lef"
OUT_LEF = ROOT / "openlane" / "user_project_wrapper" / "CF_ROM_SYNC.lef"
CORE_GDS = ROOT / "ip" / "CF_ROM_SYNC" / "layout" / "gds" / "CF_ROM_SYNC_core.gds"
WRAP_GDS = ROOT / "ip" / "CF_ROM_SYNC" / "layout" / "gds" / "CF_ROM_SYNC.gds"

CORE_DX = Decimal("15")
CORE_DY = Decimal("15")
# sky130 met1 spacing to wide (>= 3 um) metal. The tech LEF sets USEMINSPACING
# OBS OFF, so the large OBS blocks around DO count as wide metal.
DO_CORRIDOR = Decimal("0.28")
OBS_LAYERS = ("li1", "met1", "met2")

Rect = tuple[Decimal, Decimal, Decimal, Decimal]


def parse_macro(text: str, name: str) -> tuple[list[dict], dict[str, list[Rect]]]:
    """Return signal pins and li1/met1/met2 obstructions for one macro."""
    pins: list[dict] = []
    obs: dict[str, list[Rect]] = {layer: [] for layer in OBS_LAYERS}
    in_macro = False
    pin_name = None
    pin_use = None
    pin_layer = None
    in_obs = False
    obs_layer = None

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("MACRO "):
            in_macro = line.split()[1] == name
            continue
        if not in_macro:
            continue
        if line.startswith("END ") and line.split()[1] == name:
            break
        if line.startswith("PIN "):
            pin_name = line.split()[1]
            pin_use = None
            pin_layer = None
            in_obs = False
            continue
        if pin_name and line == f"END {pin_name}":
            pin_name = None
            continue
        if line == "OBS":
            in_obs = True
            pin_name = None
            obs_layer = None
            continue
        if in_obs and line == "END":
            in_obs = False
            continue
        if pin_name:
            if line.startswith("USE "):
                pin_use = line.split()[1]
            elif line.startswith("LAYER "):
                pin_layer = line.split()[1].rstrip(";")
            elif line.startswith("RECT ") and pin_use == "SIGNAL" and pin_layer:
                pins.append(
                    {
                        "name": pin_name,
                        "layer": pin_layer,
                        "rect": tuple(Decimal(part) for part in line.split()[1:5]),
                    }
                )
        elif in_obs:
            if line.startswith("LAYER "):
                obs_layer = line.split()[1].rstrip(";")
            elif line.startswith("RECT ") and obs_layer in obs:
                obs[obs_layer].append(tuple(Decimal(part) for part in line.split()[1:5]))
    if not pins and name == "CF_ROM_SYNC":
        raise SystemExit(f"no signal pins parsed from {name}")
    return pins, obs


def _overlaps(rect: Rect, cut: Rect) -> bool:
    return not (
        rect[2] <= cut[0] or cut[2] <= rect[0] or rect[3] <= cut[1] or cut[3] <= rect[1]
    )


def subtract_rect(rect: Rect, cut: Rect) -> list[Rect]:
    if not _overlaps(rect, cut):
        return [rect]
    x0, y0, x1, y1 = rect
    ix0 = max(x0, cut[0])
    iy0 = max(y0, cut[1])
    ix1 = min(x1, cut[2])
    iy1 = min(y1, cut[3])
    pieces = []
    if y0 < iy0:
        pieces.append((x0, y0, x1, iy0))
    if iy1 < y1:
        pieces.append((x0, iy1, x1, y1))
    if x0 < ix0:
        pieces.append((x0, iy0, ix0, iy1))
    if ix1 < x1:
        pieces.append((ix1, iy0, x1, iy1))
    return [piece for piece in pieces if piece[0] < piece[2] and piece[1] < piece[3]]


def subtract_many(rects: list[Rect], cuts: list[Rect]) -> list[Rect]:
    current = list(rects)
    for cut in cuts:
        nxt: list[Rect] = []
        for rect in current:
            nxt.extend(subtract_rect(rect, cut))
        current = nxt
    return current


def translate(rects: list[Rect], dx: Decimal, dy: Decimal) -> list[Rect]:
    return [(x0 + dx, y0 + dy, x1 + dx, y1 + dy) for x0, y0, x1, y1 in rects]


def extend_do_pin(rect: Rect) -> Rect:
    """Stretch a DO pin down to the south edge, keeping its x-range and top."""
    x0, _y0, x1, y1 = rect
    return (x0, Decimal("0"), x1, y1)


def with_extended_do_pins(pins: list[dict]) -> list[dict]:
    out = []
    for pin in pins:
        if str(pin["name"]).startswith("DO["):
            out.append({**pin, "rect": extend_do_pin(pin["rect"])})
        else:
            out.append(pin)
    return out


def do_corridors(pins: list[dict], through_pin: bool) -> list[Rect]:
    """Met1 approach under DO. through_pin runs it up to the pin's top edge."""
    cuts = []
    for pin in pins:
        if not str(pin["name"]).startswith("DO["):
            continue
        x0, y0, x1, y1 = pin["rect"]
        # Use the original floating pin's y0 when corridors are checked against
        # the IP GDS; use the extended pin's top when cutting OBS.
        top = y1 if through_pin else (y0 if y0 > 0 else y1)
        cuts.append((x0 - DO_CORRIDOR, Decimal("0"), x1 + DO_CORRIDOR, top))
    return cuts


def do_pins(pins: list[dict]) -> list[dict]:
    return [pin for pin in pins if str(pin["name"]).startswith("DO[")]


def a_corridors(pins: list[dict]) -> list[Rect]:
    """Optional met2 slot from the west edge to each A pin."""
    cuts = []
    for pin in pins:
        if not str(pin["name"]).startswith("A["):
            continue
        _x0, y0, x1, y1 = pin["rect"]
        cuts.append((Decimal("0"), y0, x1, y1))
    return cuts


def core_obs_in_wrap(core_obs: dict[str, list[Rect]]) -> dict[str, list[Rect]]:
    return {
        layer: translate(core_obs[layer], CORE_DX, CORE_DY) for layer in OBS_LAYERS
    }


def merged_obs(
    wrap_pins: list[dict],
    wrap_obs: dict[str, list[Rect]],
    core_obs: dict[str, list[Rect]],
    open_a_corridors: bool,
) -> dict[str, list[Rect]]:
    access_pins = with_extended_do_pins(wrap_pins)
    shifted = core_obs_in_wrap(core_obs)
    merged: dict[str, list[Rect]] = {}
    for layer in OBS_LAYERS:
        cuts = [pin["rect"] for pin in access_pins if pin["layer"] == layer]
        if layer == "met1":
            cuts.extend(do_corridors(access_pins, through_pin=True))
        if layer == "met2" and open_a_corridors:
            cuts.extend(a_corridors(wrap_pins))
        merged[layer] = subtract_many(list(wrap_obs[layer]) + shifted[layer], cuts)
    return merged


def fmt(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-0"):
        return "0"
    return text


def rewrite_do_ports(wrap_text: str, wrap_pins: list[dict]) -> str:
    """Replace each DO pin RECT with one that reaches the south edge."""
    extended = {
        pin["name"]: extend_do_pin(pin["rect"])
        for pin in wrap_pins
        if str(pin["name"]).startswith("DO[")
    }
    lines = wrap_text.splitlines(keepends=True)
    out = []
    current_pin = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("PIN "):
            current_pin = stripped.split()[1]
        elif stripped.startswith("END ") and current_pin and stripped == f"END {current_pin}":
            current_pin = None
        elif (
            current_pin in extended
            and stripped.startswith("RECT ")
            and current_pin is not None
        ):
            x0, y0, x1, y1 = extended[current_pin]
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}RECT {fmt(x0)} {fmt(y0)} {fmt(x1)} {fmt(y1)} ;\n"
        out.append(line)
    return "".join(out)


def render(wrap_text: str, wrap_pins: list[dict], obs: dict[str, list[Rect]]) -> str:
    rewritten = rewrite_do_ports(wrap_text, wrap_pins)
    marker = "\n  OBS\n"
    at = rewritten.find(marker)
    if at < 0:
        raise SystemExit("wrap LEF has no OBS section")
    prefix = rewritten[: at + 1]
    lines = [
        "  OBS",
        "    # Generated by scripts/rom_abstract/make_rom_lef.py.",
        "    # Wrap halo plus core li1/met1/met2 OBS at (+15, +15).",
        "    # DO ports extend to y=0; signal pins and DO corridors cut out.",
    ]
    for layer in OBS_LAYERS:
        rects = sorted(obs[layer], key=lambda rect: (rect[1], rect[0], rect[3], rect[2]))
        if not rects:
            continue
        lines.append(f"    LAYER {layer} ;")
        for x0, y0, x1, y1 in rects:
            lines.append(f"      RECT {fmt(x0)} {fmt(y0)} {fmt(x1)} {fmt(y1)} ;")
    lines.append("  END")
    lines.append("END CF_ROM_SYNC")
    lines.append("")
    lines.append("END LIBRARY")
    lines.append("")
    return prefix + "\n".join(lines)


def build(open_a_corridors: bool = False) -> str:
    wrap_text = WRAP_LEF.read_text()
    core_text = CORE_LEF.read_text()
    pins, wrap_obs = parse_macro(wrap_text, "CF_ROM_SYNC")
    _core_pins, core_obs = parse_macro(core_text, "CF_ROM_SYNC_core")
    obs = merged_obs(pins, wrap_obs, core_obs, open_a_corridors)
    return render(wrap_text, pins, obs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--open-a-corridors",
        action="store_true",
        help="Also cut met2 from the west edge to each A pin",
    )
    parser.add_argument("-o", type=Path, default=OUT_LEF)
    args = parser.parse_args()
    text = build(open_a_corridors=args.open_a_corridors)
    args.o.parent.mkdir(parents=True, exist_ok=True)
    args.o.write_text(text)
    pins, _obs = parse_macro(WRAP_LEF.read_text(), "CF_ROM_SYNC")
    out_pins, _ = parse_macro(text, "CF_ROM_SYNC")
    do_out = [p for p in out_pins if p["name"].startswith("DO[")]
    print(
        f"wrote {args.o} ({len(pins)} signal pins, "
        f"{len(do_out)} DO ports extended to y=0)"
    )


if __name__ == "__main__":
    main()
