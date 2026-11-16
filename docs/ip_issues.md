# CF_ROM_SYNC abstract LEF

This note is the 0.2.3 abstract. The trial branch now builds against catalog 0.2.5, whose wrap ports are the outer 6.9 µm of each `DO` and `A` stem. The 0.2.3 LEF pair does not describe one legal routing picture. Place and route followed the wrap LEF. The core LEF, which is the geometry ChipFoundry puts back at tapeout, says that metal is occupied. This note is the report for that, and for the slow-corner liberty.

## 0.2.5 precheck LVS, run 15_NOV_2026___21_59_29

`cf precheck` on the wrapper hardened from catalog 0.2.5 passed every check except LVS. OEB passed. XOR, KLayout FEOL, BEOL, offgrid, metal density, pin labels, zero-area, spike, and illegal cell name passed. Magic DRC was skipped, as configured. LVS returned stat 1 after 902 seconds. The report is `precheck_results/15_NOV_2026___21_59_29/outputs/reports/lvs.report`. The log is `precheck_results/15_NOV_2026___21_59_29/logs/LVS_check.log`.

Harden LVS on the same database still prints `Circuits match uniquely`. That comparison black-boxes `CF_ROM_SYNC`. It never opens the child. Precheck does. `lvs/user_project_wrapper/lvs_config.json` keeps `CF_ROM_SYNC` unflattened and compares it with `ip/CF_ROM_SYNC/hdl/gl/CF_ROM_SYNC.v`.

### What the report says

The failing cell is the wrap, not the wrapper and not `rom_ctrl`. Netgen's last lines are:

```
Final result: Subcell(s) failed matching.
The following subcells failed to match:
 CF_ROM_SYNC"(0)"
 CF_ROM_SYNC"(1)"
Notice: LVS completed with these abstracted cells:
GS_CF_ROM_SYNC_core contains no devices
```

Inside that cell the device count matches (one core instance) and the net count does not: 26 on the layout side, 24 on the schematic side. Every signal pin matches with fanout 1: `DO[7:0]`, `A[9:0]`, `EN`, `CLK`, `RST`, `OE`. The four extra layout nets are `vpwr`, `vgnd`, `dummy_25`, and `dummy_26`.

The schematic, from `CF_ROM_SYNC.v`, ties the well pins to the customer rails inside the wrap:

```systemverilog
CF_ROM_SYNC_core u_core (
    .vpwr(vpwr),
    .vgnd(vgnd),
    .vpb(vpwr),
    .vnb(vgnd),
    ...
);
```

So schematic `vpwr` has fanout 2 (`vpwr` and `vpb`) and schematic `vgnd` has fanout 2 (`vgnd` and `vnb`). The extracted abstract has no `vpb` or `vnb` port. Netgen invents `proxyvpb` on `dummy_25` and `proxyvnb` on `dummy_26`, each with fanout 1, and leaves layout `vpwr` and `vgnd` at fanout 1. The instance line is `GS_CF_ROM_SYNC_core_0` against `u_core`, with `proxyvpb = 1` against `vpb = 2` and `proxyvnb = 1` against `vnb = 2`.

The hierarchy check in the same log also prints `Hierarchy check for user_project_wrapper failed` and writes `tmp/hier.csv` containing only:

```
verilog,,layout
CF_ROM_SYNC/CF_ROM_SYNC_core,1
user_project_wrapper/CF_ROM_SYNC,1
```

That message is not the LVS result. The same two lines were present on the earlier run whose LVS then passed. Precheck continues into extraction and netgen either way. The stat-1 result is the 26-versus-24 net mismatch.

### Why the layout has no well ports

`hdl/gl/CF_ROM_SYNC.v` says the well taps are tied inside. The 0.2.5 GDS does not show that tie to Magic.

Magic names a port from GDS text. `layout/gds/CF_ROM_SYNC_core.gds` has `vpwr` and `vgnd` text on layer 69 datatype 5. It has no `vpb` or `vnb` text. Pin purpose 69/16 covers `vgnd` and two address pins. It does not cover the core LEF's well pins. Those LEF rectangles are still there as drawing metal on 69/20:

- `vpb`: `RECT 0.61 58.82 5.3 60.25`, which is GDS box `610,58820 5300,60250` at 1 nm database units.
- `vnb`: `RECT 22.925 59 28.26 60.23`, GDS box `22925,59000 28260,60230`.

The core sits in the wrap at `(15000, 15000)`. The wrap's horizontal met3 rails, also unchanged from the previous drop, are `vgnd` at y = 75920–79020 nm and `vpwr` at y = 80720–83820 nm. Nothing on met2 joins the well pins up to those rails, so extraction cannot merge them even after a label is added.

`vpb` is also not its own net in the drawing. On 69/20 it shares metal with `A[7]` (and, through that component, the other `A` pins). The bridge is the west rail `280,0 610,60420`, a 0.33 µm strip the full height of the leaf. The `vpb` rectangle starts at x = 610 nm, so the two shapes abut. `vnb` does not touch that rail, `vpwr`, or `vgnd`.

Precheck abstracts `*CF_ROM_SYNC_core` before the compare. The abstract keeps every layer that has a port. Met2 has the `A` ports, so the west rail survives and the short stays. That is why a label alone, without opening the abutment, would tie `A` to `vpwr` once the strap is added. A local extract of the unmodified 0.2.5 leaf showed `vpb` and `A[7]` in one merged polygon of area 44360200 nm², and `vnb` in a separate polygon of area 7575700 nm².

Magic's black-box copy renames the child on the way into `gds/user_project_wrapper.gds`. This run used `GS_CF_ROM_SYNC_core`. The same two-letter prefix is already on the standard cells (`OY_sky130_fd_sc_hd__fill_1` is paired with `sky130_fd_sc_hd__fill_1` in this report). Netgen compared `GS_CF_ROM_SYNC_core` with `CF_ROM_SYNC_core` and then failed on the pins. The prefix is not the defect to patch. The wrapper config accepts it with `^([A-Z]{2}_)?CF_ROM_SYNC_core$`. The GDS is left with whatever prefix Magic writes.

### The edit

`scripts/rom_abstract/strap_rom_wells.rb` was run once on `ip/CF_ROM_SYNC/layout/gds/CF_ROM_SYNC.gds` and on `layout/gds/CF_ROM_SYNC_core.gds`. The wrap file is the one streamout copies. The same four shapes were added to `layout/mag/CF_ROM_SYNC.mag` so the MAG and the GDS describe one wrap. The 6.9 µm `DO` and `A` stems are untouched.

On the core, in 1 nm database units:

- Text `vpb` at `(2955, 59535)` and `vnb` at `(25592, 59615)`, layer 69 datatype 5, the same text type as `vpwr` and `vgnd`.
- Pin purpose 69/16 on the LEF rectangles `610,58820 5300,60250` and `22925,59000 28260,60230`.
- The west rail's right edge moves from x = 610 nm to x = 470 nm. The gap is 140 nm, the sky130 met2 spacing. The address feeds still meet the rail, which still covers x = 280–470 nm. After the cut, `vpb` and `A[7]` are different polygons.

On the wrap, the core origin is `(15000, 15000)`:

- Met2 `17715,74500 18195,82000` from the `vpb` pin up into the `vpwr` rail, and via2 `17855,81000 18055,81200` only where that finger overlaps `vpwr` (y = 80720–83820). The finger crosses the `vgnd` rail on met2 and does not via there.
- Met2 `40350,74500 40830,77750` from the `vnb` pin into the `vgnd` rail, and via2 `40490,77000 40690,77200` inside y = 75920–79020.

In the MAG those rectangles are divided by 5, because the file is in 5 nm units: met2 `3543 14900 3639 16400` and `8070 14900 8166 15550`, via2 `3571 16200 3611 16240` and `8098 15400 8138 15440`.

A Magic abstract of this GDS, using the same delete-and-keep-port-layers sequence as precheck, then extracts the wrap as: `vnb` merged into parent `vgnd`, `vpb` merged into core `vpwr`, and that `vpwr` merged into parent `vpwr`. No `A` pin merges into `vpwr`. The core reports 26 ports, including `vpb` and `vnb`.

The current `gds/user_project_wrapper.gds` is still the failing harden. Precheck reads that file, not the IP GDS directly. The next `cf harden user_project_wrapper` copies the edited IP GDS. Do not run `make rom-lef`. Do not rename the prefixed core after streamout.

The project-local abstract is `openlane/user_project_wrapper/CF_ROM_SYNC.lef`, generated by `scripts/rom_abstract/make_rom_lef.py`. It is not a hand edit. When a fixed IP LEF ships, the wrapper `MACROS.CF_ROM_SYNC.lef` entry goes back to `ip/CF_ROM_SYNC/layout/lef/CF_ROM_SYNC.lef`.

## What the two LEFs say

Wrap macro `ip/CF_ROM_SYNC/layout/lef/CF_ROM_SYNC.lef`, size 160.18 × 90.42 µm.

- `li1` obstruction is the whole macro: `RECT 0 0 160.18 90.42`.
- `met1` and `met2` obstructions are the halo only. The array interior, roughly x = 15..145 and y = 15..75, is open.
- `DO[4]` is `RECT 89.78 14.95 89.975 15.38` on met1. The halo obstruction on that same x is `RECT 89.78 0 89.975 14.95`, so the pin does not reach the south edge. The same pattern is on `DO[7:0]`. `DO[4]` and `DO[5]` were the pins that picked up KLayout m1.2 when the router used that opening.
- `OE`, `EN`, `CLK`, and `RST` already start at y = 0, so their south approach is open.
- West `met2` is `RECT 0 0 15 90.42`. `A[9:0]` sits just inside that, for example `A[0]` at `RECT 15.015 16.285 15.405 16.77` (0.39 × 0.485 µm).
- Neither LEF obstructs met3. A via2 from met3 can land on `A`.

Core macro `ip/CF_ROM_SYNC/layout/lef/CF_ROM_SYNC_core.lef`, size 130.18 × 60.42 µm. In the wrap it sits at (+15, +15), which lines up with the halo (15 + 130.18 = 145.18, 15 + 60.42 = 75.42). Its `li1`, `met1`, and `met2` obstructions cover the array except the pin slots. Example, core `DO[4]` is `RECT 74.78 0.075 74.975 0.255` on met1, which is the wrap pin after the +15 shift.

A route the wrap LEF accepts over the array, such as `rom_a[0]` on met2 inside y < 189 in the earlier wrapper run, sits on core metal once the real leaf is substituted. Abstract LVS and DRC do not see that.

## What the generator changes

- Size, non-DO signal pins, and `vpwr`/`vgnd` are copied from the wrap LEF.
- Each `DO` pin PORT is stretched to the south edge: same x-range, `y = 0` to the original top. That matches `OE`/`EN`/`CLK`/`RST`. The wrap's floating 0.195 × 0.43 µm `DO` rectangles do not get a TritonRoute access point: met1 is horizontal-preferred, the south met2 halo is solid OBS, and a corridor alone is not enough. Wrapper detailed routing failed with `DRT-0073 No access point for u_cf_rom_sync/DO[0]` until the ports reached the edge.
- Obstruction is the wrap halo plus the core `li1`/`met1`/`met2` obstruction translated by (+15, +15).
- Each signal pin rectangle, including the extended `DO` ports, is cut out of that obstruction.
- Each `DO` pin also gets a met1 corridor, pin x ± 0.28 µm, from y = 0 through the pin top. 0.28 µm is the sky130 met1 spacing to wide (≥ 3 µm) metal. The tech LEF sets `USEMINSPACING OBS OFF`, so the large obstruction blocks around `DO` are treated as wide metal.
- `A` does not get a met2 corridor. `--open-a-corridors` adds one from the west edge if detailed routing reports a pin-access failure. That flag is off.

`scripts/rom_abstract/check_rom_corridors.py` checks the IP GDS. In the halo part of a corridor (below the core boundary), met1/met2 that is not the `DO` pin, or any core-cell 67/10, 68/10, or 69/10 blockage, is a failure. The wrap cell's datatype 10 is the halo abstract this LEF replaces, so it is not a hit. Above the core boundary the real leaf is hidden, so the check can only fail on visible met1 that is not the `DO` net. A wrap pin with no landing metal is also a failure.

`scripts/rom_abstract/check_rom_pin_access.py` routes all 22 pins in a one-macro design and fails on `DRT-0073`, routing DRC, or routed metal on the core keepout. `scripts/rom_abstract/check_rom_keepout.py` checks `gds/user_project_wrapper.gds` after the wrapper harden. Its keepout is the translated core obstruction minus the wrap signal pin rectangles, layer by layer. Wrapper metal outside the `CF_ROM_SYNC` cell inside that keepout is a failure. There is no DRC waiver for this.

## Liberty

`timing/lib/CF_ROM_SYNC_ss_1.60V_-40C.lib` is the only slow library, and it is at −40 °C. The sky130 slow STA corner is 100 °C / 1.60 V. The wrapper config maps `*_ss_100C_1v60` to that file because there is no 100 °C ss library. Clock-to-`DO` at the 0.111 pF minimum load reaches 16.350 ns in that file. `DO` `min_capacitance` is 0.111 pF in all three libraries. A `DO` net under that load needs a real cell, not a timing waiver.
