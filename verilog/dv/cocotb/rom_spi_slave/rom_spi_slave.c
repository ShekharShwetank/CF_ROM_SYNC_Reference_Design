#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

void main(void)
{
	rom_boot();
	rom_csr_write(ROM_CTRL, ROM_CTRL_RESET);
	ManagmentGpio_write(1);
	while (1)
		;
}
