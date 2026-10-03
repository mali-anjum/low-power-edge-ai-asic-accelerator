# LinkedIn banner from the final GDSII

Renders `results/int8_parallel/accelerator_top_project_run_02.gds` (INT8 4-way
parallel, OpenLane `project_run_02`) and composes 1584x396 banners into `banner/`.
The caption's 0.247 mm² is `die_area_mm2` from `results/int8_parallel/metrics.csv`.

```bash
pip install gdstk pillow numpy
python3 scripts/linkedin_banner/render_gds.py      # -> banner/chip_render_full.png
INTER_DIR=/path/to/Inter/extras/ttf python3 scripts/linkedin_banner/compose_banner.py
```

Run from the repo root. Without `INTER_DIR` the text falls back to DejaVu Sans.
Layer colours: met1 cyan, met2 magenta, met3 gold, met4 green, met5 white, li1 faint blue.
