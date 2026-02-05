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
- `results/batch/<relative_path_without_ext>/result.json`

Common batch options:
- `--options` / `--options-file` / `--set key=value`
- `--table/--no-table`
- `--html` / `--docx` / `--pdf`
- `--batch-id` / `--batch-name`
- `--reset`
