# CF_ROM_SYNC reference design

A Caravel user project whose only catalog IP is `CF_ROM_SYNC` 0.2.3. The management RISC-V core is the CPU. The management UART is the console. Serial readout is custom RTL in `rom_ctrl`, so the ROM stays the block under study.

The public ROM GDS is an abstract. ChipFoundry substitutes the programmed leaf at tapeout. This repository shows how to build that image, how to read it, and how to place the macro.

`rom_ctrl` and `CF_ROM_SYNC` are hard macros. The wrapper is synthesized, so the clock tree, hold repair, and the GPIO repeaters are ordinary cells. The ROM `CLK` pin is `wb_clk_i`. It is not a `rom_ctrl` output.

## What you can do from the Wishbone port

Base address `0x3000_0000`.

| Range | What it is |
|---|---|
| `0x3000_0000`–`0x3000_03FF` | The 1024 image bytes. A word read is four bytes, little-endian, wrapping at 1023. Writes are ignored and set `WR_ERR`. |
| `0x3000_1000` | Ten control registers. See [docs/register_map.md](docs/register_map.md). |

`CTRL` resets to `0x000000C9`: output enable on, one wait state, SPI slave enabled, pin trigger enabled. Bit 3 is the wait-state LSB, so one wait state is `0xC9`, not `0xC1`.

## Pins

| `mprj_io` | Name | Direction |
|---|---|---|
| 8 | `STRM_SCK` | out, idle low |
| 9 | `STRM_SDO` | out, MSB first |
| 10 | `STRM_CS_N` | out, low while a frame is shifting |
| 11 | `STRM_TRIG` | in, rising edge dumps the ROM when `TRIG_EN` is set |
| 12 | `SPIS_SCK` | in |
| 13 | `SPIS_CS_N` | in, active low |
| 14 | `SPIS_MOSI` | in |
| 15 | `SPIS_MISO` | out while selected |
| 16 | `BUSY` | out |

Pins 0–7 stay with Caravel housekeeping. The stream is mode-0: data changes on the falling edge, the receiver samples on the rising edge. `SCK = wb_clk / (2 * (CLKDIV + 1))`.

The SPI slave accepts `0x03` plus a 16-bit address (low 10 bits select the byte) and then streams bytes. `0x9F` returns `CF 52 01`. Each SCK half-period must cover the 2-flop synchronizer and four stable samples, which is 6 Wishbone clocks in this controller. At 40 MHz that is about 3.3 MHz.

## Image and programming

```bash
source /home/shekhar/Desktop/work/.work_env/bin/activate
make rom
```

That writes `submit/CF_ROM_SYNC.rom`, its SHA-256, and `build/CF_ROM_SYNC_sim.v`. Submit the `.rom` and the digest with the design. Place and route keeps using `ip/CF_ROM_SYNC/hdl/gl/CF_ROM_SYNC.v`. The simulation file does not go in `VERILOG_FILES`.

The image map is [docs/rom_image_map.md](docs/rom_image_map.md). Replacing the image is [docs/rom_programming.md](docs/rom_programming.md).

## Tests

Block tests do not need Caravel:

```bash
source /home/shekhar/Desktop/work/.work_env/bin/activate
make block-sim
```

Chip tests, after `cf setup`:

```bash
cf verify --all
```

The suites are listed in [docs/verification.md](docs/verification.md).

## Placement and the ROM abstract

`rom_ctrl` is 400 × 200 µm, met3 only, so the wrapper keeps met4 and met5. Hold repair on the Wishbone inputs adds about 850 buffers. At 300 × 200 µm that reached 67% utilization, the router detoured nets on met1–met3, and the slow corner failed max slew. `u_rom_ctrl` starts at (60, 60) µm.

`u_cf_rom_sync` starts at (130, 320) µm, 60 µm above the controller. The wrapper's met5 straps over it are `vccd1` at y = 374.3 µm and `vssd1` at y = 392.9 µm. Both must cross the 90.42 µm macro, or the ROM's `vgnd` or `vpwr` met4 pins are left unconnected; at y = 300 the `vssd1` strap missed. Power hooks are `vpwr`/`vgnd` on the ROM and `vccd1`/`vssd1` on `rom_ctrl`, both tied to the user core rails.

Place and route does not use `ip/CF_ROM_SYNC/layout/lef/CF_ROM_SYNC.lef`. That LEF leaves the array open and blocks the met1 approach to `DO`. `scripts/rom_abstract/make_rom_lef.py` writes `openlane/user_project_wrapper/CF_ROM_SYNC.lef` from the wrap LEF and the core LEF. The core obstruction is shifted by (+15, +15), and a met1 corridor 0.28 µm wider than each `DO` pin on both sides is opened from the macro edge to the pin top. 0.28 µm is the sky130 met1 spacing to wide metal, which applies to this LEF's obstructions. A narrower corridor gives `DRT-0073 No access point`. `A` is reached by a via2 from met3. The defect report is [docs/ip_issues.md](docs/ip_issues.md). When ChipFoundry ships a fixed LEF, point the wrapper config back at the IP file.

`make rom-lef` regenerates that LEF, checks the corridors on the IP GDS, and routes all 22 ROM pins in a one-macro design with the LibreLane image's OpenROAD. It fails on any pin-access error, routing DRC, or routed metal on the core array. It takes a few seconds; run it before a wrapper harden whenever the generator or the IP changes.

The ss liberty is characterized at −40 °C, not 100 °C. The slow corner still uses that file. That gap is in the same note.

## Harden and gate-level

Run these from this directory after `source /home/shekhar/Desktop/work/.work_env/bin/activate`. LibreLane stays on the shuttle pin `cf setup` installs (CI2511 / 2.4.6). Do not install 3.0.13.

**B0. Environment, once**

1. `cf setup --pdk sky130A --only-pdk`
2. `cf setup --pdk sky130A --no-caravel-lite --only-caravel --overwrite`
   - Gate: `ls caravel/mag/caravel_core.mag*` shows the file, and `caravel/verilog/rtl/user_defines.v` is a regular file. If the `.mag` is missing, stop.
3. `cf setup --pdk sky130A --only-mcw --only-cocotb --overwrite`
   - Gate: `verilog/dv/cocotb/design_info.yaml` exists and its paths are absolute.
4. `cf setup --pdk sky130A --only-precheck`

**B1. Image and block**

`make rom`, then `make block-sim`. Gate: 4 image tests and 21 block tests pass.

**B2. Chip RTL**

`cf verify --all`. Gate: 7/7. About 25 minutes.

**B3. Harden `rom_ctrl`**

`cf harden rom_ctrl`. Gate: the flow ends with no errors and writes `gds/`, `lef/`, `lib/`, `spef/`, `verilog/gl/`, and `mag/` itself. In `openlane/rom_ctrl/runs/<tag>`, setup and hold are at or above 0 in all 9 corners, lint and synth checks are 0, and LVS, DRC, and XOR are clean. `*-openroad-stapostpnr/*/checks.rpt` has no max slew or max cap violators at any corner. The wrapper re-checks this macro's internal nets from its netlist and parasitics, so a slow-corner slew violation here also fails B5. The antenna report is not a gate.

**B4. Gate-level block**

`make -C verilog/dv/block gl`. Gate: the same 21 block tests pass on the hardened netlist.

**B5. Harden the wrapper**

`make rom-lef` first. Then `cf harden user_project_wrapper`. Gate: the flow finishes with no deferred errors and saves its own views. In the run directory, LVS is clean, KLayout DRC is 0, XOR is clean, and setup and hold are at or above 0 at all 9 corners. `*-openroad-stapostpnr/*/checks.rpt` has no max slew or max cap violators, and no max fanout violators on data nets. Clock-tree leaf buffers (`clkbuf_leaf_*`) drive more than 10 loads by design, so they are not counted. LibreLane only warns on these, so this check is manual. The power-grid step must not report `PSM-0039 Unconnected instance` for `u_cf_rom_sync` or `u_rom_ctrl`.

Then:

```bash
klayout -b -r scripts/rom_abstract/check_rom_keepout.py -rd gds=gds/user_project_wrapper.gds
make rom-sta
```

Keepout must report 0 intrusions. `make rom-sta` must report positive slack on every ROM pin path, and each `DO` net at or above the liberty `min_capacitance` of 0.111 pF. A short `DO` net needs a real load cell.

**B6. Full-chip gate-level**

`cf verify rom_smoke --sim gl` first. The log must show `gen_gpio_defaults` writing `verilog/gl/caravel_core.v`, then a clean compile, then a pass. Then `cf verify --all --sim gl`. Gate: 7/7. This is several hours. `rom_cpu_flush` is the long one, about 0.63 M cycles at RTL.

**B7. Precheck**

`cf precheck`. Gate: the required checks pass, including LVS against `lvs/user_project_wrapper/lvs_config.json`, XOR, consistency, and the GPIO-defaults checks.

If a gate fails, the report to send back is the one named in that step: the run's `checks.rpt` / `min.rpt` / `max.rpt`, the keepout log, or `build/rom_sta/<corner>.rpt`.

LVS checks the wrap, not the mask bits. The image proof is the SHA-256 in `submit/`.

## IP behaviour this design is built around

- `EN` high on a rising `CLK` captures `mem[A]`. `EN` low holds the output register.
- `RST` high on a rising `CLK` clears that register to `0x00`. The Liberty file describes this as synchronous. The ideal model also clears asynchronously. The controller holds `RST` for a full clock so both descriptions agree.
- `OE` low makes `DO` high-Z. The controller keeps `OE` high except when the `OE` bit is cleared, and it does not sample `DO` in that mode.
- Clock-to-`DO` is about 8–10 ns typical and 16.4 ns at the slow corner for the minimum 0.111 pF load (`timing/lib`). One wait state is the reset setting at 40 MHz. A slow-corner miss becomes a multicycle constraint and a larger `WS`, not a new controller.
- `DO` asks for at least 0.111 pF of load. Buffer it. Add an explicit load if static timing reports a minimum-capacitance violation.
