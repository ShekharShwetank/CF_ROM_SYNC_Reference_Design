`default_nettype none
/*
 * user_project_wrapper — CF_ROM_SYNC reference design.
 *
 * rom_ctrl and CF_ROM_SYNC are hard macros. This wrapper is synthesized:
 * tie cells, repeaters, and the clock tree live here. The ROM clock is
 * wb_clk_i, the same net that clocks rom_ctrl.
 */

module user_project_wrapper #(
    parameter BITS = 32
) (
`ifdef USE_POWER_PINS
    inout vdda1,
    inout vdda2,
    inout vssa1,
    inout vssa2,
    inout vccd1,
    inout vccd2,
    inout vssd1,
    inout vssd2,
`endif
    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output wbs_ack_o,
    output [31:0] wbs_dat_o,

    input  [127:0] la_data_in,
    output [127:0] la_data_out,
    input  [127:0] la_oenb,

    input  [`MPRJ_IO_PADS-1:0] io_in,
    output [`MPRJ_IO_PADS-1:0] io_out,
    output [`MPRJ_IO_PADS-1:0] io_oeb,

    inout [`MPRJ_IO_PADS-10:0] analog_io,

    input   user_clock2,

    output [2:0] user_irq
);

    wire [9:0] rom_a;
    wire [7:0] rom_do;
    wire rom_en;
    wire rom_rst;
    wire rom_oe;
    wire [8:0] gpio_in;
    wire [8:0] gpio_out;
    wire [8:0] gpio_oeb;

    assign gpio_in = io_in[16:8];
    assign io_out[16:8] = gpio_out;
    assign io_oeb[16:8] = gpio_oeb;
    assign io_out[7:0] = 8'h0;
    assign io_oeb[7:0] = 8'hFF;
    assign io_out[37:17] = 21'h0;
    assign io_oeb[37:17] = 21'h1FFFFF;
    assign la_data_out = 128'h0;
    assign user_irq = 3'h0;

    rom_ctrl u_rom_ctrl (
`ifdef USE_POWER_PINS
        .vccd1(vccd1),
        .vssd1(vssd1),
`endif
        .wb_clk_i(wb_clk_i),
        .wb_rst_i(wb_rst_i),
        .wbs_stb_i(wbs_stb_i),
        .wbs_cyc_i(wbs_cyc_i),
        .wbs_we_i(wbs_we_i),
        .wbs_sel_i(wbs_sel_i),
        .wbs_dat_i(wbs_dat_i),
        .wbs_adr_i(wbs_adr_i),
        .wbs_ack_o(wbs_ack_o),
        .wbs_dat_o(wbs_dat_o),
        .gpio_in(gpio_in),
        .gpio_out(gpio_out),
        .gpio_oeb(gpio_oeb),
        .rom_a(rom_a),
        .rom_en(rom_en),
        .rom_rst(rom_rst),
        .rom_oe(rom_oe),
        .rom_do(rom_do)
    );

    // Four inv_16 inputs per DO bit. The input pin is 0.033 pF, so four
    // of them are 0.134 pF before wire capacitance. The ROM minimum is
    // 0.111 pF. Synthesis does not define USE_POWER_PINS, so these cells
    // sit outside that guard. keep stops them being deleted; the resizer
    // ignore list rom_do stops them being swapped for a smaller inverter.
    wire [7:0] rom_do_ld0;
    wire [7:0] rom_do_ld1;
    wire [7:0] rom_do_ld2;
    wire [7:0] rom_do_ld3;

    genvar rom_do_i;
    generate
        for (rom_do_i = 0; rom_do_i < 8; rom_do_i = rom_do_i + 1) begin : rom_do_load
            /* verilator lint_off PINMISSING */
            (* keep *) sky130_fd_sc_hd__inv_16 u0 (
                .A(rom_do[rom_do_i]),
                .Y(rom_do_ld0[rom_do_i])
            );
            (* keep *) sky130_fd_sc_hd__inv_16 u1 (
                .A(rom_do[rom_do_i]),
                .Y(rom_do_ld1[rom_do_i])
            );
            (* keep *) sky130_fd_sc_hd__inv_16 u2 (
                .A(rom_do[rom_do_i]),
                .Y(rom_do_ld2[rom_do_i])
            );
            (* keep *) sky130_fd_sc_hd__inv_16 u3 (
                .A(rom_do[rom_do_i]),
                .Y(rom_do_ld3[rom_do_i])
            );
            /* verilator lint_on PINMISSING */
        end
    endgenerate

    CF_ROM_SYNC u_cf_rom_sync (
`ifdef USE_POWER_PINS
        .vpwr(vccd1),
        .vgnd(vssd1),
`else
        .vpwr(1'b1),
        .vgnd(1'b0),
`endif
        .DO(rom_do),
        .A(rom_a),
        .EN(rom_en),
        .CLK(wb_clk_i),
        .RST(rom_rst),
        .OE(rom_oe)
    );

    wire _unused = &{1'b0, la_data_in, la_oenb, user_clock2,
                     io_in[7:0], io_in[37:17],
                     rom_do_ld0, rom_do_ld1, rom_do_ld2, rom_do_ld3};
endmodule

`default_nettype wire
