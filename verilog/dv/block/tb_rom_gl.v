`timescale 1ns/1ps
`default_nettype none

// Gate-level rom_ctrl plus the programmed ROM model.
module tb_rom_gl (
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
    input [37:0] io_in,
    output [37:0] io_out,
    output [37:0] io_oeb
);

    wire [9:0] rom_a;
    wire [7:0] rom_do;
    wire rom_en;
    wire rom_rst;
    wire rom_oe;
    wire [8:0] gpio_out;
    wire [8:0] gpio_oeb;
    wire vccd1;
    wire vssd1;

    assign vccd1 = 1'b1;
    assign vssd1 = 1'b0;
    assign io_out = {21'h0, gpio_out, 8'h0};
    assign io_oeb = {21'h1FFFFF, gpio_oeb, 8'hFF};

    rom_ctrl u_ctrl (
        .vccd1(vccd1),
        .vssd1(vssd1),
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
        .gpio_in(io_in[16:8]),
        .gpio_out(gpio_out),
        .gpio_oeb(gpio_oeb),
        .rom_a(rom_a),
        .rom_en(rom_en),
        .rom_rst(rom_rst),
        .rom_oe(rom_oe),
        .rom_do(rom_do)
    );

    CF_ROM_SYNC u_rom (
        .vpwr(1'b1),
        .vgnd(1'b0),
        .DO(rom_do),
        .A(rom_a),
        .EN(rom_en),
        .CLK(wb_clk_i),
        .RST(rom_rst),
        .OE(rom_oe)
    );
endmodule

`default_nettype wire
