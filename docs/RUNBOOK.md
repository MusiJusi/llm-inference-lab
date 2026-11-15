# Запуск и диагностика

## Windows / Docker Compose

Требуются Python, Docker Desktop с Linux-контейнерами и WSL 2, а также драйвер NVIDIA с поддержкой CUDA 13.0. Проверенное окружение использует RTX 5070 Ti Laptop с 12 ГБ VRAM. Точную совместимость другой видеокарты нужно проверить отдельным запуском.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

Скрипт создаёт новый локальный API-токен при его отсутствии, собирает образы и дожидается готовности. Для готовых образов можно добавить `-SkipBuild`. Для публичной модели HF-токен не нужен; для модели с ограниченным доступом задайте `HF_TOKEN` в окружении перед запуском.

```powershell
python scripts/check_gpu.py
python scripts/check_local.py
docker compose ps
docker compose logs --no-color server
```

Чтобы остановить сервис и сохранить веса:

```powershell
docker compose down
```

Том `llm-inference-lab-models` сохраняется. Повторный `start-local.ps1 -SkipBuild` использует его без скачивания готовой модели.

## Linux / Docker Compose

Требуются Docker Compose с поддержкой `gpus`, NVIDIA Container Toolkit и доступ GPU в контейнеры.

```bash
mkdir -p .local
python3 -c 'import pathlib,secrets; p=pathlib.Path(".local/api-token"); p.exists() or p.write_text(secrets.token_urlsafe(32))'
python3 -c 'import os,pathlib; pathlib.Path(".local/hf-token").write_text(os.environ.get("HF_TOKEN", ""))'
docker compose build
docker compose up --detach --wait --wait-timeout 1800
python3 scripts/check_gpu.py
python3 scripts/check_local.py
```

## Minikube с GPU

Понадобятся Minikube 1.39.0 и kubectl. Скрипт ищет `minikube` в PATH, затем `.local/bin/minikube.exe`. Его настройки и kubeconfig сохраняются внутри `.local/`; команды используют контекст `llm-inference-lab-gpu` и namespace `llm-inference-lab`.

Одна видеокарта используется одним сервером. Перед переключением с Compose:

```powershell
docker compose stop server
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-kubernetes.ps1 -SkipBuild -ImportLocalCache
$env:KUBECONFIG = Join-Path (Get-Location) '.local/kubeconfig'
python scripts/check_cluster.py
```

`-ImportLocalCache` копирует готовый снимок из тома этого проекта в отдельный PVC. Импорт ограничен выделенным узлом и PVC; существующий завершённый снимок не перезаписывается. Без этого параметра initContainer скачает модель самостоятельно. Первый перенос большого GPU-образа в Minikube может занять заметное время.

В WSL скрипт настраивает NVIDIA CDI и библиотеку `libdxcore.so` внутри выделенного Minikube-узла. Изменения Docker Engine на хосте не требуются. На обычном Linux требуется настроенный NVIDIA runtime и device plugin; сами манифесты остаются теми же.

Для ручного обращения к Kubernetes API:

```powershell
$env:KUBECONFIG = Join-Path (Get-Location) '.local/kubeconfig'
kubectl --context llm-inference-lab-gpu -n llm-inference-lab port-forward service/vllm 8001:8000
```

Чтобы вернуться к Compose:

```powershell
kubectl --context llm-inference-lab-gpu -n llm-inference-lab scale deployment/vllm --replicas=0
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -SkipBuild
```

## Настройки и секреты

| Файл | Назначение |
| --- | --- |
| `config/model.env` | Идентификатор модели, закреплённая ревизия и каталог весов |
| `config/inference.json` | Контекст, параллельность, BF16 и бюджет памяти GPU |
| `config/runtime.json` | Закреплённый образ и сведения о версии vLLM |
| `.local/api-token` | Локальный Bearer-токен |
| `.local/hf-token` | Необязательный HF-токен, доступный только загрузчику |

Compose читает конфигурацию из `config/`. Для Kubernetes соответствующие файлы лежат в `k8s/base/config/`; тест проверяет их совпадение. После изменения параметров примените конфигурацию и перезапустите сервис. Менять или пересобирать GPU-образ для смены модели и лимитов не требуется.

## Выбор модели в Compose

| Профиль | Модель | Где лежат веса | Память GPU / пакет |
| --- | --- | --- | --- |
| `default` | Qwen2.5-1.5B-Instruct | Docker volume | 65% / 4096 токенов |
| `qwen2.5-1.5b` | Qwen2.5-1.5B-Instruct | Тот же Docker volume | 82% / 2048 токенов |
| `qwen3-4b` | Qwen3-4B-Instruct-2507 | Папка `models/` внутри проекта | 82% / 2048 токенов |

Все профили используют BF16, контекст 4096 и до четырёх последовательностей. Два именованных профиля имеют одинаковые лимиты для сравнения моделей. Скрипт заменяет только сервер и загрузчик этого Compose-проекта; одновременно работает одна модель.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Profile qwen3-4b -SkipBuild
python scripts/check_gpu.py --profile qwen3-4b --output results/comparison/qwen3-4b/environment.json
python scripts/check_local.py --profile qwen3-4b --output-dir results/comparison/qwen3-4b
```

Для первого запуска без готовых образов уберите `-SkipBuild`. Готовые веса проверяются по SHA-256 без повторного скачивания. Qwen3 занимает около 7,5 ГиБ в `models/`; на проверенной машине это `D:\GitProjects\LLM_inference\models`. Папка подключается напрямую, сервер получает доступ только для чтения. Образ Docker не содержит весов.

Команды `docker compose` без дополнительных `-f` описывают профиль `default`. Для ручного управления Qwen3 используйте оба файла:

```powershell
docker compose -f compose.yaml -f profiles/qwen3-4b/compose.yaml ps
docker compose -f compose.yaml -f profiles/qwen3-4b/compose.yaml logs --no-color server
docker compose -f compose.yaml -f profiles/qwen3-4b/compose.yaml stop server
```

Результаты и команды сравнения находятся в [COMPARISON.md](COMPARISON.md). Kubernetes проверен с Qwen2.5; профили Qwen3 в этом разделе относятся к Compose.

## Диагностика

| Симптом | Что проверить |
| --- | --- |
| Docker недоступен | Запущен ли Docker Desktop и выбран ли WSL 2 backend |
| CUDA недоступна | Драйвер, поддержку GPU контейнерами и `python scripts/check_gpu.py` |
| Ошибка UVA | В образе должен быть `VLLM_USE_V2_MODEL_RUNNER=0` |
| Triton не загружает `.so` | `/tmp` сервера должен быть доступен для исполнения; в Compose используется `exec` |
| GPU отсутствует в Kubernetes | Системный NVIDIA plugin, CDI и `python scripts/configure_wsl_gpu.py` в WSL |
| `ErrImageNeverPull` | Образы нужно загрузить в выделенный Minikube-профиль через `minikube image load` |
| HTTP 401 | Используется ли актуальный токен из `.local/api-token` |
| Ошибка загрузки модели | HTTPS/DNS-доступ к Hugging Face, доступность ревизии, место на диске и права на том |

Серверные исключения сохраняются как тип ошибки и расположение в коде. Тексты пользовательских запросов и ответов в диагностику не включаются.

## Обновление окружения

При смене базового образа закрепите новый digest в `Dockerfile` и `config/runtime.json`, затем обновите инвентаризацию:

```powershell
python scripts/freeze_runtime.py
docker compose build server
```

Сборка проверяет полный набор активных Python-пакетов. После обновления повторите модульные и GPU-интеграционные проверки, а затем измерения производительности.
