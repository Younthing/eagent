# eagent / ROB2

用于 ROB2 风险偏倚评估的本地流水线与调试工具，支持证据定位、验证、领域推理与结果汇总。

## 快速开始

```bash
uv run rob2 -h
uv run rob2 run /path/to.pdf --json
```

## Docker (uv)

准备环境变量文件（首次使用）：

```bash
cp .env.example .env
```

构建镜像：

```bash
docker build -t eagent:local .
```

使用本地 .env + 模型 + 示例 PDF：

```bash
docker run --rm --env-file .env \
  -v "$PWD/models:/app/models:ro" \
  -v "$PWD/example:/data:ro" \
  -v "$PWD/outputs:/outputs" \
  eagent:local run /data/2.Angelone.pdf --json --output-dir /outputs
```

使用 docker compose：

```bash
docker compose run --rm rob2 run /data/2.Angelone.pdf --json --output-dir /outputs
```

说明：
- 镜像默认不包含 `models/`，请挂载本地模型目录或将 `SPLADE_MODEL_ID` 指向可用的远程模型。
- 需要写文件时可使用 `--output-dir /outputs` 并挂载 `./outputs:/outputs`。
