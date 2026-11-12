#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

static int16_t sample_at(uint32_t addr)
{
	int16_t value = (int16_t)(rom_read8(addr) | (rom_read8(addr + 1) << 8));
	return value;
}

void main(void)
{
	int16_t s0;
	int16_t s16;
	int16_t s48;

	rom_boot();
	s0 = sample_at(0x300);
	s16 = sample_at(0x320);
	s48 = sample_at(0x360);
	ManagmentGpio_write(1);
	if (s0 == ROM_SINE_0 && s16 == ROM_SINE_16 && s48 == ROM_SINE_48)
		print("SINE ok\n");
	else
		print("SINE fail\n");
}
