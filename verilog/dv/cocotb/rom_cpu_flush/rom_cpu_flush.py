import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caravel_cocotb.caravel_interfaces import UART, report_test
import cocotb

from rom_io import accept, rom_test_configure


@cocotb.test()
@report_test
async def rom_cpu_flush(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=20_000_000)
    uart = UART(caravel)
    await caravel.wait_mgmt_gpio(1)
    status = await uart.get_line()
    flush = await uart.get_line()
    if not accept(status, "CRC ok"):
        cocotb.log.error(f"[TEST] '{status}'")
        return
    if not accept(flush, "FLUSH 00000000"):
        cocotb.log.error(f"[TEST] '{flush}'")
        return
    cocotb.log.info("[TEST] Pass CPU flush")
