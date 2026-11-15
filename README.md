# LLM Inference Lab

[![CI](https://github.com/MusiJusi/llm-inference-lab/actions/workflows/validate.yaml/badge.svg)](https://github.com/MusiJusi/llm-inference-lab/actions/workflows/validate.yaml)

Локальный сервис языковых моделей на NVIDIA GPU: OpenAI-совместимый API, потоковые ответы, постоянный кэш весов и воспроизводимые нагрузочные измерения.

| Компонент | Конфигурация |
| --- | --- |
| Модели | Qwen2.5-1.5B-Instruct и Qwen3-4B-Instruct-2507, BF16 |
| Сервер | vLLM 0.25.1, PyTorch 2.11.0, CUDA 13.0 |
| Проверяемое оборудование | RTX 5070 Ti Laptop, 12 ГБ VRAM |
| Запуск | Docker Compose или Kubernetes с NVIDIA GPU |
| API | `http://127.0.0.1:8001/v1` |

Сервер и загрузчик работают от UID 10001 с файловой системой только для чтения. Веса загружаются отдельным контейнером, проверяются по SHA-256 и сохраняются между запусками. Авторизация использует Bearer-токен; серверные логи содержат метаданные запросов без их текстов и ответов модели.

**Проверено:** 29 тестов в Linux, интеграционные проверки обеих моделей в Compose, Kubernetes с Qwen2.5, 600 запросов при сравнении моделей без ошибок.

## Быстрый запуск

Понадобятся Python, Docker Desktop с WSL 2 и актуальный драйвер NVIDIA. GPU должен быть доступен Linux-контейнерам.

```powershell
git clone https://github.com/MusiJusi/llm-inference-lab.git
cd llm-inference-lab
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

Первый запуск скачивает образ и модель. Повторные запуски используют сохранённые веса. Локальный токен создаётся в `.local/api-token`; этот каталог исключён из Git и контекста сборки.

```powershell
python scripts/check_gpu.py
python scripts/check_local.py
```

Проверки выполняют генерацию, streaming, запросы с неверным токеном, проверяют приватность логов, доступ к кэшу без сети и перезапуск сервера.

## Запрос к модели

```powershell
$headers = @{ Authorization = 'Bearer ' + (Get-Content .local/api-token -Raw).Trim() }
$payload = @{
    model = (Invoke-RestMethod -Uri 'http://127.0.0.1:8001/v1/models' -Headers $headers).data[0].id
    messages = @(@{ role = 'user'; content = 'Объясни назначение Docker в двух предложениях.' })
    max_tokens = 128
    temperature = 0
} | ConvertTo-Json -Depth 5
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/v1/chat/completions' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($payload))
$reply.choices[0].message.content
```

## Модели и измерения

По умолчанию запускается Qwen2.5-1.5B. Для Qwen3 используйте отдельный профиль:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Profile qwen3-4b -SkipBuild
python scripts/check_gpu.py --profile qwen3-4b --output results/comparison/qwen3-4b/environment.json
python scripts/check_local.py --profile qwen3-4b --output-dir results/comparison/qwen3-4b
python scripts/benchmark.py --model qwen3-4b-instruct --requests 50 --concurrency-levels 1 2 4 --max-tokens 128 --warmup-rounds 3 --ignore-eos --gpu-metrics --output results/comparison/qwen3-4b/benchmark.json
```

`-SkipBuild` используется после первой сборки. Веса Qwen3 хранятся в папке `models/` внутри проекта, около 7,5 ГиБ. Смена профиля заменяет сервер: одновременно работает одна модель. [Профили и хранение весов](docs/RUNBOOK.md#выбор-модели-в-compose).

Сравнение на RTX 5070 Ti Laptop: **по 300 запросов на модель, 0 ошибок**, 128 выходных токенов на запрос. Лимиты сервера одинаковы; короткий и длинный вход, три уровня параллельности, отдельный прогрев полных пакетов.

| Вход | Параллельность | Qwen2.5-1.5B, токенов/с | Qwen3-4B, токенов/с |
| --- | ---: | ---: | ---: |
| Короткий | 1 | 115.60 | 47.99 |
| Длинный | 1 | 108.35 | 44.58 |
| Короткий | 2 | 220.60 | 99.18 |
| Длинный | 2 | 197.59 | 86.68 |
| Короткий | 4 | 417.64 | 189.35 |
| Длинный | 4 | 341.90 | 148.02 |

Это суммарная пропускная способность сервиса. Качество ответов данным прогоном не измерялось. [Методика, задержки, память и исходные данные](docs/COMPARISON.md) · [Сводка CSV](results/comparison/summary.csv) · [Первоначальный прогон](docs/BENCHMARK.md).

## Kubernetes

Манифесты Kustomize используют `initContainer`, PVC, ConfigMap, Secret и ресурс `nvidia.com/gpu: 1`. Скрипт создаёт отдельный Minikube-профиль и хранит его kubeconfig внутри проекта.

```powershell
# Освободить GPU перед переключением с Compose.
docker compose stop server
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-kubernetes.ps1 -SkipBuild
$env:KUBECONFIG = Join-Path (Get-Location) '.local/kubeconfig'
python scripts/check_cluster.py
```

Подробности запуска, импорт существующего кэша и особенности WSL описаны в [RUNBOOK.md](docs/RUNBOOK.md).

## Структура

| Каталог / файл | Назначение |
| --- | --- |
| `src/app/` | Загрузка весов, проверка снимка, запуск vLLM, авторизация и аудит |
| `config/` | Модель, настройки инференса и безопасное журналирование |
| `Dockerfile`, `downloader/` | GPU-сервер и отдельный лёгкий загрузчик |
| `compose.yaml`, `k8s/` | Локальный запуск и развёртывание в Kubernetes |
| `scripts/` | Запуск, интеграционные проверки и бенчмарк |
| `tests/` | Модульные тесты конфигурации, кэша, авторизации и приватности |
| `results/` | Измерения и параметры окружения |
| `profiles/` | Дополнительные конфигурации моделей |

[Архитектура](docs/ARCHITECTURE.md) · [Запуск и диагностика](docs/RUNBOOK.md) · [Проверки](docs/VALIDATION.md)
