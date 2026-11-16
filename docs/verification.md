# Verification

## Image

`python3 -m unittest discover -s rom/tests -v`

Checks the header, each region, the sine points, the address fingerprint, the CRC, and that `submit/CF_ROM_SYNC.rom` matches the generator.

## Block

`make block-sim` runs Cocotb 2 against `rom_ctrl` and `build/CF_ROM_SYNC_sim.v` under Icarus. No Caravel and no firmware.

The suite covers reset values, all 1024 bytes, byte lanes, the sequential port, wait states 0–3, a clean flush, a forced flush failure, `EN` hold, `OE` high-Z, `RST_PULSE`, a full stream, a wrapping stream, three `CLKDIV` values, the pin trigger, SPI `READ` and `RDID`, an aborted SPI command, an unknown command, a fast SPI host, arbitration against a Wishbone read, and write rejection.

The fast SPI host uses a half-period of 6 Wishbone clocks. That is the shortest pulse that still produces four stable samples after the two synchronizer flops.

Activate the virtualenv first so `cocotb-config` is on `PATH`:

```bash
source /home/shekhar/Desktop/work/.work_env/bin/activate
```

## Chip

`cf verify --all` runs the caravel-cocotb tests:

| Test | What it checks |
|---|---|
| `rom_smoke` | `ID` and header magic on the management UART |
| `rom_cpu_flush` | Firmware CRC of all 1024 bytes, with flush checking on |
| `rom_serial_stream` | GPIO 8–10 frame matches the image and its CRC |
| `rom_serial_trigger` | A rising edge on GPIO 11 dumps the ROM |
| `rom_spi_slave` | External `0x9F` and `0x03` on GPIO 12–15 |
| `rom_flush_regs` | `RST_PULSE`, `RD_COUNT`, and `WR_ERR` |
| `rom_boot_table` | Sine samples 0, 16, and 48 |

`make -C verilog/dv/block gl` runs the same 21 tests on the hardened `rom_ctrl` netlist, the programmed ROM model, and the Sky130 cell models.

Full-chip gate-level uses the full Caravel tree (`cf setup --no-caravel-lite`), not caravel-lite. `caravel_cocotb` runs `caravel/scripts/gen_gpio_defaults.py`, which reads `caravel/mag/caravel_core.mag` and `verilog/rtl/user_defines.v` and writes `verilog/gl/caravel_core.v` plus `verilog/gl/gpio_defaults_block_*.v`. `verilog/includes/includes.gl.caravel_user_project` names those files, and `Test.write_includes_file` expands the glob. `cf verify --all --sim gl` reads `verilog/dv/cocotb/all_tests_gl.yaml` (7 tests, `sim: GL`).

`rom_ctrl` samples GPIO 11–14 from reset, because the CTRL reset value turns on the pin trigger and the SPI slave. Every chip test starts with `rom_test_configure` from `verilog/dv/cocotb/rom_io.py`, which holds trigger, SCK, and MOSI low and CSn high through reset. A floating pad reads as X. RTL hides that because `if (X)` takes the else branch. The netlist does not: the read engine goes X a few clocks after reset, and the first ROM window read returns X on `wbs_ack_o`, which stops the management SoC. A board must drive or pull those four pins to the same levels.

The wrapper is synthesized. Hold between `rom_ctrl` and the ROM is closed by the ROM pin budget in `openlane/rom_ctrl/base.sdc` and by the wrapper resizer. `make rom-sta` reports the paths through each ROM pin after the wrapper harden. KLayout DRC stays on. Magic DRC stays off for the same reason as the reference: the ROM GDS uses obstruction datatypes 67/10, 68/10, and 69/10. `scripts/rom_abstract/check_rom_keepout.py` is the check that wrapper metal did not land on the array.

## What a passing LVS does not prove

A passing LVS shows that `CF_ROM_SYNC` is connected and that `vpb` is on `vpwr` and `vnb` is on `vgnd` inside the wrap. Catalog 0.2.5 does not draw that tie. Precheck run `15_NOV_2026___21_59_29` failed only there: 26 layout nets against 24 schematic nets, with `proxyvpb` and `proxyvnb`. The record and the GDS edit are in [ip_issues.md](ip_issues.md). The mask image is the SHA-256 of `submit/CF_ROM_SYNC.rom`.
