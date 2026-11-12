import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caravel_cocotb.caravel_interfaces import report_test
import cocotb

from rom_io import rom_test_configure, spi_transfer


@cocotb.test()
@report_test
async def rom_spi_slave(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=8_000_000)
    await caravel.wait_mgmt_gpio(1)
    ident = await spi_transfer(caravel, [0x9F, 0, 0, 0], half=12)
    data = await spi_transfer(caravel, [0x03, 0x00, 0x00, 0x00], half=12)
    if ident[1:4] != bytes((0xCF, 0x52, 0x01)):
        cocotb.log.error(f"[TEST] RDID {ident.hex()}")
        return
    if data[3] != 0x43:
        cocotb.log.error(f"[TEST] READ {data.hex()}")
        return
    cocotb.log.info("[TEST] Pass SPI slave")
