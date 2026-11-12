#include <firmware_apis.h>
#include "../../../../fw/cf_rom_demo.h"

static void delay(int n)
{
	int i;
	for (i = 0; i < n; i++)
		asm volatile("nop");
}

void main(void)
{
	rom_boot();
	ManagmentGpio_write(1);
	delay(20000);
	rom_stream_start(0, 0, 0, 1);
	rom_stream_wait();
	print("STREAM done\n");
}
