# ROM image

1024 bytes, built by `rom/gen_rom_image.py`. The committed SHA-256 of those bytes is in `submit/CF_ROM_SYNC.rom.sha256`.

| Addresses | Contents |
|---|---|
| `0x000`–`0x00F` | Header |
| `0x010`–`0x017` | Walking ones: `80 40 20 10 08 04 02 01` |
| `0x018`–`0x01F` | Walking zeros: `7F BF DF EF F7 FB FD FE` |
| `0x020`–`0x05F` | Checkerboard, 16-byte rows. Even rows start `55 AA`. Odd rows start `AA 55`. Address `0x040` is `5A`. |
| `0x060`–`0x07F` | `0x00` |
| `0x080`–`0x0FF` | `0xFF` |
| `0x100`–`0x1FF` | Byte equals `address[7:0]` |
| `0x200`–`0x2FF` | Byte equals the inverse of `address[7:0]`. Address `0x200` is `A5`. |
| `0x300`–`0x37F` | 64 little-endian int16 samples, `round(32767 * sin(2πk/64))` |
| `0x380`–`0x3BF` | ASCII `CF_ROM_SYNC reference image v1`, NUL padded |
| `0x3C0`–`0x3FB` | `0xFF` |
| `0x3FC`–`0x3FF` | CRC-32 of bytes `0x000`–`0x3FB`, little-endian |

Header bytes: `43 46 52 4D 01 00 00 04 10 18 20 60 80 00 01 00`.

The two overrides exist so the bytes at addresses `0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512` are all different. Those are the locations selected by no address bit and by each address bit alone. The generator exits if a later edit makes two of them equal.

Sine checkpoints used by firmware: sample 0 is 0, sample 16 is 32767, sample 48 is −32767.
