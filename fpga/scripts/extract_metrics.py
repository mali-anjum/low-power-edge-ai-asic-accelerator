#!/usr/bin/env python3
"""Collect FPGA metrics from Yosys/nextpnr output into fpga/results/.

Every number written here is parsed from a tool report -- Yosys `stat`
(post-synthesis cell counts) and nextpnr's --report JSON / log (post-route
utilization, Fmax, critical-path breakdown). Nothing is estimated; a metric
the reports do not contain is written as an empty field.

  --build/--results/--variants ...   metrics.csv + <variant>/ curated reports
  --seed-sweep DIR                   seed_sweep.csv from DIR/<variant>_seed<N>.json
"""

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess

CLK_PREFIX = "posedge"

VARIANT_INFO = {
    "int8": ("INT8", "accelerator_top", "MULT18X18D"),
    "int4": ("INT4", "accelerator_top_int4", "MULT18X18D"),
    "int8_nodsp": ("INT8", "accelerator_top", "LUT (synth_ecp5 -nodsp)"),
    "int4_nodsp": ("INT4", "accelerator_top_int4", "LUT (synth_ecp5 -nodsp)"),
}

YOSYS_CELLS = ["LUT4", "CCU2C", "PFUMX", "L6MUX21", "TRELLIS_FF", "MULT18X18D",
               "ALU54B", "DP16KD", "TRELLIS_DPR16X4"]


def yosys_cells(stat_path):
    counts = {c: 0 for c in YOSYS_CELLS}
    with open(stat_path) as f:
        for line in f:
            m = re.match(r"\s+(\d+)\s+(\S+)\s*$", line)
            if m and m.group(2) in counts:
                counts[m.group(2)] = int(m.group(1))
    return counts


def clock_fmax(report):
    # One clock domain (clk, promoted to a global net by nextpnr).
    (name, fm), = report["fmax"].items()
    return fm["achieved"], fm["constraint"]


def critical_path(report, src, dst):
    for cp in report["critical_paths"]:
        if cp["from"].startswith(src) and cp["to"].startswith(dst):
            return cp["path"]
    return None


def path_breakdown(path):
    by_type = {}
    dsp = 0.0
    for seg in path:
        by_type[seg["type"]] = by_type.get(seg["type"], 0.0) + seg["delay"]
        if seg["type"] == "logic" and "MULT18X18D" in seg["from"]["cell"] \
                and not re.search(r"MULT18X18D_P\d+_", seg["from"]["cell"]):
            dsp += seg["delay"]
    total = sum(by_type.values())
    return total, by_type.get("logic", 0.0), by_type.get("routing", 0.0), dsp


def max_delays(log_path):
    """Final (post-route) 'Max delay' lines for the unclocked I/O paths."""
    text = open(log_path).read()
    final = text[text.rfind("Critical path report for clock"):]
    out = {}
    for m in re.finditer(r"Max delay (\S+)\s+(?:\$\S+\s+)?-> (\S+)\s*(?:\$\S+)?\s*: ([\d.]+) ns", final):
        out[(m.group(1), m.group(2))] = float(m.group(3))
    return out


def final_log_summary(log_path):
    """Utilisation block + post-route timing section of the nextpnr log."""
    lines = open(log_path).read().splitlines()
    util_start = max(i for i, l in enumerate(lines) if "Device utilisation:" in l)
    util = []
    for l in lines[util_start:]:
        if l.strip() == "Info:" or (util and not l.startswith("Info: \t")):
            break
        util.append(l)
    # Critical-path reports are only printed after routing, so the first one
    # starts the post-route timing section.
    # The unclocked I/O path listings in between are dropped (their max delays
    # are kept in metrics.csv); the clk reg-to-reg path is kept in full.
    crit_start = next(i for i, l in enumerate(lines) if "Critical path report for clock" in l)
    io_start = next(i for i, l in enumerate(lines) if "Critical path report for cross-domain" in l)
    fmax_start = max(i for i, l in enumerate(lines) if "Max frequency for clock" in l)
    timing = lines[crit_start:io_start] + ["Info: [I/O path listings omitted]", ""] + \
        [l for l in lines[fmax_start:] if not l.startswith("Warning:")]
    return "\n".join(util) + "\n\n" + "\n".join(timing) + "\n"


def tool_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        # nextpnr prints its version on stderr, the others on stdout.
        return (r.stdout.strip() or r.stderr.strip()).splitlines()[0]
    except (OSError, IndexError):
        return ""


def collect(args):
    os.makedirs(args.results, exist_ok=True)
    rows = []
    for v in args.variants:
        vdir = os.path.join(args.build, v)
        report = json.load(open(os.path.join(vdir, "report.json")))
        cells = yosys_cells(os.path.join(vdir, "yosys_stat.txt"))
        util = report["utilization"]
        fmax, target = clock_fmax(report)
        reg_path = critical_path(report, CLK_PREFIX, CLK_PREFIX)
        total, logic, routing, dsp = path_breakdown(reg_path)
        io = max_delays(os.path.join(vdir, "nextpnr.log"))
        precision, top, mult = VARIANT_INFO[v]

        rows.append({
            "variant": v,
            "precision": precision,
            "accel_top_module": top,
            "multiplier_impl": mult,
            "device": args.device,
            "package": args.package,
            "speed_grade": args.speed,
            "pnr_seed": args.seed,
            "target_clock_mhz": target,
            "fmax_mhz": round(fmax, 2),
            "timing_met": fmax >= target,
            "reg2reg_critical_path_ns": round(total, 2),
            "reg2reg_logic_ns": round(logic, 2),
            "reg2reg_routing_ns": round(routing, 2),
            "reg2reg_dsp_ns": round(dsp, 2),
            "max_delay_in_to_out_ns": io.get(("<async>", "<async>"), ""),
            "max_delay_in_to_reg_ns": io.get(("<async>", "posedge"), ""),
            "max_delay_reg_to_out_ns": io.get(("posedge", "<async>"), ""),
            **{f"yosys_{c.lower()}": n for c, n in cells.items()},
            "pnr_trellis_comb_used": util["TRELLIS_COMB"]["used"],
            "pnr_trellis_comb_avail": util["TRELLIS_COMB"]["available"],
            "pnr_trellis_ff_used": util["TRELLIS_FF"]["used"],
            "pnr_trellis_ff_avail": util["TRELLIS_FF"]["available"],
            "pnr_mult18x18d_used": util["MULT18X18D"]["used"],
            "pnr_mult18x18d_avail": util["MULT18X18D"]["available"],
            "pnr_dp16kd_used": util["DP16KD"]["used"],
            "pnr_dp16kd_avail": util["DP16KD"]["available"],
            "pnr_trellis_ramw_used": util["TRELLIS_RAMW"]["used"],
            "pnr_trellis_io_used": util["TRELLIS_IO"]["used"],
            "pnr_trellis_io_avail": util["TRELLIS_IO"]["available"],
        })

        out = os.path.join(args.results, v)
        os.makedirs(out, exist_ok=True)
        shutil.copy(os.path.join(vdir, "yosys_stat.txt"), os.path.join(out, "yosys_stat.txt"))
        with open(os.path.join(out, "nextpnr_summary.txt"), "w") as f:
            f.write(final_log_summary(os.path.join(vdir, "nextpnr.log")))

    with open(os.path.join(args.results, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(args.results, "toolchain.txt"), "w") as f:
        for cmd in (["yosys", "-V"], ["nextpnr-ecp5", "--version"], ["iverilog", "-V"],
                    ["verilator", "--version"]):
            f.write(tool_version(cmd) + "\n")

    for r in rows:
        print(f"{r['variant']:<11} Fmax {r['fmax_mhz']:>6} MHz  "
              f"COMB {r['pnr_trellis_comb_used']:>5}  FF {r['pnr_trellis_ff_used']:>4}  "
              f"DSP {r['pnr_mult18x18d_used']}  BRAM {r['pnr_dp16kd_used']}")


def seed_sweep(args):
    rows = []
    for v in args.variants:
        seeds = sorted(int(m.group(1)) for fn in os.listdir(args.seed_sweep)
                       if (m := re.fullmatch(rf"{v}_seed(\d+)\.json", fn)))
        for s in seeds:
            report = json.load(open(os.path.join(args.seed_sweep, f"{v}_seed{s}.json")))
            fmax, target = clock_fmax(report)
            rows.append({"variant": v, "seed": s, "fmax_mhz": round(fmax, 2),
                         "target_clock_mhz": target,
                         "trellis_comb_used": report["utilization"]["TRELLIS_COMB"]["used"]})
    os.makedirs(args.results, exist_ok=True)
    with open(os.path.join(args.results, "seed_sweep.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for v in args.variants:
        f = [r["fmax_mhz"] for r in rows if r["variant"] == v]
        print(f"{v}: n={len(f)} Fmax min {min(f)} / median {round(statistics.median(f), 2)} / max {max(f)} MHz")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="build")
    ap.add_argument("--results", default="results")
    ap.add_argument("--variants", nargs="+", default=["int8", "int4"])
    ap.add_argument("--device", default="")
    ap.add_argument("--package", default="")
    ap.add_argument("--speed", default="")
    ap.add_argument("--seed", default="")
    ap.add_argument("--seed-sweep")
    args = ap.parse_args()
    seed_sweep(args) if args.seed_sweep else collect(args)


if __name__ == "__main__":
    main()
