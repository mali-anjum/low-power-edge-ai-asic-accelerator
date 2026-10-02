// FPGA top wrapper (Lattice ECP5) around the UNMODIFIED ASIC RTL.
//
// Adds exactly one thing: a 2-flop reset synchroniser (asynchronous
// assert, synchronous de-assert). The ASIC flow drives rst_n from a
// testbench/pad with no synchroniser because OpenLane's STA does not check
// reset recovery/removal for this design; on an FPGA, rst_n comes from a
// button or host GPIO that is asynchronous to clk, and releasing an async
// reset near a clock edge can leave some flops in reset and others out.
//
// Everything else is a straight port pass-through -- no pipelining, no
// I/O registers, no datapath logic -- so the FPGA netlist computes the
// same function as the SKY130 netlist and can be checked against the same
// golden vectors. The variant is selected at compile time:
//
//   (default)   -> rtl/accelerator_top.sv                         (INT8)
//   -DFPGA_INT4 -> designs/accelerator_int4_parallel/accelerator_top_int4.sv
//                  (the same pass-through wrapper OpenLane used for INT4)
`ifdef FPGA_INT4
  `define FPGA_DW 4
`else
  `define FPGA_DW 8
`endif

module fpga_top (
    input  logic clk,
    input  logic rst_n,          // asynchronous, active-low (button / host)
    input  logic start,

    input  logic                     weight_wr_en,
    input  logic [1:0]               weight_wr_pe,
    input  logic [2:0]               weight_wr_idx,
    input  logic signed [`FPGA_DW-1:0] weight_wr_data,

    input  logic                     act_wr_en,
    input  logic [2:0]               act_wr_idx,
    input  logic signed [`FPGA_DW-1:0] act_wr_data,

    input  logic                     bias_wr_en,
    input  logic [1:0]               bias_wr_pe,
    input  logic signed [31:0]       bias_wr_data,

    input  logic [4:0]               shift_in,

    output logic                     busy,
    output logic                     done,
    output logic [4*`FPGA_DW-1:0]    y_out
);

    // rst_sync is flopped on clk yet drives the core's async resets --
    // that is the synchroniser's whole purpose, hence the waiver.
    /* verilator lint_off SYNCASYNCNET */
    logic [1:0] rst_sync;
    /* verilator lint_on SYNCASYNCNET */
    logic       rst_n_sync;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) rst_sync <= 2'b00;
        else        rst_sync <= {rst_sync[0], 1'b1};
    end

    assign rst_n_sync = rst_sync[1];

`ifdef FPGA_INT4
    accelerator_top_int4 u_accel (
`else
    accelerator_top #(
        .DATA_WIDTH (8),
        .NUM_INPUTS (8),
        .NUM_NEURONS(4),
        .ACC_WIDTH  (32),
        .SHIFT_WIDTH(5)
    ) u_accel (
`endif
        .clk           (clk),
        .rst_n         (rst_n_sync),
        .start         (start),
        .weight_wr_en  (weight_wr_en),
        .weight_wr_pe  (weight_wr_pe),
        .weight_wr_idx (weight_wr_idx),
        .weight_wr_data(weight_wr_data),
        .act_wr_en     (act_wr_en),
        .act_wr_idx    (act_wr_idx),
        .act_wr_data   (act_wr_data),
        .bias_wr_en    (bias_wr_en),
        .bias_wr_pe    (bias_wr_pe),
        .bias_wr_data  (bias_wr_data),
        .shift_in      (shift_in),
        .busy          (busy),
        .done          (done),
        .y_out         (y_out)
    );

endmodule
