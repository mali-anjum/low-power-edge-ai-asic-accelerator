# FPGA (Lattice ECP5 LFE5U-25F) target for the Version 1 accelerator.
#
#   make fpga          synth -> place & route -> timing -> bitstream, INT8 + INT4
#   make sim           golden vectors vs RTL and vs Yosys post-synth netlists
#   make metrics       fpga/results/ (metrics.csv + curated reports) from tool output
#   make seeds         nextpnr seed sweep (Fmax spread) -> fpga/results/seed_sweep.csv
#   make asic-regress  the untouched ASIC testbenches in verification/, on the shared RTL
#   make breakdown     per-module cell counts (synth_ecp5 -noflatten) -> results/<v>/yosys_hier_stat.txt
#   make all           fpga + sim + metrics
#
# Supplemental "nodsp" variants (synth_ecp5 -nodsp: multipliers built from
# LUTs instead of MULT18X18D) are built by `make fpga` too. They are an
# ablation to show what the hard DSP blocks absorb, and their netlists are
# simulated with Yosys's own cell models only -- no custom DSP model.
#
# Reads rtl/ and designs/accelerator_int4_parallel/ read-only; writes only
# under fpga/build/ (gitignored) and fpga/results/.

OSS_CAD   ?= $(HOME)/oss-cad-suite
export PATH := $(OSS_CAD)/bin:$(PATH)

DEVICE    ?= 25k
DEVICE_NAME ?= LFE5U-25F
PACKAGE   ?= CABGA256
SPEED     ?= 6
SEED      ?= 1
SEEDS     ?= 1 2 3 4 5 6 7 8 9 10
PYTHON    ?= python3

REPO      := $(abspath ..)
BUILD     := build
RESULTS   := results
LPF       := constraints/ecp5_25f.lpf
CELLS_DIR := $(shell $(OSS_CAD)/bin/yosys-config --datdir)/ecp5
CELLS_SIM := $(BUILD)/sim/ecp5_cells_sim.v
DSP_SIM   := sim/mult18x18d_comb_sim.v

CORE_RTL  := $(REPO)/rtl/controller.sv $(REPO)/rtl/processing_element.sv \
             $(REPO)/rtl/requantize.sv $(REPO)/rtl/accelerator_top.sv
INT4_WRAP := $(REPO)/designs/accelerator_int4_parallel/accelerator_top_int4.sv
TOP_RTL   := rtl/fpga_top.sv

# Per-variant settings: source list, defines, golden-model bit width,
# extra synth_ecp5 flags, and the extra sim model the netlist needs.
RTL_int8        := $(CORE_RTL) $(TOP_RTL)
RTL_int4        := $(CORE_RTL) $(INT4_WRAP) $(TOP_RTL)
RTL_int8_nodsp  := $(RTL_int8)
RTL_int4_nodsp  := $(RTL_int4)
DEF_int8        :=
DEF_int4        := -DFPGA_INT4
DEF_int8_nodsp  :=
DEF_int4_nodsp  := -DFPGA_INT4
BITS_int8       := 8
BITS_int4       := 4
BITS_int8_nodsp := 8
BITS_int4_nodsp := 4
SYN_int8        :=
SYN_int4        :=
SYN_int8_nodsp  := -nodsp
SYN_int4_nodsp  := -nodsp
XSIM_int8       := $(DSP_SIM)
XSIM_int4       := $(DSP_SIM)
XSIM_int8_nodsp :=
XSIM_int4_nodsp :=

MAIN      := int8 int4
VARIANTS  := $(MAIN) int8_nodsp int4_nodsp
SUITES    := golden extended

.PHONY: all fpga sim metrics seeds vectors lint asic-regress breakdown clean \
        $(addprefix synth-,$(VARIANTS)) $(addprefix pnr-,$(VARIANTS))

all: fpga sim metrics

fpga: $(foreach v,$(VARIANTS),$(BUILD)/$(v)/fpga_top.bit)

vectors: $(foreach b,8 4,$(foreach s,$(SUITES),$(BUILD)/vectors/int$(b)_$(s).txt))

# ---------------------------------------------------------------- flow ---
define VARIANT_RULES
$(BUILD)/$(1)/fpga_top.json $(BUILD)/$(1)/netlist.v &: $(RTL_$(1)) | $(BUILD)/$(1)
	yosys -l $(BUILD)/$(1)/yosys.log -p "\
	  read_verilog -sv $(DEF_$(1)) $(RTL_$(1)); \
	  synth_ecp5 $(SYN_$(1)) -top fpga_top -json $(BUILD)/$(1)/fpga_top.json; \
	  tee -o $(BUILD)/$(1)/yosys_stat.txt stat; \
	  write_verilog -noattr $(BUILD)/$(1)/netlist.v"

# nextpnr runs static timing analysis on the routed design and writes the
# achieved Fmax and utilization to report.json. --timing-allow-fail keeps a
# missed 50 MHz target visible as a number instead of aborting the flow.
$(BUILD)/$(1)/fpga_top.config: $(BUILD)/$(1)/fpga_top.json $(LPF)
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --speed $(SPEED) --seed $(SEED) \
	  --json $$< --lpf $(LPF) --lpf-allow-unconstrained --timing-allow-fail \
	  --textcfg $$@ --report $(BUILD)/$(1)/report.json -l $(BUILD)/$(1)/nextpnr.log

$(BUILD)/$(1)/fpga_top.bit: $(BUILD)/$(1)/fpga_top.config
	ecppack --compress $$< --bit $$@

synth-$(1): $(BUILD)/$(1)/fpga_top.json
pnr-$(1): $(BUILD)/$(1)/fpga_top.config

$(BUILD)/$(1):
	mkdir -p $$@

$(BUILD)/sim/$(1)_netlist.vvp: $(BUILD)/$(1)/netlist.v sim/tb_fpga_top.sv $(CELLS_SIM) $(XSIM_$(1))
	iverilog -g2012 $(DEF_$(1)) -I$(CELLS_DIR) -s tb_fpga_top -o $$@ sim/tb_fpga_top.sv \
	  $(BUILD)/$(1)/netlist.v $(CELLS_SIM) $(XSIM_$(1))
endef

define RTL_SIM_RULE
$(BUILD)/sim/$(1)_rtl.vvp: $(RTL_$(1)) sim/tb_fpga_top.sv | $(BUILD)/sim
	iverilog -g2012 $(DEF_$(1)) -s tb_fpga_top -o $$@ sim/tb_fpga_top.sv $(RTL_$(1))
endef

define VECTOR_RULE
$(BUILD)/vectors/int$(1)_$(2).txt: scripts/make_vectors.py | $(BUILD)/vectors
	$(PYTHON) scripts/make_vectors.py --bits $(1) --suite $(2) --out $$@
endef

$(foreach v,$(VARIANTS),$(eval $(call VARIANT_RULES,$(v))))
$(foreach v,$(MAIN),$(eval $(call RTL_SIM_RULE,$(v))))
$(foreach b,8 4,$(foreach s,$(SUITES),$(eval $(call VECTOR_RULE,$(b),$(s)))))

$(BUILD)/sim $(BUILD)/vectors:
	mkdir -p $@

# Yosys's ECP5 cells_sim.v `includes cells_ff.vh and cells_io.vh both
# directly and via common_sim.vh (seen in OSS CAD Suite 2026-09-27), which
# iverilog rejects as duplicate modules. Simulate a de-duplicated copy
# instead of patching the toolchain install.
$(CELLS_SIM): $(CELLS_DIR)/cells_sim.v | $(BUILD)/sim
	sed -e '/^`include "cells_ff.vh"/d' -e '/^`include "cells_io.vh"/d' $< > $@

# ----------------------------------------------------------- simulation ---
# Runs: RTL and post-synth netlist of int8/int4, plus the -nodsp netlists,
# each against the golden and extended suites. Fails if any run mismatches.
SIM_RUNS := $(foreach v,$(MAIN),$(v):rtl $(v):netlist) int8_nodsp:netlist int4_nodsp:netlist

sim: vectors $(foreach v,$(MAIN),$(BUILD)/sim/$(v)_rtl.vvp) \
     $(foreach v,$(VARIANTS),$(BUILD)/sim/$(v)_netlist.vvp)
	@rm -f $(BUILD)/sim/summary.txt
	@set -e; for run in $(SIM_RUNS); do v=$${run%%:*}; m=$${run##*:}; \
	  bits=$$(echo $$v | cut -c4); \
	  for s in $(SUITES); do \
	    log=$(BUILD)/sim/$${v}_$${m}_$${s}.log; \
	    vvp -n $(BUILD)/sim/$${v}_$${m}.vvp +VECTORS=$(BUILD)/vectors/int$${bits}_$${s}.txt > $$log; \
	    printf "%-11s %-8s %-9s %s  %s\n" $$v $$m $$s \
	      "$$(grep -E '^VECTORS:' $$log)" "$$(grep -E '^RESULT:' $$log || echo 'RESULT: NO RESULT LINE')" \
	      | tee -a $(BUILD)/sim/summary.txt; \
	  done; done
	@! grep -qE "MISMATCH|NO RESULT" $(BUILD)/sim/summary.txt || \
	  (echo "NOT BIT-EXACT -- see $(BUILD)/sim/*.log"; exit 1)
	@mkdir -p $(RESULTS) && cp $(BUILD)/sim/summary.txt $(RESULTS)/sim_summary.txt

# The ASIC-side testbenches, run untouched from a build dir, to show the
# shared RTL still passes its original checks (incl. the internal INT32
# accumulator probes the port-level FPGA testbench cannot see).
asic-regress: | $(BUILD)/sim
	iverilog -g2012 -s tb_accelerator -o $(BUILD)/sim/tb_accelerator.vvp \
	  $(REPO)/verification/tb_accelerator.sv $(CORE_RTL)
	iverilog -g2012 -s tb_accelerator_int4 -o $(BUILD)/sim/tb_accelerator_int4.vvp \
	  $(REPO)/verification/tb_accelerator_int4.sv $(CORE_RTL)
	cd $(BUILD)/sim && vvp -n tb_accelerator.vvp +DUMPFILE=tb_accelerator.vcd | tail -2
	cd $(BUILD)/sim && vvp -n tb_accelerator_int4.vvp +DUMPFILE=tb_accelerator_int4.vcd | tail -2

lint:
	verilator --lint-only -Wall -Wno-DECLFILENAME --top-module fpga_top $(RTL_int8)
	verilator --lint-only -Wall -Wno-DECLFILENAME --top-module fpga_top -DFPGA_INT4 $(RTL_int4)

# ------------------------------------------------------------- results ---
metrics: fpga
	$(PYTHON) scripts/extract_metrics.py --build $(BUILD) --results $(RESULTS) \
	  --variants $(VARIANTS) --device $(DEVICE_NAME) --package $(PACKAGE) \
	  --speed $(SPEED) --seed $(SEED)

seeds: $(foreach v,$(VARIANTS),$(BUILD)/$(v)/fpga_top.json)
	@mkdir -p $(BUILD)/seeds $(RESULTS)
	@set -e; for v in $(VARIANTS); do for s in $(SEEDS); do \
	  echo "nextpnr $$v seed $$s"; \
	  nextpnr-ecp5 -q --$(DEVICE) --package $(PACKAGE) --speed $(SPEED) --seed $$s \
	    --json $(BUILD)/$$v/fpga_top.json --lpf $(LPF) --lpf-allow-unconstrained \
	    --timing-allow-fail --report $(BUILD)/seeds/$${v}_seed$$s.json \
	    -l $(BUILD)/seeds/$${v}_seed$$s.log; \
	done; done
	$(PYTHON) scripts/extract_metrics.py --seed-sweep $(BUILD)/seeds --results $(RESULTS) \
	  --variants $(VARIANTS)

# Per-module cell counts from a separate synth_ecp5 -noflatten run. Used only
# to attribute LUTs to modules; the headline numbers come from the normal
# flattened flow, which can optimize across module boundaries.
breakdown:
	@set -e; for v in $(MAIN); do mkdir -p $(RESULTS)/$$v; \
	  if [ $$v = int4 ]; then d="$(DEF_int4)"; f="$(RTL_int4)"; else d="$(DEF_int8)"; f="$(RTL_int8)"; fi; \
	  yosys -q -p "read_verilog -sv $$d $$f; synth_ecp5 -noflatten -top fpga_top; \
	    tee -q -o $(RESULTS)/$$v/yosys_hier_stat.txt stat"; \
	  echo "wrote $(RESULTS)/$$v/yosys_hier_stat.txt"; done

clean:
	rm -rf $(BUILD)
