SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TOPLEVEL = tb_rom_top
MODULE = test_rom_block
RTL_DIR = ../../rtl
ROOT = ../../..

VERILOG_SOURCES = \
	$(RTL_DIR)/rom_ctrl.v \
	$(ROOT)/build/CF_ROM_SYNC_sim.v \
	tb_rom_top.v

COCOTB_CONFIG ?= cocotb-config
PDK_ROOT ?= $(ROOT)/dependencies/pdks
PDK_VERILOG ?= $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog
GL_SOURCES = \
	$(PDK_VERILOG)/primitives.v \
	$(PDK_VERILOG)/sky130_fd_sc_hd.v \
	$(ROOT)/verilog/gl/rom_ctrl.v \
	$(ROOT)/build/CF_ROM_SYNC_sim.v \
	tb_rom_gl.v

include $(shell $(COCOTB_CONFIG) --makefiles)/Makefile.sim

# All 21 tests in test_rom_block.py. COCOTB_TESTCASE in the environment
# used to keep this to reset, lane reads, and the SPI ID command.
.PHONY: gl
gl:
	$(MAKE) clean
	env -u COCOTB_TESTCASE $(MAKE) TOPLEVEL=tb_rom_gl VERILOG_SOURCES="$(GL_SOURCES)" COMPILE_ARGS="-DUSE_POWER_PINS -DFUNCTIONAL -DUNIT_DELAY=\#1"

.PHONY: rom
rom:
	$(MAKE) -C $(ROOT) rom
