import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cocotb
from caravel_cocotb.caravel_interfaces import report_test
from cocotb.triggers import ClockCycles

from rom_io import capture_stream, payload_crc, rom_test_configure


@cocotb.test()
@report_test
async def rom_serial_trigger(dut):
    caravel = await rom_test_configure(dut, timeout_cycles=20_000_000)
    await caravel.wait_mgmt_gpio(1)
    task = cocotb.start_soon(capture_stream(caravel, 1028))
    await ClockCycles(caravel.clk, 50)
    caravel.drive_gpio_in(11, 1)
    await ClockCycles(caravel.clk, 20)
    caravel.drive_gpio_in(11, 0)
    data = await task
    if len(data) < 1028 or payload_crc(data[:1024]) != int.from_bytes(data[1024:1028], "little"):
        cocotb.log.error(f"[TEST] trigger dump length {len(data)}")
        return
    cocotb.log.info("[TEST] Pass pin trigger")
