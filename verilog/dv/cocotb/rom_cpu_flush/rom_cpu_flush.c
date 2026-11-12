#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

void main(void)
{
	uint32_t crc = 0xFFFFFFFFu;
	uint32_t i;
	int b;
	uint8_t byte;

	uint32_t trailer;

	rom_boot();
	rom_flush_enable();
	/* The trailer is the CRC of the first 1020 bytes, not of itself. */
	for (i = 0; i < 0x3FCu; i++) {
		byte = rom_read8(i);
		crc ^= byte;
		for (b = 0; b < 8; b++)
			crc = (crc & 1u) ? ((crc >> 1) ^ 0xEDB88320u) : (crc >> 1);
	}
	crc ^= 0xFFFFFFFFu;
	trailer = rom_read8(0x3FC) | ((uint32_t)rom_read8(0x3FD) << 8) |
		  ((uint32_t)rom_read8(0x3FE) << 16) | ((uint32_t)rom_read8(0x3FF) << 24);
	ManagmentGpio_write(1);
	if (crc == ROM_IMAGE_CRC && crc == trailer &&
	    (rom_csr_read(ROM_STATUS) & ROM_STAT_FLUSH) == 0)
		print("CRC ok\n");
	else
		print("CRC fail\n");
	print("FLUSH ");
	rom_print_hex32(rom_csr_read(ROM_STATUS) & ROM_STAT_FLUSH);
	print("\n");
}
