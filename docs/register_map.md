# Register map

Wishbone base `0x3000_0000`. The slave acks every access inside `0x3000_xxxx`.

## ROM window

`0x3000_0000`–`0x3000_03FF`. Address bits `[9:0]` are the first byte. Each set `wbs_sel` lane, from low to high, reads the next byte and places it in that lane. A word at `0x3FE` returns bytes `0x3FE`, `0x3FF`, `0x000`, `0x001`.

A write acks, changes nothing, and sets `WR_ERR`.

## CSRs

Word offsets from `0x3000_1000`.

| Offset | Name | Reset | Notes |
|---|---|---|---|
| 0 | `ID` | `0x524F4D01` | Constant |
| 1 | `CTRL` | `0x000000C9` | See bits below |
| 2 | `STATUS` | `0` | Sticky bits clear when written 1 |
| 3 | `ADDR` | `0` | Sequential-port address, `[9:0]` |
| 4 | `DATA` | — | Read returns `ROM[ADDR]`, then increments `ADDR` |
| 5 | `STRM_START` | `0` | First stream byte |
| 6 | `STRM_LEN` | `0` | `0` means 1024 bytes |
| 7 | `STRM_CFG` | `0x00010000` | `APPEND_CRC` set, `CLKDIV` 0, `GO` reads 0 |
| 8 | `CRC` | `0` | CRC-32 of the last finished stream |
| 9 | `RD_COUNT` | `0` | Capture edges since reset. Wraps at 2^32 |

### CTRL

| Bits | Name | Reset | Meaning |
|---|---|---|---|
| 0 | `OE` | 1 | 0 forces the ROM data pins to high-Z and returns 0 without a capture |
| 1 | `FLUSH_EN` | 0 | Pulse `RST` before every capture |
| 2 | `FLUSH_CHK` | 0 | With `FLUSH_EN`, flag `FLUSH_ERR` if `DO` is not 0 after the flush |
| 4:3 | `WS` | 1 | Extra clocks between the capture edge and the sample edge |
| 5 | `RST_PULSE` | 0 | Write 1 for one flush and no capture. Always reads 0 |
| 6 | `SPIS_EN` | 1 | SPI slave may use the ROM |
| 7 | `TRIG_EN` | 1 | A rising edge on GPIO 11 starts a stream |

`WS = 1` sets bit 3, so the reset word is `0xC9`.

### STATUS

| Bit | Name | Clear |
|---|---|---|
| 0 | `BUSY` | Level |
| 1 | `STREAM_DONE` | Write 1 |
| 2 | `SPIS_ACTIVE` | Level, chip-select low and `SPIS_EN` |
| 3 | `FLUSH_ERR` | Write 1 |
| 4 | `WR_ERR` | Write 1 |
| 5 | `STREAM_BUSY` | Level |

### STRM_CFG

| Bits | Name | Meaning |
|---|---|---|
| 0 | `GO` | Write 1 to start. Ignored while a stream is running |
| 15:8 | `CLKDIV` | Half-period of `STRM_SCK` is `CLKDIV + 1` Wishbone clocks |
| 16 | `APPEND_CRC` | Append CRC-32, little-endian, after the payload |

CRC-32 is the ISO-HDLC polynomial, initial `0xFFFFFFFF`, final XOR `0xFFFFFFFF`, the same value as `zlib.crc32`. The CRC is over the byte values. On the wire each byte is still MSB first.

## Read sequence

For one byte, with `OE` high:

1. If `FLUSH_EN`: `RST=1` for one rising edge.
2. If `FLUSH_CHK`: the next edge must see `DO == 0`.
3. `EN=1` for one rising edge with `A` held.
4. `WS` further clocks.
5. Sample `DO`.

`EN` is low in every other cycle. `RD_COUNT` counts capture edges only.

Priority when two clients want a byte: SPI slave, then stream, then the Wishbone port. A client keeps the port until its byte finishes. The CPU's `ack` stays low while it waits.
