"""
WSGI config for aplans project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os
from loguru import logger

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aplans.settings')

django_application = get_wsgi_application()


def run_deployment_checks():
    from django.core import checks  # noqa

    msgs: list[checks.CheckMessage] = checks.run_checks(include_deployment_checks=True)
    LEVEL_MAP = {
        checks.DEBUG: 'DEBUG',
        checks.INFO: 'INFO',
        checks.WARNING: 'WARNING',
        checks.ERROR: 'ERROR',
        checks.CRITICAL: 'CRITICAL',
    }

    for msg in msgs:
        msg.hint = None
        logger.log(LEVEL_MAP.get(msg.level, 'WARNING'), str(msg))

# We execute all the checks when running under uWSGI, so that we:
#   - load more of the code to save memory after uWSGI forks workers
#   - keep the state of the system closer to how it is under runserver
try:
    import uwsgi  # type: ignore  # noqa
    run_deployment_checks()
    from datetime import datetime, UTC
    from .log_handler import ISO_FORMAT
    def set_time():
        now = datetime.now(UTC)
        uwsgi.set_logvar('isotime', now.strftime(ISO_FORMAT).replace('+00:00', 'Z'))
except ImportError:
    def set_time():
        pass


def application(env, start_response):
    ret = django_application(env, start_response)
    set_time()
    return ret
