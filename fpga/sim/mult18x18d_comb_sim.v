// Simulation model for the ECP5 MULT18X18D DSP block, restricted to the
// one configuration Yosys's synth_ecp5 emits for this design: no pipeline
// registers (every REG_*_CLK = "NONE", the blackbox defaults), C tied low,
// SOURCEA/SOURCEB = 0 (operands from the A/B pins, not the shift chain),
// i.e. a purely combinational 18x18 -> 36 multiplier whose operand
// signedness comes from the SIGNEDA/SIGNEDB pins.
//
// Yosys ships MULT18X18D only as a blackbox (ecp5/cells_bb.v), so
// post-synthesis netlist simulation needs this model. It is the only
// non-Yosys-provided cell model in the netlist sim; every LUT4/CCU2C/
// PFUMX/L6MUX21/TRELLIS_FF comes from Yosys's own ecp5/cells_sim.v. To
// keep it from silently mis-modelling a mode it does not implement, it
// stops the simulation if any instance is configured differently. The
// Makefile's `sim-nodsp` target is an independent cross-check with no
// custom model at all (multipliers built from LUTs instead).
module MULT18X18D (
    input  A17, A16, A15, A14, A13, A12, A11, A10, A9, A8, A7, A6, A5, A4, A3, A2, A1, A0,
    input  B17, B16, B15, B14, B13, B12, B11, B10, B9, B8, B7, B6, B5, B4, B3, B2, B1, B0,
    input  C17, C16, C15, C14, C13, C12, C11, C10, C9, C8, C7, C6, C5, C4, C3, C2, C1, C0,
    input  SIGNEDA, SIGNEDB, SOURCEA, SOURCEB,
    output P35, P34, P33, P32, P31, P30, P29, P28, P27, P26, P25, P24, P23, P22, P21, P20, P19, P18, P17, P16, P15, P14, P13, P12, P11, P10, P9, P8, P7, P6, P5, P4, P3, P2, P1, P0
);
    parameter REG_INPUTA_CLK = "NONE";
    parameter REG_INPUTB_CLK = "NONE";
    parameter REG_INPUTC_CLK = "NONE";
    parameter REG_PIPELINE_CLK = "NONE";
    parameter REG_OUTPUT_CLK = "NONE";
    parameter MULT_BYPASS = "DISABLED";

    wire [17:0] a = {A17, A16, A15, A14, A13, A12, A11, A10, A9, A8, A7, A6, A5, A4, A3, A2, A1, A0};
    wire [17:0] b = {B17, B16, B15, B14, B13, B12, B11, B10, B9, B8, B7, B6, B5, B4, B3, B2, B1, B0};
    wire [17:0] c = {C17, C16, C15, C14, C13, C12, C11, C10, C9, C8, C7, C6, C5, C4, C3, C2, C1, C0};
    wire signed [18:0] a_ext = {SIGNEDA & a[17], a};
    wire signed [18:0] b_ext = {SIGNEDB & b[17], b};
    wire signed [37:0] prod  = a_ext * b_ext;

    assign {P35, P34, P33, P32, P31, P30, P29, P28, P27, P26, P25, P24, P23, P22, P21, P20, P19, P18, P17, P16, P15, P14, P13, P12, P11, P10, P9, P8, P7, P6, P5, P4, P3, P2, P1, P0} = prod[35:0];

    initial begin
        if (REG_INPUTA_CLK != "NONE" ||
            REG_INPUTB_CLK != "NONE" ||
            REG_INPUTC_CLK != "NONE" ||
            REG_PIPELINE_CLK != "NONE" ||
            REG_OUTPUT_CLK != "NONE" ||
            MULT_BYPASS != "DISABLED") begin
            $display("MULT18X18D model: unsupported (registered/bypass) configuration in %m");
            $fatal(1);
        end
    end

    // Checked once after time 0: these pins are tied to constants in the
    // netlist, so an always @* on them would never fire.
    initial #1 begin
        if (SOURCEA !== 1'b0 || SOURCEB !== 1'b0 || c !== 18'd0) begin
            $display("MULT18X18D model: SOURCEA/SOURCEB/C must be 0 in %m");
            $fatal(1);
        end
    end
endmodule
