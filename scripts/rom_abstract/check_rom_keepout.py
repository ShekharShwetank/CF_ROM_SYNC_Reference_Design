#!/usr/bin/env python3
"""Fail if wrapper li1/met1/met2 outside CF_ROM_SYNC lands on the core array.

The keepout on each layer is the core LEF obstruction, shifted by the
(+15, +15) core placement inside the wrap, minus the wrap signal pin
rectangles. A wire that lands on a pin overlaps the pin's own metal and is
allowed; anything else inside the keepout would sit on the real leaf that is
substituted at tapeout. Geometry inside the CF_ROM_SYNC cell is the IP itself
and is not counted.

    klayout -b -r scripts/rom_abstract/check_rom_keepout.py -rd gds=gds/user_project_wrapper.gds
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_rom_lef as rom

try:
    import pya
except ImportError:
    sys.stderr.write("Run this with klayout -b -r check_rom_keepout.py -rd gds=...\n")
    raise SystemExit(2)

GDS_LAYER = {"li1": 67, "met1": 68, "met2": 69}
METAL_DATATYPES = {16, 20}


def rd_value(name: str) -> str | None:
    value = globals().get(name)
    if isinstance(value, str) and value:
        return value
    for arg in sys.argv[1:]:
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def um_box(layout: pya.Layout, rect: rom.Rect) -> pya.Box:
    scale = Decimal("1") / Decimal(str(layout.dbu))
    return pya.Box(
        int((rect[0] * scale).to_integral_value()),
        int((rect[1] * scale).to_integral_value()),
        int((rect[2] * scale).to_integral_value()),
        int((rect[3] * scale).to_integral_value()),
    )


def wrapper_metal(layout: pya.Layout, top: pya.Cell, rom_cell: pya.Cell, layer: int, window: pya.Box) -> pya.Region:
    region = pya.Region()
    for info in layout.layer_infos():
        if info.layer != layer or info.datatype not in METAL_DATATYPES:
            continue
        it = top.begin_shapes_rec_overlapping(layout.layer(info.layer, info.datatype), window)
        it.unselect_cells([rom_cell.cell_index()])
        region += pya.Region(it)
    return region


def main() -> None:
    gds_arg = rd_value("gds")
    if not gds_arg:
        raise SystemExit("pass -rd gds=gds/user_project_wrapper.gds")
    gds_path = Path(gds_arg)
    if not gds_path.is_file():
        raise SystemExit(f"missing GDS {gds_path}")

    pins, _wrap_obs = rom.parse_macro(rom.WRAP_LEF.read_text(), "CF_ROM_SYNC")
    _core_pins, core_obs = rom.parse_macro(rom.CORE_LEF.read_text(), "CF_ROM_SYNC_core")
    shifted = rom.core_obs_in_wrap(core_obs)

    layout = pya.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    rom_cell = layout.cell("CF_ROM_SYNC")
    if top is None or rom_cell is None:
        raise SystemExit(f"{gds_path.name} has no CF_ROM_SYNC cell to check")

    keepout = {}
    for layer in rom.OBS_LAYERS:
        cuts = [pin["rect"] for pin in pins if pin["layer"] == layer]
        region = pya.Region()
        for rect in rom.subtract_many(shifted[layer], cuts):
            region.insert(um_box(layout, rect))
        keepout[layer] = region.merged()

    placed = 0
    intrusions = 0
    dbu = layout.dbu
    for inst in top.each_inst():
        if inst.cell.cell_index() != rom_cell.cell_index():
            continue
        placed += 1
        window = inst.bbox()
        for layer in rom.OBS_LAYERS:
            obs = keepout[layer].transformed(inst.cplx_trans)
            hit = wrapper_metal(layout, top, rom_cell, GDS_LAYER[layer], window) & obs
            if hit.is_empty():
                continue
            intrusions += hit.count()
            for poly in list(hit.each())[:10]:
                box = poly.bbox()
                print(
                    f"FAIL {layer} wrapper metal on CF_ROM_SYNC core at "
                    f"({box.left * dbu:.3f}, {box.bottom * dbu:.3f})-"
                    f"({box.right * dbu:.3f}, {box.top * dbu:.3f})"
                )

    if placed == 0:
        raise SystemExit(f"no CF_ROM_SYNC instance directly under {top.name}")
    if intrusions:
        print(f"{intrusions} intrusion(s)")
        raise SystemExit(1)
    print(f"keepout clean for {placed} CF_ROM_SYNC instance(s)")


if __name__ == "__main__":
    main()
