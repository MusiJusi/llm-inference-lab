# LLM Inference Lab

[![CI](https://github.com/MusiJusi/llm-inference-lab/actions/workflows/validate.yaml/badge.svg)](https://github.com/MusiJusi/llm-inference-lab/actions/workflows/validate.yaml)

Локальный сервис языковой модели на NVIDIA GPU: OpenAI-совместимый API, потоковые ответы, постоянный кэш весов и воспроизводимые нагрузочные измерения.

| Компонент | Конфигурация |
| --- | --- |
| Модель | Qwen2.5-1.5B-Instruct, BF16, закреплённая ревизия |
| Сервер | vLLM 0.25.1, PyTorch 2.11.0, CUDA 13.0 |
| Проверяемое оборудование | RTX 5070 Ti Laptop, 12 ГБ VRAM |
| Запуск | Docker Compose или Kubernetes с NVIDIA GPU |
| API | `http://127.0.0.1:8001/v1` |

Сервер и загрузчик работают от UID 10001 с файловой системой только для чтения. Веса загружаются отдельным контейнером, проверяются по SHA-256 и сохраняются между запусками. Авторизация использует Bearer-токен; серверные логи содержат метаданные запросов без их текстов и ответов модели.

**Проверено:** 25 тестов в Linux, интеграционные прогоны Docker Compose и Kubernetes, 300 нагрузочных запросов без ошибок.

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
    model = 'qwen2.5-1.5b-instruct'
    messages = @(@{ role = 'user'; content = 'Объясни назначение Docker в двух предложениях.' })
    max_tokens = 128
    temperature = 0
} | ConvertTo-Json -Depth 5
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/v1/chat/completions' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($payload))
$reply.choices[0].message.content
```

## Нагрузочные измерения

```powershell
python scripts/benchmark.py --requests 50 --concurrency-levels 1 2 4 --max-tokens 128 --warmup-requests 3 --ignore-eos --gpu-metrics
```

Два размера входного текста, три уровня параллельности, всего 300 измеряемых запросов. Отчёт содержит TTFT, полную задержку, время на выходной токен, пропускную способность и телеметрию GPU. Методика и результаты находятся в [BENCHMARK.md](docs/BENCHMARK.md).

Прогон на RTX 5070 Ti Laptop: **300 запросов, 0 ошибок**, 128 выходных токенов на запрос.

| Вход | Параллельность | TTFT p50, мс | Выходных токенов/с |
| --- | ---: | ---: | ---: |
| Короткий | 1 | 27.9 | 103.58 |
| Длинный | 1 | 79.6 | 105.39 |
| Короткий | 2 | 32.0 | 214.65 |
| Длинный | 2 | 121.1 | 175.41 |
| Короткий | 4 | 38.7 | 431.85 |
| Длинный | 4 | 191.4 | 316.75 |

[Исходные измерения](results/benchmark.json) · [Окружение](results/environment.json)

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
