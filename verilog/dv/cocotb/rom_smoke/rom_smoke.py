import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caravel_cocotb.caravel_interfaces import UART, report_test
import cocotb

from rom_io import accept, rom_test_configure


@cocotb.test()
@report_test
async def rom_smoke(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=2_000_000)
    uart = UART(caravel)
    await caravel.wait_mgmt_gpio(1)
    ident = await uart.get_line()
    magic = await uart.get_line()
    if not accept(ident, "524F4D01"):
        cocotb.log.error(f"[TEST] ID line '{ident}'")
        return
    if not accept(magic, "4346524D"):
        cocotb.log.error(f"[TEST] MAGIC line '{magic}'")
        return
    cocotb.log.info(f"[TEST] Pass '{ident}' / '{magic}'")
