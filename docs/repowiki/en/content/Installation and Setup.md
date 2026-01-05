# Installation and Setup

<cite>
**Referenced Files in This Document**   
- [pyproject.toml](file://pyproject.toml)
- [.env.example](file://.env.example)
- [src/core/config.py](file://src/core/config.py)
- [src/retrieval/engines/splade.py](file://src/retrieval/engines/splade.py)
- [src/retrieval/engines/faiss_ip.py](file://src/retrieval/engines/faiss_ip.py)
- [src/cli/commands/retrieval.py](file://src/cli/commands/retrieval.py)
- [scripts/check_splade_retrieval.py](file://scripts/check_splade_retrieval.py)
</cite>

## Table of Contents
1. [Dependency Requirements](#dependency-requirements)
2. [Installation with uv](#installation-with-uv)
3. [Configuration Hierarchy](#configuration-hierarchy)
4. [LLM Provider Setup](#llm-provider-setup)
5. [Retrieval Model Configuration](#retrieval-model-configuration)
6. [Optional Components](#optional-components)
7. [Environment Variable Examples](#environment-variable-examples)
8. [Verification Steps](#verification-steps)
9. [Common Installation Issues](#common-installation-issues)

## Dependency Requirements

The eAgent system requires Python 3.13 or higher and depends on several key libraries for its functionality. The core dependencies include:

- **LangGraph**: For orchestrating the multi-agent workflow and state management
- **Pydantic**: For data validation and settings management via `pydantic-settings`
- **Docling**: For parsing and structuring PDF documents into machine-readable format
- **Vector Search Libraries**: Including `faiss-cpu` for efficient similarity search and retrieval
- **LangChain Ecosystem**: Including `langchain`, `langchain-core`, `langchain-docling`, and provider-specific packages (`langchain-openai`, `langchain-anthropic`)

Additional optional dependencies are available for extended functionality:
- **Visual Components**: `gradio`, `pymupdf`, and `pillow` for visualization capabilities
- **Testing Tools**: `pytest`, `pytest-asyncio`, and `pytest-mock` for unit and integration testing

**Section sources**
- [pyproject.toml](file://pyproject.toml#L10-L27)
- [pyproject.toml](file://pyproject.toml#L30-L39)

## Installation with uv

The recommended way to install this tool is using the `uv` package manager, which provides fast dependency resolution and virtual environment management.

### Step 1: Install uv
```bash
pip install uv
```

### Step 2: Create and Activate Virtual Environment
```bash
uv venv
source .venv/bin/activate
```

### Step 3: Install the Package
Install the base package with all required dependencies:
```bash
uv install
```

For development purposes, install with dev dependencies:
```bash
uv install --group dev
```

To install optional visual components:
```bash
uv install visual
```

### Alternative: Using Other Python Package Managers
You can also use `pip` with the generated lock file:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Section sources**
- [pyproject.toml](file://pyproject.toml#L48-L50)
- [uv.lock](file://uv.lock)

## Configuration Hierarchy

The system uses a hierarchical configuration system based on environment variables loaded via Pydantic Settings. Configuration follows this priority order:

1. Command-line arguments (highest priority)
2. Environment variables
3. `.env` file
4. Default values in code (lowest priority)

The configuration is managed through the `Settings` class in `src/core/config.py`, which uses `pydantic-settings` to validate and load environment variables. The `.env` file is automatically loaded from the project root.

Key configuration categories include:
- LLM providers and model specifications
- Retrieval system parameters
- Validation and reasoning models
- Docling document processing settings
- Caching and performance tuning

**Section sources**
- [.env.example](file://.env.example#L1-L112)
- [src/core/config.py](file://src/core/config.py#L11-L198)

## LLM Provider Setup

### Required API Keys
Set up your LLM provider credentials in the `.env` file:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
```

These keys are used by the LangChain integrations for OpenAI and Anthropic models.

### Model Configuration
Each component that uses an LLM has configurable model settings. For example:

```env
# Query Planner
QUERY_PLANNER_MODEL=openai:gpt-4o-mini
QUERY_PLANNER_MAX_RETRIES=2

# Relevance Validator
RELEVANCE_MODEL=openai:gpt-4o-mini
RELEVANCE_MAX_RETRIES=2

# Domain Reasoning (D1-D5)
D1_MODEL=openai:gpt-4o-mini
D2_MODEL=openai:gpt-4o-mini
D3_MODEL=openai:gpt-4o-mini
D4_MODEL=openai:gpt-4o-mini
D5_MODEL=openai:gpt-4o-mini
```

The model string follows the format `{provider}:{model_name}`. Supported providers include `openai`, `anthropic`, and others supported by LangChain.

**Section sources**
- [.env.example](file://.env.example#L2-L9)
- [src/core/config.py](file://src/core/config.py#L27-L152)

## Retrieval Model Configuration

### SPLADE Model Setup
The system supports SPLADE (SParse Lexical Annotated Document Encoder) for advanced retrieval. You can configure it in several ways:

#### Option 1: Local Model (Recommended)
Download the SPLADE model locally and reference it:
```env
SPLADE_MODEL_ID=./models/splade_distil_CoCodenser_large
```

The system will automatically detect and use a local model if the path exists.

#### Option 2: Hugging Face Model
Use a remote model from Hugging Face:
```env
SPLADE_MODEL_ID=naver/splade-v3
SPLADE_HF_TOKEN=hf-...
```

You'll need to provide a Hugging Face token if accessing gated models.

#### Device Configuration
Specify the device for model execution:
```env
SPLADE_DEVICE=mps  # Use Apple Silicon GPU
# SPLADE_DEVICE=cuda  # Use NVIDIA GPU
# SPLADE_DEVICE=cpu   # Use CPU (default)
```

**Section sources**
- [.env.example](file://.env.example#L21-L28)
- [src/retrieval/engines/splade.py](file://src/retrieval/engines/splade.py#L13-L38)
- [scripts/check_splade_retrieval.py](file://scripts/check_splade_retrieval.py#L50-L53)

## Optional Components

### FAISS Vector Search
The system includes FAISS support for inner-product similarity search:

```env
# No additional configuration needed - uses faiss-cpu by default
```

FAISS is automatically used when dense embedding retrieval is enabled. The `faiss-cpu` package is included in dependencies.

To verify FAISS installation:
```python
from retrieval.engines.faiss_ip import build_ip_index, search_ip
```

### Reranking Configuration
Enable cross-encoder reranking after retrieval:

```env
RERANKER_MODEL_ID=ncbi/MedCPT-Cross-Encoder
RERANKER_DEVICE=cpu
RERANKER_MAX_LENGTH=512
RERANKER_BATCH_SIZE=8
RERANKER_TOP_N=50
```

This reranks results from multiple retrieval engines using a specialized cross-encoder model.

### Domain Audit Mode
Enable full-text audit mode for comprehensive validation:

```env
DOMAIN_AUDIT_MODE=llm
DOMAIN_AUDIT_MODEL=openai:gpt-4o-mini
DOMAIN_AUDIT_RERUN_DOMAINS=true
DOMAIN_AUDIT_FINAL=true
```

This runs an additional audit pass on the full document to patch evidence and re-run domain assessments.

**Section sources**
- [.env.example](file://.env.example#L30-L36)
- [src/retrieval/engines/faiss_ip.py](file://src/retrieval/engines/faiss_ip.py#L12-L32)
- [.env.example](file://.env.example#L92-L105)

## Environment Variable Examples

### Development Configuration
```env
# Use local models and CPU
SPLADE_MODEL_ID=./models/splade_distil_CoCodenser_large
SPLADE_DEVICE=cpu
RERANKER_DEVICE=cpu
LANGSMITH_TRACING=false
```

### Production Configuration
```env
# Use cloud models and GPU acceleration
SPLADE_MODEL_ID=naver/splade-v3
SPLADE_DEVICE=cuda
SPLADE_HF_TOKEN=hf-...
RERANKER_DEVICE=cuda
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=production-rob2
```

### Apple Silicon Mac Configuration
```env
# Optimize for M1/M2/M3 Macs
SPLADE_DEVICE=mps
RERANKER_DEVICE=mps
# Set environment variable for PyTorch
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

**Section sources**
- [.env.example](file://.env.example#L1-L112)

## Verification Steps

### Step 1: Verify Installation
```bash
uv run rob2 --version
```

This should output the package version (e.g., 0.1.1).

### Step 2: Check CLI Help
```bash
uv run rob2 --help
```

Verify that the main command and subcommands are available.

### Step 3: Test Retrieval Setup
```bash
uv run rob2 retrieval splade --help
```

Ensure the retrieval commands are properly installed.

### Step 4: Validate Environment Loading
Create a test script to verify configuration:
```python
from src.core.config import get_settings
settings = get_settings()
print(f"SPLADE Model: {settings.splade_model_id}")
print(f"OpenAI API Key present: {'*' * bool(settings.model_dump().get('openai_api_key'))}")
```

### Step 5: Run Sample Check
Use the provided script to test SPLADE retrieval:
```bash
python scripts/check_splade_retrieval.py --help
```

**Section sources**
- [src/cli/app.py](file://src/cli/app.py#L41-L50)
- [pyproject.toml](file://pyproject.toml#L42)
- [src/core/config.py](file://src/core/config.py#L193-L196)

## Common Installation Issues

### Issue 1: Python Version Compatibility
**Problem**: "Requires-Python: >=3.13" error
**Solution**: Upgrade to Python 3.13 or higher:
```bash
# Using pyenv
pyenv install 3.13.0
pyenv local 3.13.0
```

### Issue 2: FAISS Import Errors
**Problem**: "faiss is required for FAISS indexing" RuntimeError
**Solution**: Ensure faiss-cpu is properly installed:
```bash
uv pip uninstall faiss-cpu
uv pip install faiss-cpu
```

On macOS with Apple Silicon, you may need to set:
```bash
export KMP_DUPLICATE_LIB_OK=TRUE
```

### Issue 3: SPLADE Model Access
**Problem**: Hugging Face model access denied
**Solution**: 
1. Ensure you have accepted the model terms on Hugging Face
2. Set your HF token:
```env
SPLADE_HF_TOKEN=your_token_here
# Or set environment variable
export HF_TOKEN=your_token_here
```

### Issue 4: CUDA/GPU Issues
**Problem**: CUDA out of memory or not detected
**Solution**:
```env
# Fall back to CPU if GPU issues occur
SPLADE_DEVICE=cpu
RERANKER_DEVICE=cpu
```

Or reduce batch sizes:
```env
SPLADE_BATCH_SIZE=4
RERANKER_BATCH_SIZE=4
```

### Issue 5: Environment Variables Not Loading
**Problem**: Settings not reading from .env file
**Solution**: Verify the .env file is in the project root and named correctly. The system looks for `.env` by default.

You can also create a `.env` file from the example:
```bash
cp .env.example .env
# Then edit .env with your actual values
```

**Section sources**
- [src/retrieval/engines/faiss_ip.py](file://src/retrieval/engines/faiss_ip.py#L18-L21)
- [src/retrieval/engines/splade.py](file://src/retrieval/engines/splade.py#L28-L30)
- [src/core/config.py](file://src/core/config.py#L186-L190)