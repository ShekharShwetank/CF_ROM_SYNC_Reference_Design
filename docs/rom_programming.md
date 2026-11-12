# Programming CF_ROM_SYNC

The macro is mask-programmed. The files shipped in the IP package do not contain a customer image. `ip/CF_ROM_SYNC/scripts/program_cf_rom_sync.py` checks a 1024-byte hex file and writes:

| File | Use |
|---|---|
| `build/CF_ROM_SYNC_sim.v` | Simulation. Defines `CF_ROM_SYNC` and `CF_ROM_SYNC_core` with the image. |
| `build/CF_ROM_SYNC_lvs.v` | Same ports as `hdl/gl`, empty leaf, digest in a comment. |
| `submit/CF_ROM_SYNC.rom` | One lowercase byte per line. This is the file to submit. |

The script prints the SHA-256 of the 1024 bytes. `make rom` saves that digest to `submit/CF_ROM_SYNC.rom.sha256`.

## Use the reference image

```bash
make rom
python3 -m unittest discover -s rom/tests -v
```

`make rom` also refreshes `fw/rom_map.h` and `verilog/dv/golden/rom_map.py`.

## Use a different image

Write 1024 hex bytes, address 0 first. Blank lines and `//` or `#` comments are ignored.

```bash
python3 ip/CF_ROM_SYNC/scripts/program_cf_rom_sync.py my_image.hex \
  --sim build/CF_ROM_SYNC_sim.v \
  --lvs build/CF_ROM_SYNC_lvs.v \
  --image-out submit/CF_ROM_SYNC.rom
```

Submit `submit/CF_ROM_SYNC.rom` and the printed SHA-256 with the tapeout. The public GDS does not change. OpenLane must keep compiling `ip/CF_ROM_SYNC/hdl/gl/CF_ROM_SYNC.v`. Do not add `build/CF_ROM_SYNC_sim.v` to `VERILOG_FILES`.

Simulation include lists compile the sim file and not also the zero behavioural model, because both define `CF_ROM_SYNC_core`.

LVS compares the wrap hierarchy against the abstract layout. It does not check the programmed bytes.
