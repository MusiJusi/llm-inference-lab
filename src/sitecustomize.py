"""Install safe logging in the API process and every spawned Python worker."""

import json
import logging
import logging.config
import os
import sys
import threading
import traceback
from pathlib import Path


def private_exception_hook(error_type, error, traceback):
    logging.getLogger("app.audit").error(
        "runtime_failure", extra={"event": "runtime_failure"},
        exc_info=(error_type, error, traceback),
    )


def private_print_exception(exc, value=None, tb=None, *args, **kwargs):
    if isinstance(exc, BaseException):
        private_exception_hook(type(exc), exc, exc.__traceback__)
    elif isinstance(value, BaseException):
        private_exception_hook(exc, value, tb)
    else:
        logging.getLogger("app.audit").error("runtime_failure", extra={"event":"runtime_failure"})


try:
    config_path = os.environ.get("APP_LOGGING_CONFIG")
    if config_path:
        logging.config.dictConfig(json.loads(Path(config_path).read_text(encoding="utf-8")))
        logging.captureWarnings(True)
        traceback.print_exception = private_print_exception
        sys.excepthook = private_exception_hook
        threading.excepthook = lambda args: private_exception_hook(args.exc_type, args.exc_value, args.exc_traceback)
        sys.unraisablehook = lambda args: private_exception_hook(args.exc_type, args.exc_value, args.exc_traceback)
except Exception:
    sys.stderr.write('{"event":"logging_setup_failed"}\n')
    os._exit(1)
