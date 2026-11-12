import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cocotb
from caravel_cocotb.caravel_interfaces import UART, report_test

from rom_io import accept, capture_stream, payload_crc, rom_test_configure


@cocotb.test()
@report_test
async def rom_serial_stream(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=20_000_000)
    uart = UART(caravel)
    await caravel.wait_mgmt_gpio(1)
    task = cocotb.start_soon(capture_stream(caravel, 1028))
    line = await uart.get_line()
    data = await task
    if not accept(line, "STREAM done"):
        cocotb.log.error(f"[TEST] '{line}'")
        return
    if len(data) < 1028 or payload_crc(data[:1024]) != int.from_bytes(data[1024:1028], "little"):
        cocotb.log.error(f"[TEST] stream length {len(data)}")
        return
    cocotb.log.info("[TEST] Pass serial stream")
