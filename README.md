# LLM Inference Lab

Reproducible GPU inference with vLLM, persistent model snapshots and privacy-preserving request logs.

The first GPU profile targets Qwen/Qwen3-4B-Instruct-2507 on a single NVIDIA GPU.

## Development

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
