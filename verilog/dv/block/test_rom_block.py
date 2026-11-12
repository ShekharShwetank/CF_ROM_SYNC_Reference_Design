"""Block-level checks for rom_ctrl plus a programmed CF_ROM_SYNC."""

import sys
import zlib
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.handle import Force, Release
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "rom"))
import gen_rom_image as image_gen  # noqa: E402

IMAGE = image_gen.build_image()
WIN = 0x30000000
ID = 0x30001000
CTRL = 0x30001004
STATUS = 0x30001008
ADDR = 0x3000100C
DATA = 0x30001010
START = 0x30001014
LEN = 0x30001018
CFG = 0x3000101C
CRC = 0x30001020
COUNT = 0x30001024

CTRL_RESET = 0xC9
CFG_RESET = 0x00010000
FLUSH_ERR = 1 << 3
WR_ERR = 1 << 4
STREAM_DONE = 1 << 1


def _int(value):
    return int(value)


async def start(dut):
    cocotb.start_soon(Clock(dut.wb_clk_i, 25, unit="ns").start())
    dut.wb_rst_i.value = 1
    dut.wbs_cyc_i.value = 0
    dut.wbs_stb_i.value = 0
    dut.wbs_we_i.value = 0
    dut.wbs_sel_i.value = 0
    dut.wbs_dat_i.value = 0
    dut.wbs_adr_i.value = 0
    dut.io_in.value = 1 << 13
    await ClockCycles(dut.wb_clk_i, 5)
    dut.wb_rst_i.value = 0
    await ClockCycles(dut.wb_clk_i, 2)


async def wb(dut, addr, write=False, data=0, sel=0xF):
    dut.wbs_adr_i.value = addr
    dut.wbs_dat_i.value = data
    dut.wbs_sel_i.value = sel
    dut.wbs_we_i.value = 1 if write else 0
    dut.wbs_cyc_i.value = 1
    dut.wbs_stb_i.value = 1
    seen = None
    for _ in range(4000):
        await RisingEdge(dut.wb_clk_i)
        if _int(dut.wbs_ack_o.value) == 1:
            seen = _int(dut.wbs_dat_o.value)
            break
    dut.wbs_stb_i.value = 0
    dut.wbs_cyc_i.value = 0
    dut.wbs_we_i.value = 0
    await RisingEdge(dut.wb_clk_i)
    if seen is None:
        raise AssertionError("Wishbone timeout at 0x%08X" % addr)
    return seen


def rom_byte(addr):
    return IMAGE[addr & 0x3FF]


def expect_word(addr):
    return (
        rom_byte(addr)
        | (rom_byte(addr + 1) << 8)
        | (rom_byte(addr + 2) << 16)
        | (rom_byte(addr + 3) << 24)
    )


async def capture_stream(dut, nbytes):
    while _int(dut.io_out.value) >> 10 & 1:
        await RisingEdge(dut.wb_clk_i)
    bits = []
    prev = 0
    guard = 0
    while len(bits) < nbytes * 8 and guard < 2_000_000:
        await RisingEdge(dut.wb_clk_i)
        guard += 1
        sck = (_int(dut.io_out.value) >> 8) & 1
        if prev == 0 and sck == 1:
            bits.append((_int(dut.io_out.value) >> 9) & 1)
        prev = sck
        if ((_int(dut.io_out.value) >> 10) & 1) and bits:
            break
    out = []
    for index in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[index:index + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


async def spi_clock(dut, mosi, half=8):
    bits_out = []
    for byte in mosi:
        for bit in range(7, -1, -1):
            dut.io_in.value = (1 << 14) * ((byte >> bit) & 1)
            for _ in range(half):
                await RisingEdge(dut.wb_clk_i)
            current = _int(dut.io_in.value)
            dut.io_in.value = current | (1 << 12)
            for _ in range(half // 2):
                await RisingEdge(dut.wb_clk_i)
            bits_out.append((_int(dut.io_out.value) >> 15) & 1)
            for _ in range(half - half // 2):
                await RisingEdge(dut.wb_clk_i)
            dut.io_in.value = _int(dut.io_in.value) & ~(1 << 12)
    packed = []
    for index in range(0, len(bits_out) - 7, 8):
        byte = 0
        for bit in bits_out[index:index + 8]:
            byte = (byte << 1) | bit
        packed.append(byte)
    return bytes(packed)


async def spi_begin(dut):
    dut.io_in.value = 0
    await ClockCycles(dut.wb_clk_i, 4)


async def spi_end(dut):
    dut.io_in.value = 1 << 13
    await ClockCycles(dut.wb_clk_i, 6)


@cocotb.test()
async def reset_defaults(dut):
    await start(dut)
    assert await wb(dut, ID) == 0x524F4D01
    assert await wb(dut, CTRL) == CTRL_RESET
    assert await wb(dut, STATUS) == 0
    assert await wb(dut, CFG) == CFG_RESET
    assert await wb(dut, COUNT) == 0


@cocotb.test()
async def window_all(dut):
    await start(dut)
    for addr in range(0, 1024, 4):
        got = await wb(dut, WIN + addr)
        assert got == expect_word(addr), (addr, hex(got), hex(expect_word(addr)))


@cocotb.test()
async def window_lanes(dut):
    await start(dut)
    byte = await wb(dut, WIN + 0x10, sel=0x1)
    assert byte == 0x80
    high = await wb(dut, WIN + 0x10, sel=0x2)
    assert (high & 0xFF) == 0
    assert ((high >> 8) & 0xFF) == 0x80
    half = await wb(dut, WIN + 0x20, sel=0x3)
    assert (half & 0xFFFF) == (0x55 | (0xAA << 8))


@cocotb.test()
async def seq_port(dut):
    await start(dut)
    await wb(dut, ADDR, write=True, data=0)
    for index in range(1100):
        got = await wb(dut, DATA) & 0xFF
        assert got == rom_byte(index)


@cocotb.test()
async def wait_states(dut):
    await start(dut)
    sample = IMAGE[0:32]
    for ws in range(4):
        ctrl = (CTRL_RESET & ~0x18) | (ws << 3)
        await wb(dut, CTRL, write=True, data=ctrl)
        before = await wb(dut, COUNT)
        got = []
        for addr in range(32):
            got.append(await wb(dut, WIN + addr, sel=0x1) & 0xFF)
        assert bytes(got) == sample
        after = await wb(dut, COUNT)
        assert after - before == 32


@cocotb.test()
async def flush_ok(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=CTRL_RESET | 0x6)
    got = bytearray()
    for addr in range(1024):
        got.append(await wb(dut, WIN + addr, sel=0x1) & 0xFF)
    assert bytes(got) == IMAGE
    assert (await wb(dut, STATUS) & FLUSH_ERR) == 0


@cocotb.test()
async def flush_detect(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=CTRL_RESET | 0x6)

    # rom_rst is a port, so this also works on the gate-level netlist,
    # where the controller state register is renamed by synthesis.
    async def spoil():
        await RisingEdge(dut.u_ctrl.rom_rst)
        await Timer(1, unit="ns")
        dut.u_rom.u_core.q.value = Force(0xA5)

    cocotb.start_soon(spoil())
    await wb(dut, WIN, sel=0x1)
    assert await wb(dut, STATUS) & FLUSH_ERR
    dut.u_rom.u_core.q.value = Release()


@cocotb.test()
async def en_hold(dut):
    await start(dut)
    await wb(dut, WIN, sel=0x1)
    before = _int(dut.u_rom.u_core.q.value)
    count = await wb(dut, COUNT)
    await wb(dut, ADDR, write=True, data=0x55)
    await ClockCycles(dut.wb_clk_i, 3)
    assert _int(dut.u_rom.u_core.q.value) == before
    assert _int(dut.u_ctrl.rom_en.value) == 0
    assert _int(dut.u_ctrl.rom_a.value) == 0x55
    assert await wb(dut, COUNT) == count


@cocotb.test()
async def oe_high_z(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=CTRL_RESET & ~1)
    await ClockCycles(dut.wb_clk_i, 2)
    assert "z" in str(dut.u_rom.DO.value).lower()
    count = await wb(dut, COUNT)
    assert await wb(dut, WIN, sel=0x1) == 0
    assert await wb(dut, COUNT) == count


@cocotb.test()
async def rst_pulse(dut):
    await start(dut)
    await wb(dut, WIN, sel=0x1)
    assert _int(dut.u_rom.u_core.q.value) == IMAGE[0]
    await wb(dut, CTRL, write=True, data=CTRL_RESET | 0x20)
    await ClockCycles(dut.wb_clk_i, 8)
    assert _int(dut.u_rom.u_core.q.value) == 0
    assert (await wb(dut, CTRL) & 0x20) == 0


@cocotb.test()
async def stream_full(dut):
    await start(dut)
    task = cocotb.start_soon(capture_stream(dut, 1028))
    await wb(dut, CFG, write=True, data=CFG_RESET | 1)
    data = await task
    assert data[:1024] == IMAGE
    assert int.from_bytes(data[1024:1028], "little") == zlib.crc32(IMAGE) & 0xFFFFFFFF
    assert await wb(dut, STATUS) & STREAM_DONE


@cocotb.test()
async def stream_partial(dut):
    await start(dut)
    payload = bytes(rom_byte(1000 + i) for i in range(48))
    task = cocotb.start_soon(capture_stream(dut, 52))
    await wb(dut, START, write=True, data=1000)
    await wb(dut, LEN, write=True, data=48)
    await wb(dut, CFG, write=True, data=CFG_RESET | 1)
    data = await task
    assert data[:48] == payload
    assert int.from_bytes(data[48:52], "little") == zlib.crc32(payload) & 0xFFFFFFFF


@cocotb.test()
async def stream_div(dut):
    await start(dut)
    for div in (0, 1, 7):
        task = cocotb.start_soon(capture_stream(dut, 5))
        await wb(dut, START, write=True, data=0x10)
        await wb(dut, LEN, write=True, data=1)
        await wb(dut, CFG, write=True, data=(1 << 16) | (div << 8) | 1)
        data = await task
        assert data[:1] == bytes([IMAGE[0x10]]), data.hex()
        for _ in range(10000):
            if (await wb(dut, STATUS)) & STREAM_DONE:
                break
        else:
            raise AssertionError("stream did not finish")
        await wb(dut, STATUS, write=True, data=STREAM_DONE)
        while ((_int(dut.io_out.value) >> 10) & 1) == 0:
            await RisingEdge(dut.wb_clk_i)


@cocotb.test()
async def stream_trig(dut):
    await start(dut)
    task = cocotb.start_soon(capture_stream(dut, 1028))
    await ClockCycles(dut.wb_clk_i, 4)
    dut.io_in.value = (1 << 13) | (1 << 11)
    await ClockCycles(dut.wb_clk_i, 4)
    dut.io_in.value = 1 << 13
    first = await task
    assert first[:1024] == IMAGE
    status = await wb(dut, STATUS)
    assert status & STREAM_DONE
    await wb(dut, STATUS, write=True, data=STREAM_DONE)
    dut.io_in.value = (1 << 13) | (1 << 11)
    await ClockCycles(dut.wb_clk_i, 20)
    dut.io_in.value = 1 << 13
    await ClockCycles(dut.wb_clk_i, 30)
    assert (await wb(dut, STATUS) & STREAM_DONE) == 0


@cocotb.test()
async def spi_read(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=(CTRL_RESET & ~0x18))
    addresses = (0, 1, 15, 16, 255, 256, 511, 512, 1000, 1023)
    for addr in addresses:
        await spi_begin(dut)
        raw = await spi_clock(dut, [0x03, (addr >> 8) & 0xFF, addr & 0xFF] + [0] * 16, half=8)
        await spi_end(dut)
        assert raw[3:19] == bytes(rom_byte(addr + i) for i in range(16)), addr


@cocotb.test()
async def spi_id(dut):
    await start(dut)
    await spi_begin(dut)
    raw = await spi_clock(dut, [0x9F, 0, 0, 0], half=8)
    await spi_end(dut)
    assert raw[1:4] == bytes((0xCF, 0x52, 0x01))


@cocotb.test()
async def spi_abort(dut):
    await start(dut)
    await spi_begin(dut)
    await spi_clock(dut, [0x03, 0x00], half=8)
    await spi_end(dut)
    await spi_begin(dut)
    raw = await spi_clock(dut, [0x03, 0x00, 0x10, 0x00], half=8)
    await spi_end(dut)
    assert raw[3] == IMAGE[0x10]


@cocotb.test()
async def spi_unknown(dut):
    await start(dut)
    await spi_begin(dut)
    raw = await spi_clock(dut, [0x00, 0xFF, 0xFF], half=8)
    await spi_end(dut)
    assert raw[1:] == bytes(len(raw) - 1)


@cocotb.test()
async def spi_fast(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=(CTRL_RESET & ~0x18))
    await spi_begin(dut)
    raw = await spi_clock(dut, [0x03, 0x00, 0x00, 0x00], half=6)
    await spi_end(dut)
    assert raw[3] == IMAGE[0]


@cocotb.test()
async def arbitrate(dut):
    await start(dut)
    await wb(dut, CTRL, write=True, data=CTRL_RESET | 0x2 | (3 << 3))
    reader = cocotb.start_soon(wb(dut, WIN + 0x20))
    await ClockCycles(dut.wb_clk_i, 15)
    await spi_begin(dut)
    raw = await spi_clock(dut, [0x03, 0x00, 0x80, 0], half=8)
    await spi_end(dut)
    got = await reader
    assert raw[3] == IMAGE[0x80]
    assert got == expect_word(0x20)


@cocotb.test()
async def write_reject(dut):
    await start(dut)
    await wb(dut, WIN, write=True, data=0xFFFFFFFF)
    assert await wb(dut, STATUS) & WR_ERR
    assert (await wb(dut, WIN, sel=0x1) & 0xFF) == IMAGE[0]
