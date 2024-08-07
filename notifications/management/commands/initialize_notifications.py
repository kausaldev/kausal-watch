from random import randrange
import re

from django.utils import translation
from django.utils.translation import pgettext
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from actions.models import Plan
from notifications.models import BaseTemplate, NotificationType, AutomaticNotificationTemplate, ContentBlock


ALPHANUM = 'abcdefghijklmnopqrstuvwxyz0123456789'


def generate_draftail_block_key():
    return ''.join((ALPHANUM[randrange(0, len(ALPHANUM))] for _ in range(0, 5)))


def split_into_draftail_paragraphs(s):
    return "\n".join((f'<p data-block-key="{generate_draftail_block_key()}">{x.strip()}</p>'
                      for x in re.split(r'\n\n+', s.strip())))


def initialize_notification_templates(
    plan_identifier=None
):
    plan = Plan.objects.get(identifier=plan_identifier)
    locale = plan.primary_language
    translation.activate(locale)
    base_template_defaults = {
        'from_name': plan.name,
        'from_address': settings.DEFAULT_FROM_EMAIL,
        'reply_to': None,
        'brand_dark_color': None,
        'logo_id': None,
        'font_family': None,
        'font_css_url': None
    }
    base_template, created = BaseTemplate.objects.get_or_create(plan=plan, defaults=base_template_defaults)
    for notification_type in NotificationType:
        default_intro_text = notification_type.default_intro_text
        if default_intro_text is None:
            continue

        defaults = {
            'subject': notification_type.verbose_name,
        }
        template, created = AutomaticNotificationTemplate.objects.get_or_create(
            base=base_template, type=notification_type.identifier, defaults=defaults)
        ContentBlock.objects.get_or_create(
            template=template, identifier='intro', base=base_template,
            defaults={'content': split_into_draftail_paragraphs(default_intro_text)}
        )

    default_shared_texts = {
        'motivation': pgettext(
            'motivation',
            "Thank you for keeping the action plan updated. "
            "Up-to-date information about the actions is essential "
            "for us to achieve our goals."),
        'outro': pgettext(
            'outro',
            "If you are having difficulties using the action "
            "plan watch platform, please send an email to the "
            "administrators of the action plan.\n\n"
            "Thank you for taking part in implementing the action plan!\n\n"
            "Kind regards,\nthe action plan administrators"),
    }

    for block_type in ['motivation', 'outro']:
        ContentBlock.objects.get_or_create(
            template=None, identifier=block_type, base=base_template,
            defaults={'content': split_into_draftail_paragraphs(default_shared_texts.get(block_type))}
        )


class Command(BaseCommand):
    help = 'Initializes the email notification templates to a good value'

    def add_arguments(self, parser):
        parser.add_argument('--plan', type=str, help='Identifier of the action plan')

    def handle(self, *args, **options):
        if not options['plan']:
            raise CommandError('No plan supplied')

        initialize_notification_templates(
            plan_identifier=options['plan'],
        )
