**CLI Usage (Quick)**

**Single File**
```bash
uv run rob2 run /path/to.pdf --output-dir results --json
```

**Batch Mode**
```bash
uv run rob2 batch run /path/to/pdf_dir --output-dir results/batch --json
```

Batch mode behavior:
- Recursively discovers `*.pdf` (case-insensitive), sorted by relative path.
- Expands outputs by relative path.
- Auto-resumes from `batch_checkpoint.json`.
- Strict checkpoint consistency; use `--reset` when inputs/options changed.
- Continues on per-file failures and reports them in summary.

Batch outputs:
- `results/batch/batch_checkpoint.json`
- `results/batch/batch_summary.json`
- `results/batch/batch_summary.csv`
- `results/batch/batch_traffic_light.png`
- `results/batch/batch_summary.xlsx`
- `results/batch/<relative_path_without_ext>/result.json`

Common batch options:
- `--options` / `--options-file` / `--set key=value`
- `--table/--no-table`
- `--html` / `--docx` / `--pdf`
- `--batch-id` / `--batch-name`
- `--reset`
- `--plot/--no-plot`（默认自动生成红绿灯图）
- `--plot-output /path/to/custom.png`
- `--excel/--no-excel`（默认自动生成 Excel 汇总）
- `--excel-output /path/to/custom.xlsx`

**Batch Plot (From Existing Summary)**
```bash
uv run rob2 batch plot results/batch
uv run rob2 batch plot results/batch/batch_summary.json --output results/batch/custom_plot.png
```

**Batch Excel (From Existing Summary)**
```bash
uv run rob2 batch excel results/batch
uv run rob2 batch excel results/batch/batch_summary.json --output results/batch/custom_summary.xlsx
```
