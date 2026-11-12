"""GPIO helpers shared by the chip-level ROM tests."""

import zlib

from caravel_cocotb.caravel_interfaces import test_configure
from cocotb.triggers import ClockCycles, RisingEdge

# rom_ctrl samples trigger (11), SPI SCK (12), CSn (13), and MOSI (14) from
# reset. A floating pad reads as X at gate level, and X in those
# synchronizers leaves the ROM read engine X until the next reset.
IDLE_INPUTS = {11: 0, 12: 0, 13: 1, 14: 0}


async def rom_test_configure(dut, timeout_cycles):
    """test_configure, with the ROM input pads held idle through reset.

    caravel_cocotb's start_up releases every pad except 3 and 4 one clock
    after reset, so this runs the same steps and keeps IDLE_INPUTS driven.
    """
    env = await test_configure(dut, timeout_cycles=timeout_cycles, start_up=False)
    for pin, level in IDLE_INPUTS.items():
        env.drive_gpio_in(pin, level)
    await env.power_up()
    await env.disable_csb()
    await env.reset()
    await env.disable_bins(ignore_bins=[3, 4, *IDLE_INPUTS])
    await ClockCycles(env.clk, 10)
    return env


def _bit(env, pin):
    return env.monitor_gpio(pin).binstr == "1"


def accept(line, token):
    text = (line or "").strip()
    return token in text or token[:-1] in text


async def capture_stream(env, nbytes):
    while _bit(env, 10):
        await RisingEdge(env.clk)
    bits = []
    prev = 0
    guard = 0
    while len(bits) < nbytes * 8 and guard < 5_000_000:
        await RisingEdge(env.clk)
        guard += 1
        sck = 1 if _bit(env, 8) else 0
        if prev == 0 and sck == 1:
            bits.append(1 if _bit(env, 9) else 0)
        prev = sck
        if _bit(env, 10) and bits:
            break
    out = []
    for index in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[index:index + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


async def _spi_byte(env, mosi, half):
    bits = []
    for shift in range(7, -1, -1):
        env.drive_gpio_in(14, (mosi >> shift) & 1)
        env.drive_gpio_in(12, 0)
        await ClockCycles(env.clk, half)
        env.drive_gpio_in(12, 1)
        await ClockCycles(env.clk, max(1, half // 2))
        bits.append(1 if _bit(env, 15) else 0)
        await ClockCycles(env.clk, half - max(1, half // 2))
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


async def spi_transfer(env, payload, half=10):
    env.drive_gpio_in(13, 0)
    env.drive_gpio_in(12, 0)
    await ClockCycles(env.clk, 4)
    data = []
    for byte in payload:
        data.append(await _spi_byte(env, byte, half))
    env.drive_gpio_in(13, 1)
    env.drive_gpio_in(12, 0)
    await ClockCycles(env.clk, 8)
    return bytes(data)


def payload_crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF
