#!/usr/bin/env python3
"""Check the IP GDS against the DO corridors the generated LEF opens.

Each corridor is DO pin x +/- DO_CORRIDOR, from the macro's south edge to
the top of the pin. Two parts are checked separately:

- Halo (below the core boundary at y = 15). This is wrap geometry, which
  ships as is. Any met1/met2 drawing or pin shape here that is not the DO pin
  itself, or any CF_ROM_SYNC_core blockage, fails. Wrap-cell datatype 10 is
  the halo abstract the LEF replaces, so it is not a hit.
- Core pocket (y = 15 up to the pin top, outside the pin). The real leaf is
  substituted at tapeout, so this file cannot prove the pocket is empty.
  Visible met1 drawing that is not the DO net fails. Wrapper wires there are
  caught after routing by check_rom_keepout.py.

Every wrap signal pin must also have metal under it.

    klayout -b -r scripts/rom_abstract/check_rom_corridors.py
    klayout -b -r scripts/rom_abstract/check_rom_corridors.py -rd gds=ip/CF_ROM_SYNC/layout/gds/CF_ROM_SYNC.gds
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
    sys.stderr.write("Run this with klayout -b -r check_rom_corridors.py\n")
    raise SystemExit(2)

LI1 = 67
MET1 = 68
MET2 = 69
BLOCKAGE = 10
METAL_DATATYPES = {16, 20}
LAYER_NUM = {"met1": MET1, "met2": MET2, "li1": LI1}


def rd_value(name: str, default: Path) -> str:
    value = globals().get(name)
    if isinstance(value, str) and value:
        return value
    for arg in sys.argv[1:]:
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return str(default)


def um_box(layout: pya.Layout, rect: rom.Rect) -> pya.Box:
    scale = Decimal("1") / Decimal(str(layout.dbu))
    return pya.Box(
        int((rect[0] * scale).to_integral_value()),
        int((rect[1] * scale).to_integral_value()),
        int((rect[2] * scale).to_integral_value()),
        int((rect[3] * scale).to_integral_value()),
    )


def layer_indexes(layout: pya.Layout, layer: int, datatypes: set[int]) -> list[int]:
    return [
        layout.layer(info.layer, info.datatype)
        for info in layout.layer_infos()
        if info.layer == layer and info.datatype in datatypes
    ]


def region_on(cell: pya.Cell, indexes: list[int], skip_cell: str | None = None) -> pya.Region:
    region = pya.Region()
    for index in indexes:
        it = cell.begin_shapes_rec(index)
        while not it.at_end():
            if skip_cell is None or it.cell().name != skip_cell:
                shape = it.shape()
                if shape.is_box() or shape.is_polygon() or shape.is_path():
                    region.insert(shape.polygon.transformed(it.trans()))
            it.next()
    return region


def ensure_core(layout: pya.Layout, top: pya.Cell) -> None:
    for inst in top.each_inst():
        if inst.cell.name == "CF_ROM_SYNC_core":
            return
    if layout.cell("CF_ROM_SYNC_core") is None:
        layout.read(str(rom.CORE_GDS))
    core = layout.cell("CF_ROM_SYNC_core")
    if core is None:
        raise SystemExit(f"CF_ROM_SYNC_core is not in {rom.CORE_GDS}")
    top.insert(
        pya.CellInstArray(
            core.cell_index(),
            pya.Trans(int(round(float(rom.CORE_DX) / layout.dbu)), int(round(float(rom.CORE_DY) / layout.dbu))),
        )
    )


def main() -> None:
    gds_path = Path(rd_value("gds", rom.WRAP_GDS))
    if not gds_path.is_file():
        raise SystemExit(f"missing GDS {gds_path}")

    pins, _wrap_obs = rom.parse_macro(rom.WRAP_LEF.read_text(), "CF_ROM_SYNC")
    layout = pya.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    if top is None:
        raise SystemExit(f"{gds_path} has no top cell")
    ensure_core(layout, top)

    metal = {
        name: region_on(top, layer_indexes(layout, number, METAL_DATATYPES))
        for name, number in (("met1", MET1), ("met2", MET2))
    }
    core_blockage = region_on(
        top,
        [index for number in (LI1, MET1, MET2) for index in layer_indexes(layout, number, {BLOCKAGE})],
        skip_cell="CF_ROM_SYNC",
    )

    failures = []
    for pin in rom.do_pins(pins):
        x0, y0, x1, y1 = pin["rect"]
        pin_region = pya.Region(um_box(layout, pin["rect"]))
        halo = pya.Region(um_box(layout, (x0 - rom.DO_CORRIDOR, Decimal("0"), x1 + rom.DO_CORRIDOR, rom.CORE_DY)))
        pocket = pya.Region(
            um_box(layout, (x0 - rom.DO_CORRIDOR, rom.CORE_DY, x1 + rom.DO_CORRIDOR, y1))
        ) - pin_region
        for name in ("met1", "met2"):
            others = (metal[name] & halo) - pin_region
            if not others.is_empty():
                failures.append(f"{pin['name']} halo corridor has {name} that is not the pin")
        if not (core_blockage & halo).is_empty():
            failures.append(f"{pin['name']} halo corridor has CF_ROM_SYNC_core blockage")
        other_met1 = metal["met1"] - metal["met1"].interacting(pin_region)
        if not (other_met1 & pocket).is_empty():
            failures.append(f"{pin['name']} core pocket has visible met1 that is not the DO net")

    for pin in pins:
        number = LAYER_NUM.get(pin["layer"])
        if number is None:
            continue
        if (region_on(top, layer_indexes(layout, number, METAL_DATATYPES)) & pya.Region(um_box(layout, pin["rect"]))).is_empty():
            failures.append(f"no {pin['layer']} under pin {pin['name']} {pin['rect']}")

    if failures:
        for item in failures:
            print(f"FAIL {item}")
        raise SystemExit(1)
    print(
        f"corridors clean (DO +/- {rom.fmt(rom.DO_CORRIDOR)} um), "
        f"{len(pins)} pins have landing metal ({gds_path.name})"
    )


if __name__ == "__main__":
    main()
