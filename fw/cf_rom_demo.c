/* The driver used by the Caravel tests is header-only (cf_rom_demo.h),
 * because caravel-cocotb compiles the single test .c file. This file is
 * the same CRC the header inlines, for a host build that does not have
 * the management-firmware headers.
 */
#include <stdint.h>

uint32_t cf_rom_crc32(const uint8_t *data, uint32_t len)
{
	uint32_t crc = 0xFFFFFFFFu;
	uint32_t i;
	int b;

	for (i = 0; i < len; i++) {
		crc ^= data[i];
		for (b = 0; b < 8; b++)
			crc = (crc & 1u) ? ((crc >> 1) ^ 0xEDB88320u) : (crc >> 1);
	}
	return crc ^ 0xFFFFFFFFu;
}
