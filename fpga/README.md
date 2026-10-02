# FPGA target: Lattice ECP5 LFE5U-25F

This folder builds the **same, unmodified RTL** that went through SKY130 OpenLane
(`rtl/accelerator_top.sv` for INT8, `designs/accelerator_int4_parallel/accelerator_top_int4.sv`
for INT4) for a Lattice ECP5 FPGA with an all-open-source flow. It checks that the FPGA
netlist is still bit-exact against the Python golden model and records measured
FPGA resource and timing numbers next to the ASIC ones.

Nothing in `rtl/`, `flow/`, `verification/`, `designs/` or `results/` is modified.

| | |
|---|---|
| Device | LFE5U-25F, CABGA256 package, speed grade 6 (the slowest grade) |
| Flow | Yosys `synth_ecp5` → nextpnr-ecp5 (place, route, STA) → Project Trellis `ecppack` |
| Clock constraint | 50 MHz (`constraints/ecp5_25f.lpf`), the same 20 ns period as the SKY130 runs |
| Place-and-route seed | 1 for the headline numbers; seeds 1–10 in the sweep below |
| Toolchain | OSS CAD Suite 2026-09-27; exact versions in [`results/toolchain.txt`](results/toolchain.txt) |

## Contents

```text
fpga/
  rtl/fpga_top.sv               top wrapper: 2-flop reset synchroniser + pass-through (INT4 via -DFPGA_INT4)
  constraints/ecp5_25f.lpf      50 MHz clock constraint; no pin LOCATEs (see "Limitations")
  Makefile                      make fpga | sim | metrics | seeds | breakdown | asic-regress | lint
  sim/tb_fpga_top.sv            port-level golden-vector testbench (runs on RTL and on the netlist)
  sim/mult18x18d_comb_sim.v     simulation model for the ECP5 DSP block (netlist sim only)
  scripts/make_vectors.py       golden + extended vectors, expected outputs from algorithm/
  scripts/extract_metrics.py    tool reports -> results/metrics.csv
  results/                      curated, committed: metrics.csv, seed_sweep.csv, sim_summary.txt,
                                per-variant yosys_stat.txt + nextpnr_summary.txt, toolchain.txt
  build/                        everything generated (gitignored): netlists, logs, bitstreams
```

## How to reproduce

**1. Install the toolchain (Linux x86-64, no sudo needed).** OSS CAD Suite bundles Yosys,
nextpnr-ecp5, Project Trellis, Icarus Verilog and Verilator. It takes about 2.5 GB once
unpacked; streaming it into `tar` avoids storing the 710 MB archive too.

```bash
cd ~
curl -L https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-09-27/oss-cad-suite-linux-x64-20260927.tgz | tar xz
export PATH=$HOME/oss-cad-suite/bin:$PATH      # the Makefile adds this itself
yosys -V && nextpnr-ecp5 --version && ecppack --help | head -1 && iverilog -V | head -1
```

If the suite lives elsewhere, pass `OSS_CAD=/path/to/oss-cad-suite` to `make`.
Python 3 with NumPy is needed for the golden model, as in `algorithm/`.

**2. Build and verify.**

```bash
cd fpga
make fpga           # INT8 + INT4 (+ the -nodsp ablation): synth -> P&R -> STA -> .bit (~2 min)
make sim            # golden vectors vs RTL and post-synth netlists; fails unless bit-exact
make metrics        # results/metrics.csv and per-variant reports, parsed from tool output
make seeds          # optional: Fmax over nextpnr seeds 1-10 -> results/seed_sweep.csv
make asic-regress   # optional: the untouched verification/tb_accelerator*.sv on the same RTL
make lint           # optional: Verilator -Wall on wrapper + RTL, both variants
```

Exact synthesis command, per variant: `read_verilog -sv [-DFPGA_INT4] <rtl files>; synth_ecp5 [-nodsp] -top fpga_top`.
Exact P&R command: `nextpnr-ecp5 --25k --package CABGA256 --speed 6 --seed 1 --lpf constraints/ecp5_25f.lpf --lpf-allow-unconstrained --timing-allow-fail`.

## Changes made for FPGA synthesis

**No RTL change was needed.** Yosys 0.69 parses and synthesizes all four `rtl/*.sv` files
and the INT4 wrapper as-is, including `int` parameters, `typedef enum`, size casts
(`PE_IDX_W'(p)`) and the `.*` port connection in `accelerator_top_int4`. (The
`chparam` bug documented in `results/int4_parallel/signoff.md` never comes up, because
INT4 is built through the same `accelerator_top_int4` wrapper OpenLane used.)

Everything FPGA-specific lives in `fpga/`:

| # | Change | Where | Why |
|---|---|---|---|
| 1 | 2-flop reset synchroniser (async assert, sync release) | `rtl/fpga_top.sv` | On a board, `rst_n` comes from a button or host pin that is asynchronous to `clk`. Releasing an async reset near a clock edge can leave some flops in reset and others out. It adds 2 FFs and is **not** in the datapath. |
| 2 | Variant select with `` `ifdef FPGA_INT4 `` | `rtl/fpga_top.sv` | One wrapper instantiates either `accelerator_top` (INT8) or `accelerator_top_int4` (INT4) without editing either. |
| 3 | `.lpf` with only a clock constraint | `constraints/ecp5_25f.lpf` | Sets the timing target; pins are left to nextpnr (`--lpf-allow-unconstrained`). |
| 4 | `SYNCASYNCNET` lint waiver on `rst_sync` | `rtl/fpga_top.sv` | A reset synchroniser is by design flopped on `clk` and then used as an async reset. |
| 5 | Behavioral `MULT18X18D` model | `sim/mult18x18d_comb_sim.v` (simulation only) | Yosys ships the ECP5 DSP only as a blackbox. The model covers only the configuration Yosys emits here: combinational, no pipeline registers, SIGNEDA/B from pins. It `$fatal`s on any other configuration. The `-nodsp` netlists cross-check it without any custom model. |
| 6 | De-duplicated copy of Yosys's `ecp5/cells_sim.v` | `Makefile` (generated in `build/sim/`) | In OSS CAD Suite 2026-09-27, `cells_sim.v` includes `cells_ff.vh`/`cells_io.vh` twice, and iverilog rejects the duplicates. The toolchain install is not patched. |

## Verification: bit-exact against the Python golden model

`sim/tb_fpga_top.sv` drives only the ports of `fpga_top`. That is why the **same
testbench** runs on the RTL and on Yosys's flattened post-synthesis ECP5 netlist
(`write_verilog` after `synth_ecp5`, simulated with Yosys's ECP5 primitive models). It
loads weights, activations and biases, pulses `start`, waits for `done`, and compares
all four `y_out` lanes against the expected outputs. It also checks that `busy`/`done`
clear afterwards.

Expected outputs come only from `algorithm/reference_model.forward()`:

- **golden**: the 5 frozen rows of `verification/reference/vectors.csv` (INT8, shift 8)
  or `vectors_int4.csv` (INT4, shift 4), re-checked against `forward()` before use.
- **extended**: 1,000 seeded random vectors from `algorithm/generate_vectors.generate()`,
  25 directed corners (all-INT_MIN operands, saturation, ReLU-to-zero, bias-only, each
  at shifts 0/1/nominal/15/31), and 100 random vectors with a random shift 0–31. Across
  the 4,500 output lanes this reaches every possible output code: 0..127 for INT8 and
  0..7 for INT4. Outputs are never negative after ReLU.

Result ([`results/sim_summary.txt`](results/sim_summary.txt)):

| Variant | Model | Golden (vectors pass/total) | Extended (vectors pass/total) | Result |
|---|---|---:|---:|---|
| INT8 | RTL | 5 / 5 | 1,125 / 1,125 | bit-exact |
| INT8 | post-synth netlist | 5 / 5 | 1,125 / 1,125 | bit-exact |
| INT4 | RTL | 5 / 5 | 1,125 / 1,125 | bit-exact |
| INT4 | post-synth netlist | 5 / 5 | 1,125 / 1,125 | bit-exact |
| INT8 `-nodsp` | post-synth netlist | 5 / 5 | 1,125 / 1,125 | bit-exact |
| INT4 `-nodsp` | post-synth netlist | 5 / 5 | 1,125 / 1,125 | bit-exact |

Each vector checks 4 output lanes, so the 12 runs cover 6,780 vectors and 27,120 lane
comparisons, with 0 failures. To show the testbench can fail, one expected
output in the INT8 golden file was changed by one LSB. Both the RTL and the netlist sims then
reported `vector 2 neuron 3: FAIL y=31 expected 32` and `RESULT: MISMATCH`.
`make asic-regress` also still reports `ALL TESTS PASSED` for the original
`verification/tb_accelerator.sv` and `tb_accelerator_int4.sv`, which additionally
probe the internal INT32 accumulators.

## Results (measured, seed 1)

All numbers are copied from [`results/metrics.csv`](results/metrics.csv), which
`scripts/extract_metrics.py` parses from the Yosys `stat` output and nextpnr's
post-route report. Percentages are computed from those numbers.

| Metric | INT8 | INT4 | INT8→INT4 |
|---|---:|---:|---:|
| **LUT/carry slots, TRELLIS_COMB** (nextpnr, of 24,288) | **3,084** (12.7%) | **2,910** (12.0%) | **−5.6%** |
|   LUT4 cells (Yosys) | 2,640 | 2,466 | −6.6% |
|   CCU2C carry cells (Yosys) | 195 | 195 | 0% |
|   PFUMX / L6MUX21 wide-mux cells (Yosys) | 940 / 560 | 887 / 538 | |
| **Flip-flops, TRELLIS_FF** (of 24,288) | **583** | **423** | **−27.4%** |
| **DSP blocks, MULT18X18D** (of 28) | **4** | **4** | **0%** |
| **Block RAM, DP16KD** (of 56) | **0** | **0** | — |
| Distributed RAM (TRELLIS_RAMW) | 0 | 0 | — |
| I/O pins (of 197) | 103 | 79 | |
| **Fmax, `clk`** (post-route; target 50 MHz) | **66.36 MHz** (met) | **65.48 MHz** (met) | −1.3% at this seed; no difference over 10 seeds (see sweep) |
| Reg-to-reg critical path | 15.07 ns | 15.27 ns | |
|   of which MULT18X18D delay | 3.93 ns | 3.93 ns | |
|   total logic / routing delay | 6.81 / 7.74 ns | 6.81 / 7.94 ns | |
| Unregistered input→output path (`shift_in`→`y_out`) | 22.60 ns | 24.99 ns | |
| Power / energy per inference | not measured | not measured | |

The flip-flop counts match the architecture exactly. INT8: 256 weight + 64 activation +
128 bias + 128 accumulator + 5 FSM + 2 reset-sync = 583. INT4: 128 + 32 + 128 + 128 + 5 + 2 = 423.

**Why 0 BRAM:** the weight, activation and bias arrays are reset asynchronously in the
RTL (`for ... mem[i] <= '0` under `!rst_n`). A RAM block can't clear all its words in
one cycle, so Yosys turns them into plain registers ("Replacing memory ... with list of
registers" in the synthesis log). With only 448 (INT8) or 288 (INT4) bits of storage,
that's the right call anyway; a DP16KD holds 18 Kbit. Moving them into RAM would mean
changing the RTL, which is out of scope here.

### Where the LUTs go

From `make breakdown` ([`results/int8/yosys_hier_stat.txt`](results/int8/yosys_hier_stat.txt),
[`results/int4/yosys_hier_stat.txt`](results/int4/yosys_hier_stat.txt)). This is a
separate `synth_ecp5 -noflatten` run that keeps module boundaries so LUTs can be
attributed to modules. Its totals are slightly higher than the flattened headline flow,
which can optimize across modules.

| Module (instances) | INT8 LUT4 | INT4 LUT4 |
|---|---:|---:|
| `requantize` (×4): ReLU, round, 32-bit variable shift, clip | 4 × 605 = **2,420** (81.3%) | 4 × 567 = **2,268** (85.6%) |
| `processing_element` (×4): weight column, operand mux, accumulator | 4 × 112 = 448 | 4 × 78 = 312 |
| `accelerator_top`: activation/bias registers and muxes | 89 | 53 |
| `controller` | 17 | 17 |
| `fpga_top`: reset synchroniser | 1 | 1 |
| **Total** | **2,975** | **2,651** |

### Ablation: multipliers in LUTs instead of DSPs (`synth_ecp5 -nodsp`)

Supplemental, to explain the DSP result above. Same RTL, same seed, same constraint, also bit-exact:

| Metric | INT8 `-nodsp` | INT4 `-nodsp` | INT8→INT4 |
|---|---:|---:|---:|
| TRELLIS_COMB | 5,035 | 3,063 | −39.2% |
| LUT4 (Yosys) | 4,591 | 2,619 | −43.0% |
| TRELLIS_FF | 583 | 423 | −27.4% |
| MULT18X18D | 0 | 0 | |
| Fmax (target 50 MHz), seed 1 | 60.63 MHz | 79.00 MHz | +30.3% |
| Fmax median over seeds 1–10 | 62.31 MHz | 77.08 MHz | +23.7% |

The four DSPs absorb 1,951 TRELLIS_COMB slots for INT8 (5,035 − 3,084), but only 153 for
INT4 (3,063 − 2,910). An 8×8 multiplier is expensive in LUTs, while a 4×4 one is almost
free, yet each still takes a whole 18×18 DSP block.

### Place-and-route seed sweep

nextpnr's placer is randomized, so one seed is one sample. `make seeds` re-runs place
and route with seeds 1–10 on the same synthesized netlist
([`results/seed_sweep.csv`](results/seed_sweep.csv)). Resource counts are identical for
every seed; only Fmax moves.

| Variant | Fmax min | Fmax median | Fmax max | All 10 meet 50 MHz |
|---|---:|---:|---:|---|
| INT8 | 65.46 MHz | 66.73 MHz | 69.59 MHz | yes |
| INT4 | 64.77 MHz | 66.87 MHz | 71.31 MHz | yes |
| INT8 `-nodsp` | 60.23 MHz | 62.31 MHz | 64.37 MHz | yes |
| INT4 `-nodsp` | 71.71 MHz | 77.08 MHz | 79.69 MHz | yes |

**INT8 and INT4 have the same Fmax within place-and-route noise.** Their ranges overlap
almost completely, and the medians differ by 0.14 MHz. The −1.3% at seed 1 is noise, not
an effect. The `-nodsp` difference is real: the two ranges don't overlap
(60.23–64.37 vs 71.71–79.69 MHz).

## ASIC (SKY130) vs FPGA (ECP5)

ASIC numbers are copied from [`../results/comparison.csv`](../results/comparison.csv),
[`../results/int8_parallel/metrics.csv`](../results/int8_parallel/metrics.csv) and
[`../results/int4_parallel/metrics.csv`](../results/int4_parallel/metrics.csv)
(OpenLane `project_run_02` / `project_run_01`). FPGA numbers are from
[`results/metrics.csv`](results/metrics.csv) (seed 1). A µm² and a LUT are different
units, so compare the **INT8→INT4 change** within each technology, not the absolute
values across technologies.

| | SKY130 INT8 | SKY130 INT4 | ASIC INT8→INT4 | ECP5 INT8 | ECP5 INT4 | FPGA INT8→INT4 |
|---|---:|---:|---:|---:|---:|---:|
| Area / resources | 0.246796 mm² die | 0.172923 mm² die | **−29.9%** | 3,084 COMB + 583 FF + 4 DSP | 2,910 COMB + 423 FF + 4 DSP | **−5.6% COMB, −27.4% FF, 0% DSP** |
| Synthesized cells | 7,807 std cells | 5,553 std cells | −28.9% | 2,640 LUT4 | 2,466 LUT4 | −6.6% |
| Clock target | 50 MHz (20 ns), met | 50 MHz, met | — | 50 MHz, met | 50 MHz, met | — |
| Timing headroom | critical path 7.98 ns* | 7.47 ns* | −6.4% | Fmax 66.36 MHz (seed 1), median 66.73 over 10 seeds | Fmax 65.48 MHz (seed 1), median 66.87 | no difference within seed noise |
| Power (typical) | 57.0 nW** | 21.2 nW** | −62.8% | not measured | not measured | — |
| Latency | 10 cycles/inference | 10 | 0 | same RTL, same 10-cycle schedule | same | 0 |
| Output function | bit-exact with golden model | bit-exact | — | bit-exact (RTL + netlist) | bit-exact | — |

\* OpenLane's `critical_path_ns`, which `results/int4_parallel/signoff.md` calls
"informational only". The SKY130 runs were not swept to find a true maximum clock, so
there is **no measured ASIC Fmax** to set against the FPGA's, and 7.98 ns is
deliberately not converted into a frequency.
\** OpenLane typical-corner power as recorded in `results/comparison.csv`; see
[`docs/ppa_comparison.md`](../docs/ppa_comparison.md) for how it was obtained and its caveats.

**What the comparison shows.** On SKY130, INT8→INT4 shrinks everything the bit width
touches, the multipliers most of all, because they are built from standard cells. That
gives −29.9% area. On the ECP5, the multipliers were already in hard DSP blocks, and a
4×4 multiply uses a whole 18×18 block just as an 8×8 does. So INT4 frees no DSPs, and
the DSP's fixed 3.93 ns stays on the critical path. Fmax is flat: over 10 seeds the medians are 66.73 vs 66.87 MHz. What's left for
INT4 to shrink in the fabric is the operand storage and multiplexing: FFs fall by
27.4%, but LUTs only by 5.6%. Measured by module, 81–86% of the LUT4s sit in the four
requantizers, whose 32-bit ReLU/round/shift/clip datapath is the same width in both
variants (only the final clip narrows). The `-nodsp` ablation confirms it. Once
the multipliers are moved into LUTs, INT8→INT4 saves 39.2% of LUTs and raises the median
Fmax by 23.7% (62.31 → 77.08 MHz), the same kind of saving the ASIC shows.

## Limitations (read before quoting a number)

- **Not run on a board.** The raw parallel host interface uses 103 (INT8) or 79
  (INT4) pins and has no board pin assignment. The bitstreams (`build/*/fpga_top.bit`)
  show the design fits and meets timing on the device. They aren't board images. Running
  on hardware needs a serial front end (e.g. UART) that owns the host interface.
- **Fmax covers only register-to-register paths on `clk`.** The pins have no
  input/output delay constraints, so nextpnr only reports the I/O paths (e.g. the
  combinational `shift_in`→`y_out` path through the requantizer, 22.60 / 24.99 ns). It
  doesn't check them against a budget. On a board they would be registered or
  constrained.
- **The netlist simulation is zero-delay.** It shows the synthesized logic is
  functionally identical to the RTL. It is not a post-route timing simulation, which
  wasn't run. Timing correctness rests on nextpnr's STA.
- **The DSP simulation model is my own** (`sim/mult18x18d_comb_sim.v`), because Yosys
  provides none. Its scope is narrow and self-checking, and the `-nodsp` netlists pass
  the same vectors using only Yosys-provided models.
- **Fmax depends on the place-and-route seed** (see the seed sweep) and on the speed
  grade. Grade 6 is the slowest ECP5 grade; −7 and −8 parts are faster.
- **No FPGA power or energy number.** The open-source ECP5 flow has no power analysis,
  and Lattice's power calculator is part of the proprietary Diamond/Radiant tools. It
  isn't reported rather than guessed.
- The toolchain is a nightly build (2026-09-27). Different Yosys/nextpnr versions can
  shift LUT counts and Fmax slightly; the versions used are in `results/toolchain.txt`.
