from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OrgsConfig(AppConfig):
    name = 'orgs'
    verbose_name = _('Organizations')
