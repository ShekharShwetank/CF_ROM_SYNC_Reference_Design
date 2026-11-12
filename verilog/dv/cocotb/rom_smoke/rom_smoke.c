#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

void main(void)
{
	uint32_t magic;

	rom_boot();
	ManagmentGpio_write(1);
	print("ID ");
	rom_print_hex32(rom_csr_read(ROM_ID));
	print("\n");
	magic = ((uint32_t)rom_read8(0) << 24) | ((uint32_t)rom_read8(1) << 16) |
		((uint32_t)rom_read8(2) << 8) | rom_read8(3);
	print("MAGIC ");
	rom_print_hex32(magic);
	print("\n");
}
