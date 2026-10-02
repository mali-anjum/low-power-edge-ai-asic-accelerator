# Low-Power CMOS Accelerator for Edge-AI Signal Processing

A SKY130 RTL-to-GDSII study of low-power MAC architectures for quantized Edge-AI inference.

**Python → INT8/INT4 → SystemVerilog → OpenLane → GDSII**

## Key results

| Architecture | Precision | Area | Power (typ.) | Frequency | Energy/inference | Accuracy* |
|---|---|---:|---:|---:|---:|---:|
| Adder (Experiment 0) | n/a | 0.002578 mm² | see `results/baseline/` | CLOCK_PERIOD 10 ns | n/a | n/a |
| Sequential | INT8 | out of scope (deferred, see below) | — | — | — | — |
| **Parallel 4-MAC (baseline)** | **INT8** | **0.246796 mm²** | **57.0 nW** | **50 MHz** | **0.0114 pJ** | **90.78%** |
| Sequential | INT4 | out of scope (deferred, see below) | — | — | — | — |
| **Parallel 4-MAC (optimized)** | **INT4** | **0.172923 mm²** | **21.2 nW** | **50 MHz** | **0.0042 pJ** | **81.37%** |
| Improvement, INT8→INT4 (4-way parallel only) | — | **-29.9%** | **-62.8%** | 0% (unchanged, controlled) | **-62.8%** | **-9.41 pts** |

\*Accuracy is a **synthetic** quantization-noise metric (paired random FP32 activations/weights, seed 1234, N=2000, NRMSE-based), not a real-dataset task-accuracy number — see [docs/ppa_comparison.md](docs/ppa_comparison.md#accuracy-caveat). Full table with run tags and notes: [`results/comparison.csv`](results/comparison.csv). Figures: [`docs/figures/`](docs/figures/). Technical report: [`docs/report/report.md`](docs/report/report.md).

**Sequential-schedule variants (`int8_sequential`, `int4_sequential`) are explicitly out of scope for this project's timeline**, per [docs/research_methodology.md](docs/research_methodology.md)'s four-point matrix reduced to one axis (precision only, 4-way-parallel schedule held constant) — see [docs/optimization_plan.md](docs/optimization_plan.md). This is a scope decision recorded before the fact, not an incomplete run.

Headline metric for the accelerator study: **energy per inference**. Experiment 0 is the toolchain proof (combinational 8-bit adder through OpenLane, run `RUN_2026.08.30_06.36.00`).

## Project ownership and baseline provenance

The active research implementation is this project's Version 1 accelerator: the Python reference model, quantization path, four-PE signed INT8 RTL, verification, and future controlled variants. Those are the components developed and verified for this study.

The inherited **SiliconNPU** RTL-to-GDS material is MIT-licensed reference/provenance material only. It is excluded from the active Version 1 simulation and lint flow; its files and results must not be presented as original implementation or as measured results for this project. Its attribution, audit notes, and unverified claims are preserved in [docs/baseline_reference.md](docs/baseline_reference.md). The active flow is rooted at `rtl/accelerator_top.sv` and is documented in [docs/architecture_spec.md](docs/architecture_spec.md).

## Research question

How do reduced numerical precision and MAC parallelism affect energy-efficiency, silicon area, timing, latency, and inference accuracy of a small Edge-AI accelerator in SKY130?

## Hardware / flow

- SkyWater SKY130 (`sky130A`, `sky130_fd_sc_hd`)
- OpenLane (local checkout; not vendored in this repository)
- Yosys, OpenROAD, Magic, Netgen, KLayout
- Icarus Verilog / Verilator

## Verification

Python reference → RTL simulation → bit-exact comparison (three levels: math, RTL, physical). See [docs/verification.md](docs/verification.md).

## Physical design

RTL → synthesis → floorplan → placement → CTS → routing → DRC → LVS → GDSII. See [docs/physical_design.md](docs/physical_design.md).

The active Version 1 accelerator config is [designs/accelerator_int8_parallel/config.json](designs/accelerator_int8_parallel/config.json): `CLOCK_PORT` is `clk`, `CLOCK_PERIOD` is 20 ns, `FP_CORE_UTIL` is 35, and `PL_TARGET_DENSITY` is 0.50. The INT8 4-way baseline has been taken through the full RTL-to-GDSII chain with OpenLane run `project_run_02` (Sprint 5): DRC, LVS, XOR, routing, setup, and hold are clean; CTS is real (worst setup slack 3.74 ns, worst hold slack 0.16 ns); 23 pin / 19 net antenna violations and max-fanout warnings are documented, not silently dropped. Curated PPA is in [results/int8_parallel/metrics.csv](results/int8_parallel/metrics.csv), signoff detail in [results/int8_parallel/signoff.md](results/int8_parallel/signoff.md), the final GDS in `results/int8_parallel/accelerator_top_project_run_02.gds`, and floorplan/placement/routing screenshots rendered from that GDS in [screenshots/int8_parallel/](screenshots/int8_parallel/).

## FPGA target (Lattice ECP5)

The same, unmodified RTL is also built for a Lattice ECP5 LFE5U-25F (CABGA256, speed grade 6) with the open-source Yosys + nextpnr-ecp5 + Project Trellis flow (`cd fpga && make fpga sim metrics`). The only FPGA-specific logic is a thin top wrapper that adds a 2-flop reset synchroniser. Both variants are bit-exact against the Python golden model, on the RTL and on Yosys's post-synthesis netlist (5 frozen golden vectors + 1,125 extended vectors per variant).

| Variant | LUT/carry slots (TRELLIS_COMB) | Flip-flops | DSP (MULT18X18D) | BRAM | Fmax (post-route) |
|---|---:|---:|---:|---:|---:|
| INT8 | 3,084 | 583 | 4 | 0 | 66.36 MHz |
| INT4 | 2,910 | 423 | 4 | 0 | 65.48 MHz |

On SKY130, INT8→INT4 cut area by 29.9%. On the FPGA it saves 5.6% of LUT/carry slots and 27.4% of flip-flops, but no DSPs and no Fmax: each 8×8 or 4×4 multiply occupies one whole hard 18×18 DSP either way. Full results, the ASIC-vs-FPGA table, the seed sweep and the reproduction steps are in [fpga/README.md](fpga/README.md).

## Repository layout

```text
algorithm/      Python golden model and test vectors (Phase 1)
rtl/            Active Version 1 accelerator RTL (accelerator_top.sv, processing_element.sv,
                controller.sv, requantize.sv); inherited baseline RTL is reference-only
verification/   Testbenches and reference vectors
designs/        OpenLane configs per design variant (Experiment 0 / this project's own runs)
flow/           SiliconNPU baseline's OpenLane orchestration (Makefile, config.tcl, openlane_config/)
results/        Curated metrics and final GDS artifacts
fpga/           Second target: ECP5 FPGA wrapper, constraints, Makefile flow, results
docs/           This project's architecture, verification, PD, research plan ("My Docs"),
                including baseline_reference.md (single source of truth for the former docs1/)
                and architecture_spec.md (Version 1 accelerator port/FSM/memory-map contract)
openmac/        Baseline's Python analysis/report-parsing library
scripts/        Simulation and OpenLane helpers (this project's + baseline's)
screenshots/    Physical-design screenshots: int8_parallel/ is the Version 1 accelerator
                (Sprint 5, rendered from results/int8_parallel/); the rest are the
                inherited SiliconNPU baseline, not this project's own accelerator
tests/          Unit tests for openmac/
```

Do **not** commit the nested `OpenLane/` tree, virtualenvs, or raw run directories. GitHub is the lab notebook, not a dump of the ASIC toolchain.

## Current status

All eight sprints are complete. The Python golden model, the four-PE signed-INT8 accelerator RTL, bit-exact RTL verification, and the full RTL-to-GDSII flow are done for both the INT8 baseline and the INT4 bit-width-optimized variant (both 4-way parallel, both DRC/LVS/route/setup-hold clean). Sequential-schedule variants are an explicit, pre-registered scope cut, not unfinished work — see [docs/01_status_and_roadmap.md](docs/01_status_and_roadmap.md) and [docs/research_methodology.md](docs/research_methodology.md). The research package (figures, PPA/accuracy tables, technical report) is in [docs/figures/](docs/figures/) and [docs/report/report.md](docs/report/report.md).

**How to follow the work (new contributors):** complete the project as **8 weekly sprints** (~20–25 hours/week). Start at [docs/02_eight_week_sprint_plan.md](docs/02_eight_week_sprint_plan.md) and open only the current week under [docs/sprints/](docs/sprints/). Contribution rules: [CONTRIBUTING.md](CONTRIBUTING.md). Checkpoint list: [docs/01_status_and_roadmap.md](docs/01_status_and_roadmap.md).

## Documentation

| Document | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) | Instructions for AI coding agents: ground-truth hierarchy, current state, hard rules |
| [docs/00_project_overview.md](docs/00_project_overview.md) | Scope, stack, validation levels |
| [docs/01_status_and_roadmap.md](docs/01_status_and_roadmap.md) | Checkpoint and next steps |
| [docs/research_question.md](docs/research_question.md) | Frozen question, hypothesis, variables, scope |
| [docs/02_eight_week_sprint_plan.md](docs/02_eight_week_sprint_plan.md) | 8-week calendar, gates, stack, final package |
| [docs/sprints/](docs/sprints/) | Detailed Week 1–8 guides (tasks, files, acceptance) |
| [docs/architecture.md](docs/architecture.md) | Adder + planned PE array |
| [docs/quantization.md](docs/quantization.md) | Symmetric signed INT8 policy |
| [docs/verification.md](docs/verification.md) | Golden model and hierarchical tests |
| [docs/physical_design.md](docs/physical_design.md) | OpenLane knobs and metrics |
| [docs/experiment0_adder.md](docs/experiment0_adder.md) | Adder RTL-to-GDS evidence |
| [docs/research_methodology.md](docs/research_methodology.md) | Four-point experiment |
| [docs/github_and_lab_notebook.md](docs/github_and_lab_notebook.md) | What to commit |
| [docs/ppa_comparison.md](docs/ppa_comparison.md) | Sprint 7 INT8-vs-INT4 PPA/accuracy comparison, methodology, and caveats |
| [docs/figures/](docs/figures/) | Sprint 8 figure pack (architecture, waveform, layout, PPA/accuracy/trade-off charts) |
| [docs/report/report.md](docs/report/report.md) | Sprint 8 technical report |

## License

MIT. See [LICENSE](LICENSE).
# low-power-edge-ai-asic-accelerator
