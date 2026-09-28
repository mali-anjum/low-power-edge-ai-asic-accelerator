// Port-level golden-vector testbench for fpga/rtl/fpga_top.sv.
//
// Touches only fpga_top's ports (no hierarchical references into
// gen_pe[*]), so the SAME testbench runs unchanged against the RTL and
// against Yosys's flattened post-synthesis ECP5 netlist, where internal
// names like pe_acc no longer exist. The trade-off vs. the ASIC-side
// verification/tb_accelerator*.sv: the INT32 accumulator is not checked
// directly here, only the final requantized y_out lanes, busy, and done.
//
// Vector file (from fpga/scripts/make_vectors.py), one inference per line:
//   shift x0..x7 w00..w73 b0..b3 y0..y3   (decimal)
//
//   iverilog ... +VECTORS=<file>        (-DFPGA_INT4 selects the INT4 variant)
`ifdef FPGA_INT4
  `define TB_DW 4
`else
  `define TB_DW 8
`endif

module tb_fpga_top;

    localparam int DW = `TB_DW;
    localparam int TIMEOUT_CYCLES = 64;

    logic clk = 1'b0, rst_n = 1'b0, start = 1'b0;
    logic weight_wr_en = 1'b0, act_wr_en = 1'b0, bias_wr_en = 1'b0;
    logic [1:0]          weight_wr_pe = '0, bias_wr_pe = '0;
    logic [2:0]          weight_wr_idx = '0, act_wr_idx = '0;
    logic [DW-1:0]       weight_wr_data = '0, act_wr_data = '0;
    logic [31:0]         bias_wr_data = '0;
    logic [4:0]          shift_in = '0;
    wire                 busy, done;
    wire  [4*DW-1:0]     y_out;

    fpga_top dut (.*);

    always #5 clk = ~clk;

    int shift, x [8], w [8][4], b [4], exp_y [4];
    int n_vec = 0, vec_pass = 0, vec_fail = 0, lane_pass = 0, lane_fail = 0, proto_fail = 0;

    task automatic drive_cycle;
        @(posedge clk);
        #1;
    endtask

    task automatic run_vector;
        bit ok = 1'b1;
        int cycles;

        shift_in = shift[4:0];
        for (int i = 0; i < 8; i++)
            for (int j = 0; j < 4; j++) begin
                drive_cycle();
                weight_wr_en = 1'b1; weight_wr_pe = j[1:0]; weight_wr_idx = i[2:0];
                weight_wr_data = w[i][j][DW-1:0];
            end
        for (int i = 0; i < 8; i++) begin
            drive_cycle();
            weight_wr_en = 1'b0;
            act_wr_en = 1'b1; act_wr_idx = i[2:0]; act_wr_data = x[i][DW-1:0];
        end
        for (int j = 0; j < 4; j++) begin
            drive_cycle();
            act_wr_en = 1'b0;
            bias_wr_en = 1'b1; bias_wr_pe = j[1:0]; bias_wr_data = b[j];
        end
        drive_cycle();
        bias_wr_en = 1'b0;
        start = 1'b1;
        drive_cycle();
        start = 1'b0;

        cycles = 0;
        while (done !== 1'b1 && cycles < TIMEOUT_CYCLES) begin
            drive_cycle();
            cycles++;
        end
        if (done !== 1'b1) begin
            $display("vector %0d: FAIL -- done never asserted (timeout %0d cycles)", n_vec, TIMEOUT_CYCLES);
            proto_fail++;
            ok = 1'b0;
        end else begin
            for (int j = 0; j < 4; j++) begin
                int got;
                got = $signed(y_out[j*DW +: DW]);
                if (got === exp_y[j]) lane_pass++;
                else begin
                    lane_fail++;
                    ok = 1'b0;
                    $display("vector %0d neuron %0d: FAIL y=%0d expected %0d (shift=%0d)",
                             n_vec, j, got, exp_y[j], shift);
                end
            end
            drive_cycle();
            if (busy !== 1'b0 || done !== 1'b0) begin
                $display("vector %0d: FAIL -- busy/done did not clear after DONE", n_vec);
                proto_fail++;
                ok = 1'b0;
            end
        end

        if (ok) vec_pass++; else vec_fail++;
        n_vec++;
    endtask

    initial begin
        string path;
        int fd, r;

        if (!$value$plusargs("VECTORS=%s", path)) begin
            $display("ERROR: pass +VECTORS=<file>");
            $fatal(1);
        end
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("ERROR: cannot open %s", path);
            $fatal(1);
        end

        // Hold async reset for a few cycles, then allow the wrapper's
        // 2-flop synchroniser to release the core before the first write.
        repeat (4) @(posedge clk);
        #3 rst_n = 1'b1;
        repeat (4) @(posedge clk);

        // $fscanf reads into the scalar `v` first: iverilog cannot scan
        // directly into a variable-indexed array element.
        while (!$feof(fd)) begin
            int v;
            r = $fscanf(fd, "%d", shift);
            if (r != 1) break;
            for (int i = 0; i < 8; i++) begin r = $fscanf(fd, "%d", v); x[i] = v; end
            for (int i = 0; i < 8; i++)
                for (int j = 0; j < 4; j++) begin r = $fscanf(fd, "%d", v); w[i][j] = v; end
            for (int j = 0; j < 4; j++) begin r = $fscanf(fd, "%d", v); b[j] = v; end
            for (int j = 0; j < 4; j++) begin r = $fscanf(fd, "%d", v); exp_y[j] = v; end
            if (r != 1) begin
                $display("ERROR: truncated vector line %0d in %s", n_vec + 1, path);
                $fatal(1);
            end
            run_vector();
        end
        $fclose(fd);

        $display("----------------------------------------");
        $display("INT%0d %s", DW, path);
        $display("VECTORS: %0d  PASS: %0d  FAIL: %0d", n_vec, vec_pass, vec_fail);
        $display("OUTPUT LANES: %0d  PASS: %0d  FAIL: %0d  (protocol failures: %0d)",
                 lane_pass + lane_fail, lane_pass, lane_fail, proto_fail);
        if (n_vec > 0 && vec_fail == 0) $display("RESULT: BIT-EXACT");
        else                            $display("RESULT: MISMATCH");
        $finish;
    end

endmodule
