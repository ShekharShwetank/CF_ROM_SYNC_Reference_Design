import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caravel_cocotb.caravel_interfaces import UART, report_test
import cocotb

from rom_io import accept, rom_test_configure


@cocotb.test()
@report_test
async def rom_flush_regs(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=4_000_000)
    uart = UART(caravel)
    await caravel.wait_mgmt_gpio(1)
    for token in ("PULSE ok", "COUNT ok", "WRITE ok"):
        line = await uart.get_line()
        if not accept(line, token):
            cocotb.log.error(f"[TEST] expected {token}, got '{line}'")
            return
    cocotb.log.info("[TEST] Pass flush registers")
