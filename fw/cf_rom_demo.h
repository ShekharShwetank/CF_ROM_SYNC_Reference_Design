/* Wishbone driver for the CF_ROM_SYNC reference controller.
 * Include firmware_apis.h first so print() is declared.
 */
#ifndef CF_ROM_DEMO_H
#define CF_ROM_DEMO_H

#include <stdint.h>
#include "rom_map.h"

#define ROM_WIN 0x30000000u
#define ROM_CSR 0x30001000u

#define ROM_ID     0u
#define ROM_CTRL   1u
#define ROM_STATUS 2u
#define ROM_ADDR   3u
#define ROM_DATA   4u
#define ROM_START  5u
#define ROM_LEN    6u
#define ROM_CFG    7u
#define ROM_CRC    8u
#define ROM_COUNT  9u

#define ROM_CTRL_RESET 0x000000C9u
#define ROM_CFG_RESET  0x00010000u
#define ROM_STAT_DONE  (1u << 1)
#define ROM_STAT_FLUSH (1u << 3)
#define ROM_STAT_WR    (1u << 4)

static inline uint32_t rom_csr_read(uint32_t index)
{
	return *(volatile uint32_t *)(ROM_CSR + (index << 2));
}

static inline void rom_csr_write(uint32_t index, uint32_t value)
{
	*(volatile uint32_t *)(ROM_CSR + (index << 2)) = value;
}

static inline uint32_t rom_read32(uint32_t addr)
{
	return *(volatile uint32_t *)(ROM_WIN + (addr & 0x3FFu));
}

static inline uint8_t rom_read8(uint32_t addr)
{
	return *(volatile uint8_t *)(ROM_WIN + (addr & 0x3FFu));
}

static inline uint8_t rom_seq_read(void)
{
	return (uint8_t)rom_csr_read(ROM_DATA);
}

static inline void rom_flush_enable(void)
{
	rom_csr_write(ROM_CTRL, ROM_CTRL_RESET | 0x6u);
}

static inline void rom_stream_start(uint32_t start, uint32_t len, uint32_t div, int crc)
{
	rom_csr_write(ROM_START, start);
	rom_csr_write(ROM_LEN, len);
	rom_csr_write(ROM_CFG, (crc ? 0x10000u : 0u) | ((div & 0xFFu) << 8) | 1u);
}

static inline void rom_stream_wait(void)
{
	while ((rom_csr_read(ROM_STATUS) & ROM_STAT_DONE) == 0)
		;
}

static inline uint32_t rom_crc32(const uint8_t *data, uint32_t len)
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

static inline void rom_print_hex32(uint32_t value)
{
	static const char hex[] = "0123456789ABCDEF";
	char buf[9];
	int i;

	for (i = 0; i < 8; i++)
		buf[i] = hex[(value >> (28 - 4 * i)) & 0xF];
	buf[8] = 0;
	print(buf);
}

static inline void rom_configure_pins(void)
{
	int pin;

	GPIOs_configure(6, GPIO_MODE_MGMT_STD_OUTPUT);
	GPIOs_configure(8, GPIO_MODE_USER_STD_OUTPUT);
	GPIOs_configure(9, GPIO_MODE_USER_STD_OUTPUT);
	GPIOs_configure(10, GPIO_MODE_USER_STD_OUTPUT);
	GPIOs_configure(11, GPIO_MODE_USER_STD_INPUT_NOPULL);
	GPIOs_configure(12, GPIO_MODE_USER_STD_INPUT_NOPULL);
	GPIOs_configure(13, GPIO_MODE_USER_STD_INPUT_NOPULL);
	GPIOs_configure(14, GPIO_MODE_USER_STD_INPUT_NOPULL);
	GPIOs_configure(15, GPIO_MODE_USER_STD_BIDIRECTIONAL);
	GPIOs_configure(16, GPIO_MODE_USER_STD_OUTPUT);
	for (pin = 17; pin <= 37; pin++)
		GPIOs_configure(pin, GPIO_MODE_USER_STD_INPUT_NOPULL);
	GPIOs_loadConfigs();
}

static inline void rom_boot(void)
{
	ManagmentGpio_write(0);
	ManagmentGpio_outputEnable();
	enableHkSpi(0);
	rom_configure_pins();
	UART_enableTX(1);
	User_enableIF();
}

#endif
