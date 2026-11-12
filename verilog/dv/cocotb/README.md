# Chip tests

`cf verify --all` runs every test in `all_tests.yaml`.

Firmware links `fw/cf_rom_demo.h` and talks on the management UART. GPIO 8–16 are the ROM stream and the SPI slave. Python drives those pins through `caravelEnv.drive_gpio_in` and reads them with `monitor_gpio`.

Gate-level is `cf verify --all --sim gl`. Harden `rom_ctrl` first. The ROM simulator is still `build/CF_ROM_SYNC_sim.v`.
