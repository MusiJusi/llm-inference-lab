# Проверки

## Автоматические проверки

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

25 тестов проверяют авторизацию, потоковый аудит, скрытие исключений, конфигурацию GPU, расчёт метрик, атомарность загрузки и целостность весов. Все тесты выполняются в Linux. В Windows два теста файловых блокировок пропускаются, поскольку загрузчик работает в Linux-контейнере.

[GitHub Actions](https://github.com/MusiJusi/llm-inference-lab/actions) запускает тесты, проверяет Compose и Kustomize и собирает лёгкий загрузчик. У стандартного runner нет NVIDIA GPU, поэтому полный GPU-прогон выполняется локально.

## Docker Compose

```powershell
python scripts/check_gpu.py
python scripts/check_local.py
```

Проверяются UID 10001, настоящее CUDA-вычисление, запросы без токена и с неверным токеном, генерация, streaming, ошибки валидации, неизвестный маршрут и приватность логов. В логах ищутся уникальные входные маркеры, фактический ответ модели и токен; одновременно проверяется наличие события успешной генерации.

Отдельный контейнер проверяет готовый кэш с `--network none`, запретом `socket.connect` и отключённым импортом Hugging Face Hub. Затем сервер перезапускается с тем же образом и повторно проходит проверки API.

## Kubernetes

```powershell
$env:KUBECONFIG = Join-Path (Get-Location) '.local/kubeconfig'
python scripts/check_cluster.py
```

Применяются аналогичные проверки API и логов, отдельный offline Job и перезапуск Pod с сохранением PVC. Загрузка модели выполняется initContainer; конфигурация поступает через ConfigMap и Secret.

Локальная проверка использует снимок модели, импортированный из существующего кэша. Это проверка повторного использования весов, а не измерение времени первой загрузки из сети.

## Артефакты

| Файл | Содержимое |
| --- | --- |
| `results/environment.json` | Модель, образ, версии CUDA/PyTorch/vLLM и реальный GPU |
| `results/integration.json` | Проверки Compose и перезапуска |
| `results/smoke.json` | Авторизация, генерация и приватность логов |
| `results/kubernetes.json` | Проверки Kubernetes |
| `results/benchmark.json` | Исходные измерения нагрузки и GPU-телеметрия |
