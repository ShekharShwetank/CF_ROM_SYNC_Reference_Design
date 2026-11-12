#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

void main(void)
{
	uint32_t before;
	uint32_t after;

	rom_boot();
	(void)rom_read8(0);
	before = rom_csr_read(ROM_COUNT);
	rom_csr_write(ROM_CTRL, ROM_CTRL_RESET | 0x20u);
	after = rom_csr_read(ROM_COUNT);
	ManagmentGpio_write(1);
	if (before != 0 && after == before && (rom_csr_read(ROM_CTRL) & 0x20u) == 0)
		print("PULSE ok\n");
	else
		print("PULSE fail\n");
	if (after == before)
		print("COUNT ok\n");
	else
		print("COUNT fail\n");
	*(volatile uint32_t *)ROM_WIN = 0xFFFFFFFFu;
	if (rom_csr_read(ROM_STATUS) & ROM_STAT_WR)
		print("WRITE ok\n");
	else
		print("WRITE fail\n");
}
