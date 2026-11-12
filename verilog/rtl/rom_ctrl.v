`default_nettype none
/*
 * rom_ctrl — Wishbone front end for CF_ROM_SYNC.
 *
 * One clock, wb_clk_i. The wrapper ties that same net to the ROM CLK pin.
 * A read is a flush (optional), one EN pulse, WS wait cycles, then a sample.
 * SPI has priority over the stream master, which has priority over the CPU.
 *
 * CTRL resets to 0x000000C9: OE, one wait state, SPI slave and pin trigger
 * enabled. Bit 3 is the wait-state LSB, so the reset word is 0xC9.
 *
 * gpio_*[k] is mprj_io[8+k].
 */

module rom_ctrl (
`ifdef USE_POWER_PINS
    inout vccd1,
    inout vssd1,
`endif
    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output reg wbs_ack_o,
    output reg [31:0] wbs_dat_o,

    input [8:0] gpio_in,
    output [8:0] gpio_out,
    output [8:0] gpio_oeb,

    output [9:0] rom_a,
    output rom_en,
    output rom_rst,
    output rom_oe,
    input [7:0] rom_do
);

    localparam [3:0] W_ID        = 4'd0;
    localparam [3:0] W_CTRL      = 4'd1;
    localparam [3:0] W_STATUS    = 4'd2;
    localparam [3:0] W_ADDR      = 4'd3;
    localparam [3:0] W_DATA      = 4'd4;
    localparam [3:0] W_START     = 4'd5;
    localparam [3:0] W_LEN       = 4'd6;
    localparam [3:0] W_CFG       = 4'd7;
    localparam [3:0] W_CRC       = 4'd8;
    localparam [3:0] W_COUNT     = 4'd9;

    localparam [2:0] S_IDLE      = 3'd0;
    localparam [2:0] S_FLUSH     = 3'd1;
    localparam [2:0] S_FLUSH_CHK = 3'd2;
    localparam [2:0] S_CAPTURE   = 3'd3;
    localparam [2:0] S_WAIT      = 3'd4;
    localparam [2:0] S_SAMPLE    = 3'd5;

    localparam [2:0] OWN_NONE    = 3'd0;
    localparam [2:0] OWN_SPI     = 3'd1;
    localparam [2:0] OWN_STRM    = 3'd2;
    localparam [2:0] OWN_PULSE   = 3'd3;
    localparam [2:0] OWN_WB      = 3'd4;

    localparam [2:0] ST_IDLE     = 3'd0;
    localparam [2:0] ST_LOAD     = 3'd1;
    localparam [2:0] ST_LOW      = 3'd2;
    localparam [2:0] ST_HIGH     = 3'd3;

    localparam [2:0] SPI_IDLE    = 3'd0;
    localparam [2:0] SPI_CMD     = 3'd1;
    localparam [2:0] SPI_ADDR    = 3'd2;
    localparam [2:0] SPI_WAIT    = 3'd3;
    localparam [2:0] SPI_DATA    = 3'd4;
    localparam [2:0] SPI_ID      = 3'd5;
    localparam [2:0] SPI_ZERO    = 3'd6;

    reg ctrl_oe;
    reg ctrl_flush;
    reg ctrl_flush_chk;
    reg [1:0] ctrl_ws;
    reg ctrl_spis_en;
    reg ctrl_trig_en;
    reg pulse_pend;

    reg flush_err;
    reg wr_err;
    reg stream_done;

    reg [9:0] seq_addr;
    reg [9:0] strm_start;
    reg [9:0] strm_len;
    reg [7:0] clkdiv;
    reg append_crc;
    reg [31:0] crc_reg;
    reg [31:0] rd_count;

    reg [2:0] rd_state;
    reg [2:0] owner;
    reg [9:0] pin_addr;
    reg [1:0] ws_left;
    reg [7:0] rd_data;
    reg rd_done;

    reg wb_busy;
    reg wb_seq;
    reg [9:0] wb_base;
    reg [3:0] wb_sel;
    reg [1:0] wb_beat;
    reg [2:0] wb_nbeats;
    reg [31:0] wb_acc;

    reg [2:0] strm_state;
    reg strm_need;
    reg [9:0] strm_addr_r;
    reg [7:0] strm_div;
    reg strm_append;
    reg [10:0] pay_left;
    reg crc_phase;
    reg [1:0] crc_sent;
    reg [31:0] crc_run;
    reg [7:0] sh;
    reg [2:0] bitn;
    reg [7:0] div_cnt;
    reg cs_n;
    reg sck;
    reg sdo;

    reg [2:0] spi_state;
    reg spi_need;
    reg spi_need_is_prefetch;
    reg [9:0] spi_need_addr;
    reg [9:0] spi_cur_addr;
    reg [7:0] spi_shift;
    reg [7:0] spi_next;
    reg spi_next_valid;
    reg spi_miso;
    reg [2:0] spi_bit;
    reg [6:0] cmd_sr;
    reg [2:0] cmd_bits;
    reg [8:0] addr_sr;
    reg [3:0] addr_bits;
    reg [22:0] id_shift;
    reg spi_arm;

    reg sck_m, sck_s, sck_lvl;
    reg [1:0] sck_run;
    reg csn_m, csn_s;
    reg mosi_m, mosi_s;
    reg trig_m, trig_s, trig_d;

    wire in_win = (wbs_adr_i[31:16] == 16'h3000);
    wire rom_sel = in_win && (wbs_adr_i[15:10] == 6'h0);
    wire csr_sel = in_win && (wbs_adr_i[15:12] == 4'h1) &&
                   (wbs_adr_i[11:6] == 6'h0) && (wbs_adr_i[5:2] <= 4'd9);
    wire [3:0] csr_word = wbs_adr_i[5:2];
    wire fire = wbs_cyc_i & wbs_stb_i & ~wb_busy & ~wbs_ack_o & in_win;

    wire sck_rise = (sck_run == 2'd3) && (sck_s == 1'b1) && (sck_lvl == 1'b0);
    wire sck_fall = (sck_run == 2'd3) && (sck_s == 1'b0) && (sck_lvl == 1'b1);
    wire trig_rise = trig_s & ~trig_d;

    wire strm_busy = (strm_state != ST_IDLE);
    wire spi_active = ctrl_spis_en & ~csn_s;
    wire engine_busy = (rd_state != S_IDLE);
    wire busy = engine_busy | strm_busy | spi_active | wb_busy;

    wire [31:0] crc_final = crc_run ^ 32'hFFFFFFFF;

    wire [2:0] sel_count = {2'b0, wbs_sel_i[0]} + {2'b0, wbs_sel_i[1]} +
                           {2'b0, wbs_sel_i[2]} + {2'b0, wbs_sel_i[3]};
    wire [9:0] wb_beat_addr = (wb_base + {8'b0, wb_beat}) & 10'h3FF;

    reg [1:0] wb_lane;
    reg [2:0] lane_i;
    reg [2:0] seen_lane;
    always @* begin
        wb_lane = 2'b0;
        seen_lane = 3'd0;
        for (lane_i = 3'd0; lane_i < 3'd4; lane_i = lane_i + 3'd1) begin
            if (wb_sel[lane_i[1:0]]) begin
                if (seen_lane == {1'b0, wb_beat})
                    wb_lane = lane_i[1:0];
                seen_lane = seen_lane + 3'd1;
            end
        end
    end

    reg [31:0] wb_inserted;
    always @* begin
        wb_inserted = wb_acc;
        case (wb_lane)
            2'd0: wb_inserted[7:0] = rd_data;
            2'd1: wb_inserted[15:8] = rd_data;
            2'd2: wb_inserted[23:16] = rd_data;
            default: wb_inserted[31:24] = rd_data;
        endcase
    end

    reg [31:0] crc_next;
    reg [3:0] crc_i;
    reg [31:0] crc_c;
    always @* begin
        crc_c = crc_run ^ {24'h0, rd_data};
        for (crc_i = 4'd0; crc_i < 4'd8; crc_i = crc_i + 4'd1)
            crc_c = crc_c[0] ? ((crc_c >> 1) ^ 32'hEDB88320) : (crc_c >> 1);
        crc_next = crc_c;
    end

    function automatic [7:0] crc_byte;
        input [31:0] crc;
        input [1:0] index;
        begin
            case (index)
                2'd0: crc_byte = crc[7:0];
                2'd1: crc_byte = crc[15:8];
                2'd2: crc_byte = crc[23:16];
                default: crc_byte = crc[31:24];
            endcase
        end
    endfunction

    function automatic crc_msb;
        input [31:0] crc;
        input [1:0] index;
        /* verilator lint_off UNUSEDSIGNAL */
        reg [7:0] byte_i;
        /* verilator lint_on UNUSEDSIGNAL */
        begin
            byte_i = crc_byte(crc, index);
            crc_msb = byte_i[7];
        end
    endfunction

    reg [31:0] csr_rdata;
    always @* begin
        case (csr_word)
            W_ID: csr_rdata = 32'h524F4D01;
            W_CTRL: csr_rdata = {24'h0, ctrl_trig_en, ctrl_spis_en, 1'b0,
                                 ctrl_ws, ctrl_flush_chk, ctrl_flush, ctrl_oe};
            W_STATUS: csr_rdata = {26'h0, strm_busy, wr_err, flush_err,
                                   spi_active, stream_done, busy};
            W_ADDR: csr_rdata = {22'h0, seq_addr};
            W_START: csr_rdata = {22'h0, strm_start};
            W_LEN: csr_rdata = {22'h0, strm_len};
            W_CFG: csr_rdata = {15'h0, append_crc, clkdiv, 8'h0};
            W_CRC: csr_rdata = crc_reg;
            W_COUNT: csr_rdata = rd_count;
            default: csr_rdata = 32'h0;
        endcase
    end

    always @(posedge wb_clk_i) begin
        if (wb_rst_i) begin
            ctrl_oe <= 1'b1;
            ctrl_flush <= 1'b0;
            ctrl_flush_chk <= 1'b0;
            ctrl_ws <= 2'd1;
            ctrl_spis_en <= 1'b1;
            ctrl_trig_en <= 1'b1;
            pulse_pend <= 1'b0;
            flush_err <= 1'b0;
            wr_err <= 1'b0;
            stream_done <= 1'b0;
            seq_addr <= 10'h0;
            strm_start <= 10'h0;
            strm_len <= 10'h0;
            clkdiv <= 8'h0;
            append_crc <= 1'b1;
            crc_reg <= 32'h0;
            rd_count <= 32'h0;
            rd_state <= S_IDLE;
            owner <= OWN_NONE;
            pin_addr <= 10'h0;
            ws_left <= 2'h0;
            rd_data <= 8'h0;
            rd_done <= 1'b0;
            wb_busy <= 1'b0;
            wb_seq <= 1'b0;
            wb_base <= 10'h0;
            wb_sel <= 4'h0;
            wb_beat <= 2'h0;
            wb_nbeats <= 3'h0;
            wb_acc <= 32'h0;
            wbs_ack_o <= 1'b0;
            wbs_dat_o <= 32'h0;
            strm_state <= ST_IDLE;
            strm_need <= 1'b0;
            strm_addr_r <= 10'h0;
            strm_div <= 8'h0;
            strm_append <= 1'b1;
            pay_left <= 11'h0;
            crc_phase <= 1'b0;
            crc_sent <= 2'h0;
            crc_run <= 32'hFFFFFFFF;
            sh <= 8'h0;
            bitn <= 3'h0;
            div_cnt <= 8'h0;
            cs_n <= 1'b1;
            sck <= 1'b0;
            sdo <= 1'b0;
            spi_state <= SPI_IDLE;
            spi_need <= 1'b0;
            spi_need_is_prefetch <= 1'b0;
            spi_need_addr <= 10'h0;
            spi_cur_addr <= 10'h0;
            spi_shift <= 8'h0;
            spi_next <= 8'h0;
            spi_next_valid <= 1'b0;
            spi_miso <= 1'b0;
            spi_bit <= 3'h0;
            cmd_sr <= 7'h0;
            cmd_bits <= 3'h0;
            addr_sr <= 9'h0;
            addr_bits <= 4'h0;
            id_shift <= 23'h0;
            spi_arm <= 1'b0;
            sck_m <= 1'b0;
            sck_s <= 1'b0;
            sck_lvl <= 1'b0;
            sck_run <= 2'h0;
            csn_m <= 1'b1;
            csn_s <= 1'b1;
            mosi_m <= 1'b0;
            mosi_s <= 1'b0;
            trig_m <= 1'b0;
            trig_s <= 1'b0;
            trig_d <= 1'b0;
        end else begin
            rd_done <= 1'b0;
            wbs_ack_o <= 1'b0;

            sck_m <= gpio_in[4];
            sck_s <= sck_m;
            csn_m <= gpio_in[5];
            csn_s <= csn_m;
            mosi_m <= gpio_in[6];
            mosi_s <= mosi_m;
            trig_m <= gpio_in[3];
            trig_s <= trig_m;
            trig_d <= trig_s;
            if (sck_s == sck_lvl)
                sck_run <= 2'h0;
            else if (sck_run == 2'd3) begin
                sck_lvl <= sck_s;
                sck_run <= 2'h0;
            end else
                sck_run <= sck_run + 2'd1;

            if (fire && rom_sel && wbs_we_i) begin
                wr_err <= 1'b1;
                wbs_ack_o <= 1'b1;
                wbs_dat_o <= 32'h0;
            end else if (fire && rom_sel && !wbs_we_i) begin
                if (sel_count == 3'd0) begin
                    wbs_ack_o <= 1'b1;
                    wbs_dat_o <= 32'h0;
                end else begin
                    wb_busy <= 1'b1;
                    wb_seq <= 1'b0;
                    wb_base <= wbs_adr_i[9:0];
                    wb_sel <= wbs_sel_i;
                    wb_beat <= 2'h0;
                    wb_nbeats <= sel_count;
                    wb_acc <= 32'h0;
                end
            end else if (fire && csr_sel && wbs_we_i) begin
                wbs_ack_o <= 1'b1;
                case (csr_word)
                    W_CTRL: begin
                        ctrl_oe <= wbs_dat_i[0];
                        ctrl_flush <= wbs_dat_i[1];
                        ctrl_flush_chk <= wbs_dat_i[2];
                        ctrl_ws <= wbs_dat_i[4:3];
                        ctrl_spis_en <= wbs_dat_i[6];
                        ctrl_trig_en <= wbs_dat_i[7];
                        if (wbs_dat_i[5])
                            pulse_pend <= 1'b1;
                    end
                    W_STATUS: begin
                        if (wbs_dat_i[1])
                            stream_done <= 1'b0;
                        if (wbs_dat_i[3])
                            flush_err <= 1'b0;
                        if (wbs_dat_i[4])
                            wr_err <= 1'b0;
                    end
                    W_ADDR: begin
                        seq_addr <= wbs_dat_i[9:0];
                        if ((rd_state == S_IDLE) && !rd_done)
                            pin_addr <= wbs_dat_i[9:0];
                    end
                    W_START: strm_start <= wbs_dat_i[9:0];
                    W_LEN: strm_len <= wbs_dat_i[9:0];
                    W_CFG: begin
                        clkdiv <= wbs_dat_i[15:8];
                        append_crc <= wbs_dat_i[16];
                        if (wbs_dat_i[0] && (strm_state == ST_IDLE)) begin
                            strm_state <= ST_LOAD;
                            strm_need <= 1'b1;
                            strm_addr_r <= strm_start;
                            strm_div <= wbs_dat_i[15:8];
                            strm_append <= wbs_dat_i[16];
                            pay_left <= (strm_len == 10'h0) ? 11'd1024 : {1'b0, strm_len};
                            crc_phase <= 1'b0;
                            crc_sent <= 2'h0;
                            crc_run <= 32'hFFFFFFFF;
                            cs_n <= 1'b0;
                            sck <= 1'b0;
                            sdo <= 1'b0;
                        end
                    end
                    default: ;
                endcase
            end else if (fire && csr_sel && !wbs_we_i && (csr_word == W_DATA)) begin
                wb_busy <= 1'b1;
                wb_seq <= 1'b1;
                wb_base <= seq_addr;
                wb_sel <= 4'h1;
                wb_beat <= 2'h0;
                wb_nbeats <= 3'd1;
                wb_acc <= 32'h0;
            end else if (fire && csr_sel && !wbs_we_i) begin
                wbs_ack_o <= 1'b1;
                wbs_dat_o <= csr_rdata;
            end else if (fire) begin
                wbs_ack_o <= 1'b1;
                wbs_dat_o <= 32'h0;
            end

            if (trig_rise && ctrl_trig_en && (strm_state == ST_IDLE)) begin
                strm_state <= ST_LOAD;
                strm_need <= 1'b1;
                strm_addr_r <= strm_start;
                strm_div <= clkdiv;
                strm_append <= append_crc;
                pay_left <= (strm_len == 10'h0) ? 11'd1024 : {1'b0, strm_len};
                crc_phase <= 1'b0;
                crc_sent <= 2'h0;
                crc_run <= 32'hFFFFFFFF;
                cs_n <= 1'b0;
                sck <= 1'b0;
                sdo <= 1'b0;
            end

            if (rd_done && (owner == OWN_WB) && wb_busy) begin
                wb_acc <= wb_inserted;
                if (({1'b0, wb_beat} + 3'd1) >= wb_nbeats) begin
                    wb_busy <= 1'b0;
                    wbs_ack_o <= 1'b1;
                    wbs_dat_o <= wb_inserted;
                    if (wb_seq)
                        seq_addr <= (seq_addr + 10'd1) & 10'h3FF;
                end else
                    wb_beat <= wb_beat + 2'd1;
            end

            if (rd_done && (owner == OWN_STRM) && (strm_state == ST_LOAD)) begin
                strm_need <= 1'b0;
                sh <= rd_data;
                sdo <= rd_data[7];
                bitn <= 3'd7;
                sck <= 1'b0;
                div_cnt <= strm_div;
                strm_state <= ST_LOW;
                if (!crc_phase) begin
                    crc_run <= crc_next;
                    pay_left <= pay_left - 11'd1;
                end
            end else if ((strm_state == ST_LOW) || (strm_state == ST_HIGH)) begin
                if (div_cnt == 8'h0) begin
                    div_cnt <= strm_div;
                    if (strm_state == ST_LOW) begin
                        sck <= 1'b1;
                        strm_state <= ST_HIGH;
                    end else begin
                        sck <= 1'b0;
                        if (bitn == 3'd0) begin
                            if (!crc_phase) begin
                                if (pay_left == 11'h0) begin
                                    crc_reg <= crc_final;
                                    if (strm_append) begin
                                        crc_phase <= 1'b1;
                                        crc_sent <= 2'd0;
                                        sh <= crc_byte(crc_final, 2'd0);
                                        sdo <= crc_msb(crc_final, 2'd0);
                                        bitn <= 3'd7;
                                        strm_state <= ST_LOW;
                                    end else begin
                                        cs_n <= 1'b1;
                                        sdo <= 1'b0;
                                        strm_state <= ST_IDLE;
                                        stream_done <= 1'b1;
                                    end
                                end else begin
                                    strm_addr_r <= (strm_addr_r + 10'd1) & 10'h3FF;
                                    strm_need <= 1'b1;
                                    strm_state <= ST_LOAD;
                                end
                            end else if (crc_sent == 2'd3) begin
                                cs_n <= 1'b1;
                                sdo <= 1'b0;
                                strm_state <= ST_IDLE;
                                stream_done <= 1'b1;
                            end else begin
                                crc_sent <= crc_sent + 2'd1;
                                sh <= crc_byte(crc_reg, crc_sent + 2'd1);
                                sdo <= crc_msb(crc_reg, crc_sent + 2'd1);
                                bitn <= 3'd7;
                                strm_state <= ST_LOW;
                            end
                        end else begin
                            bitn <= bitn - 3'd1;
                            sdo <= sh[bitn - 3'd1];
                            strm_state <= ST_LOW;
                        end
                    end
                end else
                    div_cnt <= div_cnt - 8'd1;
            end

            if (!csn_s && ctrl_spis_en) begin
                case (spi_state)
                    SPI_IDLE: begin
                        spi_state <= SPI_CMD;
                        cmd_bits <= 3'd0;
                        cmd_sr <= 7'h0;
                        addr_bits <= 4'h0;
                        spi_miso <= 1'b0;
                    end
                    SPI_CMD: if (sck_rise) begin
                        if (cmd_bits == 3'd7) begin
                            if ({cmd_sr, mosi_s} == 8'h03) begin
                                spi_state <= SPI_ADDR;
                                addr_bits <= 4'h0;
                                addr_sr <= 9'h0;
                            end else if ({cmd_sr, mosi_s} == 8'h9F) begin
                                id_shift <= 23'h4F5201;
                                spi_miso <= 1'b1;
                                spi_arm <= 1'b1;
                                spi_state <= SPI_ID;
                            end else begin
                                spi_miso <= 1'b0;
                                spi_state <= SPI_ZERO;
                            end
                        end else begin
                            cmd_sr <= {cmd_sr[5:0], mosi_s};
                            cmd_bits <= cmd_bits + 3'd1;
                        end
                    end
                    SPI_ADDR: if (sck_rise) begin
                        if (addr_bits == 4'd15) begin
                            spi_need_addr <= {addr_sr, mosi_s};
                            spi_need <= 1'b1;
                            spi_need_is_prefetch <= 1'b0;
                            spi_next_valid <= 1'b0;
                            spi_state <= SPI_WAIT;
                        end else begin
                            addr_sr <= {addr_sr[7:0], mosi_s};
                            addr_bits <= addr_bits + 4'd1;
                        end
                    end
                    SPI_WAIT: ;
                    SPI_DATA: if (sck_fall) begin
                        if (spi_arm)
                            spi_arm <= 1'b0;
                        else if (spi_bit == 3'd0) begin
                            if (spi_next_valid) begin
                                spi_shift <= spi_next;
                                spi_miso <= spi_next[7];
                                spi_bit <= 3'd7;
                                spi_next_valid <= 1'b0;
                                spi_cur_addr <= (spi_cur_addr + 10'd1) & 10'h3FF;
                                spi_need <= 1'b1;
                                spi_need_is_prefetch <= 1'b1;
                                spi_need_addr <= (spi_cur_addr + 10'd2) & 10'h3FF;
                            end
                        end else begin
                            spi_bit <= spi_bit - 3'd1;
                            spi_miso <= spi_shift[spi_bit - 3'd1];
                        end
                    end
                    SPI_ID: if (sck_fall) begin
                        if (spi_arm)
                            spi_arm <= 1'b0;
                        else begin
                            spi_miso <= id_shift[22];
                            id_shift <= {id_shift[21:0], 1'b0};
                        end
                    end
                    SPI_ZERO: spi_miso <= 1'b0;
                    default: ;
                endcase
            end
            if (csn_s || !ctrl_spis_en) begin
                spi_state <= SPI_IDLE;
                spi_need <= 1'b0;
                spi_next_valid <= 1'b0;
                spi_miso <= 1'b0;
            end

            if (rd_done && (owner == OWN_SPI)) begin
                if ((spi_state == SPI_WAIT) && !spi_need_is_prefetch) begin
                    spi_shift <= rd_data;
                    spi_miso <= rd_data[7];
                    spi_bit <= 3'd7;
                    spi_cur_addr <= spi_need_addr;
                    spi_state <= SPI_DATA;
                    spi_arm <= 1'b1;
                    spi_need <= 1'b1;
                    spi_need_is_prefetch <= 1'b1;
                    spi_need_addr <= (spi_need_addr + 10'd1) & 10'h3FF;
                    spi_next_valid <= 1'b0;
                end else begin
                    spi_next <= rd_data;
                    spi_next_valid <= 1'b1;
                    spi_need <= 1'b0;
                end
            end
            if (csn_s || !ctrl_spis_en) begin
                spi_state <= SPI_IDLE;
                spi_need <= 1'b0;
                spi_next_valid <= 1'b0;
                spi_arm <= 1'b0;
            end

            case (rd_state)
                S_IDLE: begin
                    if (rd_done)
                        owner <= OWN_NONE;
                    else if (!ctrl_oe && (spi_need || strm_need || wb_busy)) begin
                        if (spi_need)
                            owner <= OWN_SPI;
                        else if (strm_need)
                            owner <= OWN_STRM;
                        else
                            owner <= OWN_WB;
                        rd_data <= 8'h00;
                        rd_done <= 1'b1;
                    end else if (spi_need) begin
                        owner <= OWN_SPI;
                        pin_addr <= spi_need_addr;
                        rd_state <= ctrl_flush ? S_FLUSH : S_CAPTURE;
                    end else if (strm_need && (spi_state == SPI_IDLE)) begin
                        owner <= OWN_STRM;
                        pin_addr <= strm_addr_r;
                        rd_state <= ctrl_flush ? S_FLUSH : S_CAPTURE;
                    end else if (pulse_pend && (spi_state == SPI_IDLE)) begin
                        owner <= OWN_PULSE;
                        pulse_pend <= 1'b0;
                        rd_state <= S_FLUSH;
                    end else if (wb_busy && (spi_state == SPI_IDLE) && !strm_need) begin
                        owner <= OWN_WB;
                        pin_addr <= wb_beat_addr;
                        rd_state <= ctrl_flush ? S_FLUSH : S_CAPTURE;
                    end
                end
                S_FLUSH: begin
                    if (owner == OWN_PULSE) begin
                        rd_state <= S_IDLE;
                        rd_done <= 1'b1;
                    end else if (ctrl_flush_chk)
                        rd_state <= S_FLUSH_CHK;
                    else
                        rd_state <= S_CAPTURE;
                end
                S_FLUSH_CHK: begin
                    if (rom_do !== 8'h00)
                        flush_err <= 1'b1;
                    rd_state <= S_CAPTURE;
                end
                S_CAPTURE: begin
                    rd_count <= rd_count + 32'd1;
                    if (ctrl_ws == 2'd0)
                        rd_state <= S_SAMPLE;
                    else begin
                        rd_state <= S_WAIT;
                        ws_left <= ctrl_ws - 2'd1;
                    end
                end
                S_WAIT: begin
                    if (ws_left == 2'd0)
                        rd_state <= S_SAMPLE;
                    else
                        ws_left <= ws_left - 2'd1;
                end
                S_SAMPLE: begin
                    rd_data <= rom_do;
                    rd_done <= 1'b1;
                    rd_state <= S_IDLE;
                end
                default: rd_state <= S_IDLE;
            endcase
        end
    end

    assign rom_a = pin_addr;
    assign rom_en = (rd_state == S_CAPTURE);
    assign rom_rst = (rd_state == S_FLUSH);
    assign rom_oe = ctrl_oe;

    assign gpio_out[0] = sck;
    assign gpio_out[1] = sdo;
    assign gpio_out[2] = cs_n;
    assign gpio_out[6:3] = 4'h0;
    assign gpio_out[7] = spi_miso;
    assign gpio_out[8] = busy;
    assign gpio_oeb[2:0] = 3'h0;
    assign gpio_oeb[6:3] = 4'hF;
    assign gpio_oeb[7] = ~(ctrl_spis_en & ~csn_s);
    assign gpio_oeb[8] = 1'b0;

    wire _unused = &{1'b0, wbs_dat_i[31:17], wbs_adr_i[1:0], gpio_in[2:0], gpio_in[8:7]};
endmodule

`default_nettype wire
