# Preprocess Command

<cite>
**Referenced Files in This Document**   
- [preprocess.py](file://src/cli/commands/preprocess.py)
- [preprocess.py](file://src/pipelines/graphs/nodes/preprocess.py)
- [documents.py](file://src/schemas/internal/documents.py)
- [shared.py](file://src/cli/commands/shared.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Preprocess Subcommands](#preprocess-subcommands)
3. [Input Parameters](#input-parameters)
4. [Output Format](#output-format)
5. [Examples](#examples)

## Introduction

The preprocess command is a debugging utility for inspecting the output of the preprocessing node. It runs the same preprocessing pipeline used by the ROB2 workflow and returns the normalized `DocStructure` payload that is passed downstream. This command is useful for validating parsing quality, verifying section spans, and diagnosing issues before retrieval and validation stages.

**Section sources**
- [preprocess.py](file://src/cli/commands/preprocess.py#L1-L170)
- [preprocess.py](file://src/pipelines/graphs/nodes/preprocess.py#L24-L70)

## Preprocess Subcommands

### show

The `show` subcommand runs preprocessing on a PDF and prints either a summary view or the JSON payload.

**Key options**
- `--body/--no-body`: Include or omit `body` text.
- `--sections/--no-sections`: Include or omit the `sections` list.
- `--section-limit`: Limit the number of sections returned.
- `--max-body-chars`: Truncate body text to a maximum number of characters.
- `--max-section-chars`: Truncate each section text to a maximum number of characters.
- `--output`: Write JSON output to a file.
- `--json`: Emit JSON to stdout.

**Section sources**
- [preprocess.py](file://src/cli/commands/preprocess.py#L91-L170)

## Input Parameters

The command accepts a single required argument:
- `PDF_PATH`: Path to the input PDF file.

The PDF is parsed into a `DocStructure` using the preprocessing pipeline described in the `preprocess_node` implementation.

**Section sources**
- [preprocess.py](file://src/cli/commands/preprocess.py#L100-L146)
- [preprocess.py](file://src/pipelines/graphs/nodes/preprocess.py#L24-L70)

## Output Format

JSON output follows this structure:

```json
{
  "doc_structure": {
    "body": "...",
    "sections": [...],
    "docling_config": {...}
  },
  "stats": {
    "body_chars": 12345,
    "section_count": 98,
    "included": {"body": true, "sections": true},
    "truncated": {"body": false, "sections": false, "section_text": false}
  }
}
```

The `doc_structure` object matches the `DocStructure` schema and may include additional metadata depending on preprocessing settings.

**Section sources**
- [preprocess.py](file://src/cli/commands/preprocess.py#L31-L124)
- [documents.py](file://src/schemas/internal/documents.py#L21-L43)

## Examples

```bash
# Print a summary (default)
rob2 preprocess show paper.pdf

# Emit full JSON
rob2 preprocess show paper.pdf --json

# Truncate output for quick inspection
rob2 preprocess show paper.pdf --max-body-chars 5000 --max-section-chars 400

# Write JSON to a file
rob2 preprocess show paper.pdf --output preprocess.json
```

