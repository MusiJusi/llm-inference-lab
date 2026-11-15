# Qwen3-4B-Instruct

Профиль для `Qwen/Qwen3-4B-Instruct-2507` в BF16. Ревизия модели закреплена полным SHA. Все три части весов проверены по официальным SHA-256 Hugging Face.

Веса находятся в каталоге `models/` внутри проекта. Compose подключает эту папку напрямую; сервер видит её только для чтения. В проверенном окружении это `D:\GitProjects\LLM_inference\models`. Каталог исключён из Git и контекста сборки образа.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Profile qwen3-4b -SkipBuild
python scripts/check_gpu.py --profile qwen3-4b --output results/comparison/qwen3-4b/environment.json
python scripts/check_local.py --profile qwen3-4b --output-dir results/comparison/qwen3-4b
```

`-SkipBuild` подходит для уже собранных образов. При первом запуске на другом компьютере его следует убрать. Если готового снимка в `models/` нет, загрузчик скачает указанную ревизию в эту папку.

Параметры профиля: контекст 4096 токенов, до четырёх последовательностей, до 2048 токенов в пакете и бюджет памяти GPU 82%. Пробный запуск с одной последовательностью и контекстом 2048 также выполнен. При старте проверяются локальные SHA-256; дополнительные обращения к Hugging Face для готовой модели не требуются.

```powershell
python scripts/benchmark.py --model qwen3-4b-instruct --requests 50 --concurrency-levels 1 2 4 --max-tokens 128 --warmup-rounds 3 --ignore-eos --gpu-metrics --output results/comparison/qwen3-4b/benchmark.json
```

Для возвращения к обычному профилю Qwen2.5:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Profile default -SkipBuild
```
