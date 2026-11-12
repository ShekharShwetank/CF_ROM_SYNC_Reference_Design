# Clock and Wishbone constraints for afe_wb. Analog_ctrl / adc_* treated as async.

set ::env(IO_SYNC) 0

if {[info exists ::env(CLOCK_PORT)] && $::env(CLOCK_PORT) != ""} {
	set clk_input $::env(CLOCK_PORT)
	create_clock [get_ports $clk_input] -name clk -period $::env(CLOCK_PERIOD)
} else {
	set clk_input __VIRTUAL_CLK__
	create_clock -name clk -period $::env(CLOCK_PERIOD)
}

set_propagated_clock [all_clocks]
set_clock_uncertainty $::env(SYNTH_CLOCK_UNCERTAINTY) [get_clocks {clk}]
set_clock_transition $::env(SYNTH_CLOCK_TRANSITION) [get_clocks {clk}]
set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
set_timing_derate -early [expr {1-$::env(SYNTH_TIMING_DERATE)}]
set_timing_derate -late [expr {1+$::env(SYNTH_TIMING_DERATE)}]

set_input_delay [expr $::env(CLOCK_PERIOD) * 0.5] -clock [get_clocks {clk}] [get_ports {wb_rst_i}]

set_multicycle_path -setup 2 -through [get_ports {wbs_ack_o}]
set_multicycle_path -hold 1  -through [get_ports {wbs_ack_o}]
set_multicycle_path -setup 2 -through [get_ports {wbs_cyc_i}]
set_multicycle_path -hold 1  -through [get_ports {wbs_cyc_i}]
set_multicycle_path -setup 2 -through [get_ports {wbs_stb_i}]
set_multicycle_path -hold 1  -through [get_ports {wbs_stb_i}]

set_clock_latency -source -max 5.57 [get_clocks {clk}]
set_clock_latency -source -min 4.65 [get_clocks {clk}]
set_input_transition 0.61 [get_ports $clk_input]

set_input_delay -max 3.89 -clock [get_clocks {clk}] [get_ports {wbs_adr_i[*]}]
set_input_delay -max 4.61 -clock [get_clocks {clk}] [get_ports {wbs_dat_i[*]}]
set_input_delay -max 3.17 -clock [get_clocks {clk}] [get_ports {wbs_sel_i[*]}]
set_input_delay -max 3.74 -clock [get_clocks {clk}] [get_ports {wbs_we_i}]
set_input_delay -max 4.13 -clock [get_clocks {clk}] [get_ports {wbs_stb_i}]
set_input_delay -max 4.74 -clock [get_clocks {clk}] [get_ports {wbs_cyc_i}]
set_input_delay -min 0.79 -clock [get_clocks {clk}] [get_ports {wbs_adr_i[*]}]
set_input_delay -min 1.04 -clock [get_clocks {clk}] [get_ports {wbs_dat_i[*]}]
set_input_delay -min 1.19 -clock [get_clocks {clk}] [get_ports {wbs_sel_i[*]}]
set_input_delay -min 1.65 -clock [get_clocks {clk}] [get_ports {wbs_we_i}]
set_input_delay -min 1.69 -clock [get_clocks {clk}] [get_ports {wbs_cyc_i}]
set_input_delay -min 1.86 -clock [get_clocks {clk}] [get_ports {wbs_stb_i}]

# Same transitions the wrapper applies. A zero-slew pin left a weak delay cell on wbs_adr_i.
set_input_transition -max 0.14  [get_ports {wbs_we_i}]
set_input_transition -max 0.15  [get_ports {wbs_stb_i}]
set_input_transition -max 0.17  [get_ports {wbs_cyc_i}]
set_input_transition -max 0.18  [get_ports {wbs_sel_i[*]}]
set_input_transition -max 0.84  [get_ports {wbs_dat_i[*]}]
set_input_transition -max 0.92  [get_ports {wbs_adr_i[*]}]
set_input_transition -min 0.07  [get_ports {wbs_adr_i[*]}]
set_input_transition -min 0.07  [get_ports {wbs_dat_i[*]}]
set_input_transition -min 0.09  [get_ports {wbs_cyc_i}]
set_input_transition -min 0.09  [get_ports {wbs_sel_i[*]}]
set_input_transition -min 0.09  [get_ports {wbs_we_i}]
set_input_transition -min 0.15  [get_ports {wbs_stb_i}]

set_output_delay -max 3.62 -clock [get_clocks {clk}] [get_ports {wbs_dat_o[*]}]
set_output_delay -max 8.41 -clock [get_clocks {clk}] [get_ports {wbs_ack_o}]
set_output_delay -min 1.13 -clock [get_clocks {clk}] [get_ports {wbs_dat_o[*]}]
set_output_delay -min 1.37 -clock [get_clocks {clk}] [get_ports {wbs_ack_o}]

set_load 0.19 [all_outputs]

# ROM pin budget from ip/CF_ROM_SYNC/timing/lib, all three liberties.
# Setup (-max) is the largest setup_rising constraint in the table.
#   A  1.872 ns  ss, fall, 4.2 ns slew (tt table max is 0.688 ns)
#   EN 2.192 ns  ss, fall, 4.2 ns slew (tt table max is 0.907 ns)
#   RST 0.602 ns ss (tt setup is negative)
# Hold (-min) is the negative of the largest hold at a 1.0 ns transition
# on both the pin and CLK, interpolated between the 0.6 ns and 1.8 ns
# table entries. The 4.2 ns entry is outside this macro's 1.0 ns max transition.
#   A   0.662 ns ss (tt table max is 0.562 ns; tt at 1.0 ns is 0.428 ns)
#   EN  no positive hold at 1.0 ns in any lib, so the min delay is 0
#   RST 0.588 ns ss (tt at 1.0 ns is 0.454 ns; tt at 4.2 ns is 1.318 ns)
# rom_do -max is the ss clock-to-DO at the 0.111 pF minimum load (16.350 ns).
# rom_do -min is the ff clock-to-DO at that load (1.907 ns).
# The wrapper, with the real ROM libs, is the signoff.
set_output_delay -max 1.872 -clock [get_clocks {clk}] [get_ports {rom_a[*]}]
set_output_delay -min -0.662 -clock [get_clocks {clk}] [get_ports {rom_a[*]}]
set_output_delay -max 2.192 -clock [get_clocks {clk}] [get_ports {rom_en}]
set_output_delay -min 0.000 -clock [get_clocks {clk}] [get_ports {rom_en}]
set_output_delay -max 0.602 -clock [get_clocks {clk}] [get_ports {rom_rst}]
set_output_delay -min -0.588 -clock [get_clocks {clk}] [get_ports {rom_rst}]
set_input_delay -max 16.350 -clock [get_clocks {clk}] [get_ports {rom_do[*]}]
set_input_delay -min 1.907 -clock [get_clocks {clk}] [get_ports {rom_do[*]}]
