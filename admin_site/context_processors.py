from django.conf import settings


def sentry(request):
    return dict(sentry_dsn=settings.SENTRY_DSN)
