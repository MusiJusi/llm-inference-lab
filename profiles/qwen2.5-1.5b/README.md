# Qwen2.5-1.5B: профиль для сравнения

Этот профиль использует ту же модель и сохранённые веса, что и запуск по умолчанию. Лимиты приведены к параметрам Qwen3: контекст 4096 токенов, четыре последовательности, пакет 2048 токенов и бюджет памяти GPU 82%.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Profile qwen2.5-1.5b -SkipBuild
python scripts/check_gpu.py --profile qwen2.5-1.5b --output results/comparison/qwen2.5-1.5b/environment.json
python scripts/check_local.py --profile qwen2.5-1.5b --output-dir results/comparison/qwen2.5-1.5b
python scripts/benchmark.py --model qwen2.5-1.5b-instruct --requests 50 --concurrency-levels 1 2 4 --max-tokens 128 --warmup-rounds 3 --ignore-eos --gpu-metrics --output results/comparison/qwen2.5-1.5b/benchmark.json
```

Параметры запуска по умолчанию в `config/` сохранены отдельно. Исторические измерения находятся в `results/benchmark.json`; сопоставление моделей использует новые прогоны в `results/comparison/`.
