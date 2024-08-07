from __future__ import annotations

import logging
import re
import reversion
import typing
import zoneinfo
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core import management
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, RegexValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _, pgettext_lazy, gettext
from django_countries.fields import CountryField
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from modeltrans.fields import TranslationField
from typing import ClassVar, Optional, Tuple, Union
from urllib.parse import urlparse
from wagtail.models import Collection, Page, Site, WorkflowTask
from wagtail.models.i18n import Locale
from wagtail_localize.operations import TranslationCreator  # type: ignore

from aplans.types import UserOrAnon, WatchAPIRequest, WatchRequest
from aplans.utils import (
    ChoiceArrayField,
    IdentifierField,
    OrderedModel,
    ModelWithPrimaryLanguage,
    PlanRelatedModel,
    validate_css_color,
    get_default_language,
    get_supported_languages
)
from indicators.models import Indicator, IndicatorLevel, RelatedIndicator
from orgs.models import Organization
from people.models import Person

if typing.TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from .action import ActionStatus, ActionImplementationPhase, ActionManager
    from .category import CategoryType
    from .features import PlanFeatures
    from aplans.graphql_types import WorkflowStateEnum
    from reports.models import ReportType
    from feedback.models import UserFeedback
    from orgs.models import OrganizationPlanAdmin


logger = logging.getLogger(__name__)

TIMEZONES = [(x, x) for x in sorted(zoneinfo.available_timezones(), key=str.lower)]


def get_plan_identifier_from_wildcard_domain(hostname: str, request: WatchRequest | None = None) -> Union[Tuple[str, str], Tuple[None, None]]:
    # Get plan identifier from hostname for development and testing
    parts = hostname.split('.', maxsplit=1)
    req_wildcards = getattr(request, 'wildcard_domains', None) or []
    wildcard_domains = (settings.HOSTNAME_PLAN_DOMAINS or []) + req_wildcards
    if len(parts) == 2 and parts[1].lower() in wildcard_domains:
        return (parts[0], parts[1])
    else:
        return (None, None)


def get_page_translation(page: Page, fallback=True) -> Page:
    """Return translation of `page` in activated language, fall back to `page` by default."""
    language = translation.get_language()
    try:
        locale = Locale.objects.get(language_code__iexact=language)
        page = page.get_translation(locale)
    except (Locale.DoesNotExist, Page.DoesNotExist):
        if not fallback:
            raise
    return page


class PlanQuerySet(models.QuerySet['Plan']):
    def for_hostname(self, hostname, request: WatchAPIRequest | None = None):
        hostname = hostname.lower()
        plan_domains = PlanDomain.objects.filter(hostname=hostname)
        lookup = Q(id__in=plan_domains.values_list('plan'))
        # Get plan identifier from hostname for development and testing
        identifier, _ = get_plan_identifier_from_wildcard_domain(hostname, request=request)
        if identifier:
            lookup |= Q(identifier=identifier)
        return self.filter(lookup)

    def live(self):
        return self.filter(published_at__isnull=False, archived_at__isnull=True)

    def available_for_request(self, request: WatchRequest):
        # FIXME later: support for logged-in users
        return self.live()

    def user_has_staff_role_for(self, user: UserOrAnon):
        from actions.models.action import Action

        if not user.is_authenticated or not user.is_staff:
            return self.none()
        staff_actions = Action.objects.get_queryset().user_has_staff_role_for(user).values_list('plan').distinct()
        # FIXME: Add indicators
        return self.filter(id__in=staff_actions)


def help_text_with_default_disclaimer(help_text, default_value=None):
    """Lazily formats a help text with the default value injected
       for clarity if one is available.
    """
    disclaimer = _('If you leave this blank the application will use the default value')
    if default_value:
        return format_lazy(
            '{help_text} {disclaimer} {default_value}.',
            help_text=help_text,
            disclaimer=disclaimer,
            default_value=default_value,
        )
    return format_lazy(
        '{help_text} {disclaimer}.',
        help_text=help_text,
        disclaimer=disclaimer,
    )


class UsageStatus(models.TextChoices):
    CUSTOMER_USE = 'customer_use', _('Customer use')
    SALES = 'sales', _('Sales and demos')
    DEVELOPMENT = 'development', _('Internal testing, training, development or other non-public use')
    CUSTOMER_OFFBOARDING = 'customer_offboarding', _('Offboarding in progress')
    INACTIVE = 'inactive', _('Inactive, not in use currently')
    DEPRECATED = 'deprecated', _('Deprecated, should be deleted')


@reversion.register(follow=[
    'action_statuses', 'action_implementation_phases',  # fixme
])
class Plan(ClusterableModel, ModelWithPrimaryLanguage):
    """The Action Plan under monitoring.

    Most information in this service is linked to a Plan.
    """
    DEFAULT_ACTION_DAYS_UNTIL_CONSIDERED_STALE = 180
    DEFAULT_ACTION_UPDATE_TARGET_INTERVAL = 30
    DEFAULT_ACTION_UPDATE_ACCEPTABLE_INTERVAL = 60
    MAX_ACTION_DAYS_UNTIL_CONSIDERED_STALE = 730

    name = models.CharField(
        max_length=100,
        verbose_name=_('name'),
        help_text=_('The official plan name in full form')
    )
    identifier = IdentifierField(
        unique=True,
        help_text=_(
            'A unique identifier for the plan used internally to distinguish between plans. '
            'This becomes part of the test site URL: https://[identifier].watch-test.kausal.tech. '
            'Use lowercase letters and dashes.'
        )
    )
    short_name = models.CharField(
        max_length=50, verbose_name=_('short name'),
        null=True, blank=True,
        help_text=_('A shorter version of the plan name')
    )
    version_name = models.CharField(
        max_length=100, blank=True, verbose_name=_('version name'),
        help_text=_('If this plan has multiple versions, name of this version'),
    )
    image = models.ForeignKey(
        'images.AplansImage', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('published at'))
    archived_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name=_('archived at'))

    usage_status = models.CharField(
        max_length=30,
        choices=UsageStatus.choices,
        default=UsageStatus.CUSTOMER_USE,
        verbose_name=_('Usage status'),
        help_text=_(
            'If unsure, use the default value representing customer use. For statistical purposes specify '
            'what the plan will be used for in order to differentiate between plans actually in '
            'use by customers and those created for some other reason.'
        )
    )

    site_url = models.URLField(
        blank=True, null=True, verbose_name=_('site URL'),
        validators=[URLValidator(('http', 'https'))]
    )
    actions_locked = models.BooleanField(
        default=False, verbose_name=_('actions locked'),
        help_text=_('Can actions be added and the official metadata edited?'),
    )
    organization = models.ForeignKey(
        Organization, related_name='plans', on_delete=models.PROTECT, verbose_name=_('main organization for the plan'),
    )

    general_admins = models.ManyToManyField(
        Person, blank=True, related_name='general_admin_plans', through='GeneralPlanAdmin',
        verbose_name=_('general administrators'),
        help_text=_('Persons that can modify everything related to the action plan')
    )

    site = models.OneToOneField(
        Site, null=True, on_delete=models.SET_NULL, editable=False, related_name='plan',
    )
    root_collection = models.OneToOneField(
        Collection, null=True, on_delete=models.PROTECT, editable=False, related_name='plan',
    )
    admin_group = models.OneToOneField(
        Group, null=True, on_delete=models.PROTECT, editable=False, related_name='admin_for_plan',
    )
    contact_person_group = models.OneToOneField(
        Group, null=True, on_delete=models.PROTECT, editable=False, related_name='contact_person_for_plan',
    )

    other_languages = ChoiceArrayField(
        models.CharField(max_length=8, choices=get_supported_languages(), default=get_default_language),
        default=list, null=True, blank=True
    )
    accessibility_statement_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Link to accessibility statement'),
    )
    external_feedback_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Link to external feedback form'),
        help_text=_(
            "If not empty, the system's built-in user feedback feature will be replaced by "
            "a link to an external feedback form available at this web address."
        )
    )

    uses_wagtail = models.BooleanField(default=True)
    statuses_updated_manually = models.BooleanField(default=False)
    theme_identifier = IdentifierField(verbose_name=_('Theme identifier'), null=True, blank=True)

    related_organizations = models.ManyToManyField(Organization, blank=True, related_name='related_plans')
    related_plans = models.ManyToManyField('self', blank=True)
    parent = models.ForeignKey(
        'self', verbose_name=pgettext_lazy('plan', 'parent'), blank=True, null=True, related_name='children',
        on_delete=models.SET_NULL
    )
    common_category_types = models.ManyToManyField('actions.CommonCategoryType', blank=True, related_name='plans')

    primary_action_classification = models.OneToOneField(
        # null=False would be nice, but we need to avoid on_delete=CASCADE and use on_delete=SET_NULL instead
        'actions.CategoryType', blank=False, null=True, on_delete=models.SET_NULL,
        related_name='primary_classification_for_plan',
        verbose_name=_('Primary action classification'),
        help_text=_('Used for primary navigation and grouping of actions')
    )
    secondary_action_classification = models.OneToOneField(
        'actions.CategoryType', blank=True, null=True, on_delete=models.SET_NULL,
        related_name='secondary_classification_for_plan',
        verbose_name=_('Secondary action classification'),
        help_text=(_(
            'Leave empty unless specifically required. Action filters based on this category are displayed '
            'more prominently than filters of other categories.'
        ))
    )

    action_days_until_considered_stale = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(MAX_ACTION_DAYS_UNTIL_CONSIDERED_STALE)],
        verbose_name=_('Days until actions considered stale'),
        help_text=help_text_with_default_disclaimer(
            _('Actions not updated since this many days are considered stale.'),
            DEFAULT_ACTION_DAYS_UNTIL_CONSIDERED_STALE
        )
    )

    settings_action_update_target_interval = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(365), MinValueValidator(1)],
        verbose_name=_('Target interval in days to update actions'),
        help_text=help_text_with_default_disclaimer(
            _('A desirable time interval in days within which actions should be updated in the optimal case.'),
            DEFAULT_ACTION_UPDATE_TARGET_INTERVAL
        )
    )
    settings_action_update_acceptable_interval = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(730), MinValueValidator(1)],
        verbose_name=_('Acceptable interval in days to update actions'),
        help_text=help_text_with_default_disclaimer(
            _('A maximum time interval in days within which actions should always be updated.'),
            DEFAULT_ACTION_UPDATE_ACCEPTABLE_INTERVAL
        )
    )

    superseded_by: models.ForeignKey['Plan' | None, 'Plan' | None] = models.ForeignKey(  # type: ignore[assignment]
        'self', verbose_name=pgettext_lazy('plan', 'superseded by'), blank=True, null=True, on_delete=models.SET_NULL,
        related_name='superseded_plans', help_text=_('Set if this plan is superseded by another plan')
    )
    timezone = models.CharField(max_length=64, choices=TIMEZONES, default='UTC')
    country = CountryField(blank=True)
    daily_notifications_triggered_at = models.DateTimeField(blank=True, null=True)

    cache_invalidated_at = models.DateTimeField(auto_now=True)
    i18n = TranslationField(fields=['name', 'short_name'], default_language_field='primary_language_lowercase')

    action_attribute_types = GenericRelation(
        to='actions.AttributeType',
        related_query_name='plan',
        content_type_field='scope_content_type',
        object_id_field='scope_id',
    )

    public_fields: ClassVar = [
        'id', 'name', 'short_name', 'version_name', 'identifier', 'image', 'action_schedules',
        'actions', 'category_types', 'action_statuses', 'indicator_levels',
        'action_impacts', 'general_content', 'impact_groups',
        'monitoring_quality_points', 'scenarios',
        'primary_language', 'other_languages', 'accessibility_statement_url',
        'action_implementation_phases', 'actions_locked', 'organization',
        'related_plans', 'theme_identifier', 'parent', 'children',
        'primary_action_classification', 'secondary_action_classification', 'superseded_by', 'superseded_plans',
        'report_types', 'external_feedback_url', 'action_dependency_roles',
    ]

    objects = PlanQuerySet.as_manager()
    _site_created: bool
    wagtail_reference_index_ignore = True

    # Type annotations for related models
    features: PlanFeatures
    actions: ActionManager
    action_statuses: RelatedManager[ActionStatus]
    action_implementation_phases: RelatedManager[ActionImplementationPhase]
    category_types: RelatedManager[CategoryType]
    domains: RelatedManager[PlanDomain]
    children: RelatedManager[Plan]
    report_types: RelatedManager[ReportType]
    user_feedbacks: RelatedManager[UserFeedback]
    organization_plan_admins: RelatedManager[OrganizationPlanAdmin]
    organization_id: int
    id: int

    class Meta:
        verbose_name = _('plan')
        verbose_name_plural = _('plans')
        get_latest_by = 'created_at'
        ordering = ('created_at',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._site_created = False

    def __str__(self):
        return self.name

    def get_last_action_identifier(self):
        return self.actions.order_by('order').values_list('identifier', flat=True).last()

    @cached_property
    def cached_actions(self):
        return self.actions.order_by('order')

    def clean(self):
        if self.primary_language in self.other_languages:
            raise ValidationError({'other_languages': _('Primary language must not be selected')})

        for field in ['primary_action_classification', 'secondary_action_classification']:
            value = getattr(self, field)
            if value and value not in self.category_types.all():
                raise ValidationError({field: _('Category type must belong to plan')})

        if self.actions.exists() and self.primary_action_classification is None:
            raise ValidationError(
                {'primary_action_classification': _(
                    'You must create and choose a primary category type for classifying actions'
                )})

        if (self.secondary_action_classification and
                self.secondary_action_classification == self.primary_action_classification):
            raise ValidationError({'secondary_action_classification': _(
                'Primary and secondary classification cannot be the same')})

    @property
    def root_page(self) -> Page:
        if self.site_id is None or self.site is None:
            return None
        page: Page = self.site.root_page
        return page

    def get_translated_root_page(self, fallback=True) -> Optional[Page]:
        """Return root page in activated language, fall back to default language by default."""
        if self.site_id is None:
            return None
        root = get_page_translation(self.root_page)
        return root

    def get_translated_documentation_root_page(self, fallback=True) -> Page | None:
        """Return documentation root page in activated language.

        If `fallback` is true, falls back to to the plan's primary language or, if this fails, to any language.
        """
        activated_language = translation.get_language()
        root_pages = {
            page.locale.language_code: page for page in self.documentation_root_pages.all()
        }
        try:
            return root_pages[activated_language]
        except KeyError:
            if not fallback:
                return None
        assert fallback
        try:
            return root_pages[self.primary_language]
        except KeyError:
            pass
        if root_pages:
            return next(iter(root_pages.values()))
        return None

    def create_default_site(self):
        if self.site is not None:
            return
        root_page = self.create_default_pages()
        site = Site(site_name=self.name, hostname=self.site_url, root_page=root_page)
        site.save()
        self._site_created = True
        self.site = site

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)

        update_fields = []
        if self.root_collection is None:
            with transaction.atomic():
                obj = Collection.get_first_root_node().add_child(name=self.name)
            self.root_collection = obj
            update_fields.append('root_collection')
        else:
            if self.root_collection.name != self.name:
                self.root_collection.name = self.name
                self.root_collection.save(update_fields=['name'])

        if self.site is not None and not self._site_created:
            # Synchronize site name, root page names
            self.site.site_name = self.name
            self.site.save()
            for language_code in (self.primary_language, *self.other_languages):
                with translation.override(language_code):
                    try:
                        root_page = self.get_translated_root_page()
                    except (Locale.DoesNotExist, Page.DoesNotExist):
                        pass
                    else:
                        if root_page is not None:
                            root_page.title = self.name_i18n
                            root_page.draft_title = self.name_i18n
                            root_page.save()

        group_name = '%s admins' % self.name
        if self.admin_group is None:
            obj = Group.objects.create(name=group_name)
            self.admin_group = obj
            update_fields.append('admin_group')
        else:
            if self.admin_group.name != group_name:
                self.admin_group.name = group_name
                self.admin_group.save()

        group_name = '%s contact persons' % self.name
        if self.contact_person_group is None:
            obj = Group.objects.create(name=group_name)
            self.contact_person_group = obj
            update_fields.append('contact_person_group')
        else:
            if self.contact_person_group.name != group_name:
                self.contact_person_group.name = group_name
                self.contact_person_group.save()

        if update_fields:
            super().save(update_fields=update_fields)
        return ret

    def get_site_notification_context(self):
        return dict(
            view_url=self.site_url,
            title=self.general_content.site_title
        )

    def invalidate_cache(self):
        logger.info('Invalidate cache for %s' % self)
        self.cache_invalidated_at = timezone.now()
        super().save(update_fields=['cache_invalidated_at'])

    def create_default_pages(self):
        """For each language of the plan, create plan root page as well as subpages that should be always there.

        Return root page in primary language."""
        from pages.models import (
            AccessibilityStatementPage, ActionListPage, IndicatorListPage, PlanRootPage, PrivacyPolicyPage
        )
        for language_code in [self.primary_language] + self.other_languages:
            if not Locale.objects.filter(language_code=language_code):
                Locale.objects.create(language_code=language_code)
        primary_locale = Locale.objects.get(language_code=self.primary_language)
        other_locales = [Locale.objects.get(language_code=language) for language in self.other_languages]
        translation_creator = TranslationCreator(user=None, target_locales=other_locales)

        # Create root page in primary language
        if self.site:
            primary_root_page = self.site.root_page.specific
        else:
            primary_root_page = PlanRootPage(
                title=self.name, slug=self.identifier, url_path='', locale=primary_locale
            )
            Page.get_first_root_node().add_child(instance=primary_root_page)

        # Create translations of root page
        translation_creator.create_translations(primary_root_page)
        for page in primary_root_page.get_translations():
            with translation.override(page.locale.language_code):
                page.draft_title = self.name_i18n
                page.title = self.name_i18n
                page.save(update_fields=['draft_title', 'title'])

        # Create subpages of root page
        def _dummy_function_so_makemessages_finds_strings():
            # This is never called
            _("Actions")
            _("Indicators")
            _("Privacy")
            _("Accessibility")
        subpages = [
            (ActionListPage, "Actions", {'show_in_menus': True, 'show_in_footer': True}),
            (IndicatorListPage, "Indicators", {'show_in_menus': True, 'show_in_footer': True}),
            (PrivacyPolicyPage, "Privacy", {'show_in_additional_links': False}),
            (AccessibilityStatementPage, "Accessibility", {'show_in_additional_links': False}),
        ]

        for PageModel, title_en, kwargs in subpages:
            # Create page in primary language first
            try:
                primary_subpage = primary_root_page.get_children().type(PageModel).get().specific
            except Page.DoesNotExist:
                with translation.override(self.primary_language):
                    primary_subpage = PageModel(title=gettext(title_en), locale=primary_locale, **kwargs)
                    primary_root_page.add_child(instance=primary_subpage)

            # Create translations
            translation_creator.create_translations(primary_subpage)

        return primary_root_page

    def is_live(self):
        return self.published_at is not None and self.archived_at is None

    def get_optional_locale_prefix(self, locale: str):
        if locale.lower() == self.primary_language.lower():
            return ''
        return next((f'/{lang}' for lang in self.other_languages if lang.lower() == locale.lower()), '')

    def get_view_url(self, client_url: Optional[str] = None, active_locale: str | None = None) -> str:
        """Return an URL for the homepage of the plan.

        If `client_url` is given, try to return the URL that matches the supplied
        `client_url` the best:
          1. If `client_url` is from a wildcard domain, return the hostname that
             matches the wildcard (with matching protocol and port).
          2. Otherwise, see if the plan has a PlanDomain matching the hostname
             (possibly with a URL path prefix).
          3. If not, return the main URL.
        """
        port = hostname = scheme = None
        if client_url:
            parts = urlparse(client_url)
            hostname = parts.netloc.split(':')[0]
            scheme = parts.scheme
            if scheme not in ('https', 'http'):
                raise Exception('Invalid scheme in client_url')
            try:
                port = parts.port
                if scheme == 'https' and port == 443:
                    port = None
                elif scheme == 'http' and port == 80:
                    port = None
            except ValueError:
                port = None

        base_path = None
        if hostname:
            _, wildcard_hostname = get_plan_identifier_from_wildcard_domain(hostname)
            if wildcard_hostname:
                hostname = '%s.%s' % (self.identifier, wildcard_hostname)
                base_path = '/'
            else:
                domains = self.domains.all()
                for domain in domains:
                    if domain.hostname == hostname:
                        hostname = domain.hostname
                        base_path = domain.base_path or '/'
                        break
                else:
                    hostname = None

        locale_prefix = ''
        if active_locale:
            locale_prefix = self.get_optional_locale_prefix(active_locale)

        if hostname:
            if not scheme:
                scheme = 'https'
            if not base_path:
                base_path = ''
            else:
                base_path = base_path.rstrip('/')
            if port:
                port_str = ':%s' % port
            else:
                port_str = ''
            return '%s://%s%s%s%s' % (scheme, hostname, port_str, base_path, locale_prefix)
        else:
            assert self.site_url is not None
            if self.site_url.startswith('http'):
                url = self.site_url.rstrip('/')
            else:
                url = 'https://%s' % self.site_url
            return f'{url}{locale_prefix}'

    @classmethod
    def create_with_defaults(
        cls,
        identifier: str,
        name: str,
        primary_language: str,
        organization: Organization,
        other_languages: typing.List[str] = [],
        short_name: Optional[str] = None,
        base_path: Optional[str] = None,
        domain: Optional[str] = None,
        client_identifier: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> Plan:
        plan = Plan(
            identifier=identifier,
            name=name,
            primary_language=primary_language,
            organization=organization,
            other_languages=other_languages
        )
        if short_name:
            plan.short_name = short_name
        if client_name:
            from admin_site.models import Client, ClientPlan
            client = Client.objects.filter(name=client_name).first()
            if client is None:
                client = Client.objects.create(name=client_name)
            ClientPlan.objects.create(plan=plan, client=client)
        return cls.apply_defaults(plan, domain=domain, base_path=base_path)

    @classmethod
    @transaction.atomic()
    def apply_defaults(
            cls,
            plan: Plan,
            base_path: Optional[str] = None,
            domain: Optional[str] = None
    ):
        from ..defaults import (
            DEFAULT_ACTION_IMPLEMENTATION_PHASES, DEFAULT_ACTION_STATUSES
        )
        plan.statuses_updated_manually = True
        default_domains = [x for x in settings.HOSTNAME_PLAN_DOMAINS if x != 'localhost']
        if not domain:
            if not default_domains:
                raise Exception("site_url not provided and no default domains configured")
            domain = default_domains[0]
            site_url = 'https://%s.%s' % (plan.identifier, domain)
        else:
            site_url = 'https://%s' % domain
        if base_path:
            site_url += '/' + base_path.strip('/')
        plan.site_url = site_url
        plan.create_default_site()
        plan.save()

        with translation.override(plan.primary_language):
            from actions.models import ActionStatus, ActionImplementationPhase

            for st in DEFAULT_ACTION_STATUSES:
                status = ActionStatus(
                    plan=plan, identifier=st['identifier'], name=st['name'],
                    is_completed=st.get('is_completed', False)
                )
                status.save()

            for idx, st in enumerate(DEFAULT_ACTION_IMPLEMENTATION_PHASES):
                phase = ActionImplementationPhase(
                    plan=plan, order=idx, identifier=st['identifier'], name=st['name'],
                )
                phase.save()

        # Set up notifications
        management.call_command('initialize_notifications', plan=plan.identifier)
        return plan

    def get_all_related_plans(self, inclusive=False) -> PlanQuerySet:
        q = Q(related_plans=self)
        if self.parent_id:
            q |= Q(id=self.parent_id)
            q |= Q(parent=self.parent_id)

        q |= Q(parent_id=self.id)

        if not inclusive:
            q &= ~Q(id=self.id)
        else:
            q |= Q(id=self.id)

        qs: PlanQuerySet = Plan.objects.filter(q)

        return qs

    def get_superseded_plans(self, recursive=False):
        result = self.superseded_plans.all()
        if recursive:
            # To optimize, use recursive queries as in https://stackoverflow.com/a/39933958/14595546
            for child in list(result):
                result |= child.get_superseded_plans(recursive=True)
        return result

    def get_superseding_plans(self, recursive=False):
        if self.superseded_by is None:
            return []
        result = [self.superseded_by]
        if recursive:
            # To optimize, use recursive queries as in https://stackoverflow.com/a/39933958/14595546
            result += self.superseded_by.get_superseding_plans(recursive=True)
        return result

    def get_action_days_until_considered_stale(self):
        days = self.action_days_until_considered_stale
        return days if days is not None else self.DEFAULT_ACTION_DAYS_UNTIL_CONSIDERED_STALE

    @property
    def action_update_target_interval(self):
        days = self.settings_action_update_target_interval
        return days if days is not None else self.DEFAULT_ACTION_UPDATE_TARGET_INTERVAL

    @property
    def action_update_acceptable_interval(self):
        days = self.settings_action_update_acceptable_interval
        return days if days is not None else self.DEFAULT_ACTION_UPDATE_ACCEPTABLE_INTERVAL

    @property
    def tzinfo(self):
        return zoneinfo.ZoneInfo(self.timezone)

    def to_local_timezone(self, dt: datetime):
        return dt.astimezone(self.tzinfo)

    def now_in_local_timezone(self):
        return self.to_local_timezone(timezone.now())

    def should_trigger_daily_notifications(self, now=None):
        if now is None:
            now = self.now_in_local_timezone()
        if not self.notification_settings.notifications_enabled:
            return False
        if self.daily_notifications_triggered_at is None:
            should_send_at_or_after = datetime.combine(now.date(), self.notification_settings.send_at_time, self.tzinfo)
        else:
            last_sent_at = self.to_local_timezone(self.daily_notifications_triggered_at)
            should_send_at_or_after = datetime.combine(last_sent_at.date(), self.notification_settings.send_at_time, last_sent_at.tzinfo)
            if last_sent_at.time() >= self.notification_settings.send_at_time:
                should_send_at_or_after += timedelta(days=1)
        return now >= should_send_at_or_after

    def get_workflow_tasks(self):
        tasks = WorkflowTask.objects.filter(workflow=self.features.moderation_workflow)
        assert tasks.count() < 3, 'Currently max. 2 task workflows supported'
        return tasks

    def get_next_workflow_task(self, workflow_state: WorkflowStateEnum) -> WorkflowTask | None:
        """Returns the next workflow task that is active after the
        desired workflow_state has been reached. For example, in a workflow
        with an approval task (1) and after that a separate publishing task (2),
        for an action to be in a "APPROVED" state, task (2) must be the current
        active workflow state task for that action.

        (Once a task has been approved, it is no longer active in that workflow for that action.)

        Returns None if no task satisfies the condition and we should use
        the published action.

        """
        from aplans.graphql_types import WorkflowStateEnum
        tasks = self.get_workflow_tasks()
        if workflow_state == WorkflowStateEnum.PUBLISHED: return None
        if tasks.count() == 1:
            if workflow_state == WorkflowStateEnum.APPROVED: return None
            return tasks.get().task
        elif tasks.count() == 2:
            if workflow_state == WorkflowStateEnum.APPROVED: return tasks.last().task
            return None
        return None

    def has_indicator_relationships(self):
        visible_levels = IndicatorLevel.objects.filter(plan=self).visible_for_public()
        visible_indicators = Indicator.objects.filter(levels__in=visible_levels)
        return RelatedIndicator.objects.filter(Q(causal_indicator__in=visible_indicators) &
                                               Q(effect_indicator__in=visible_indicators)).exists()


class PublicationStatus(models.TextChoices):
    PUBLISHED = 'published', _('Published')
    UNPUBLISHED = 'unpublished', _('Unpublished')
    SCHEDULED = 'scheduled', _('Scheduled')

    @staticmethod
    def manual_status_choices():
        return [(c.value, c.label) for c in PublicationStatus if c != PublicationStatus.SCHEDULED]


# ParentalManyToManyField  won't help, so we need the through model:
# https://stackoverflow.com/questions/49522577/how-to-choose-a-wagtail-image-across-a-parentalmanytomanyfield
# Unfortunately the reverse accessors then point to instances of the through model, not the actual target.
class GeneralPlanAdmin(OrderedModel):
    plan = ParentalKey(Plan, on_delete=models.CASCADE, verbose_name=_('plan'), related_name='general_admins_ordered')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, verbose_name=_('person'),
                               related_name='general_admin_plans_ordered')

    class Meta:
        ordering = ['plan', 'order']
        indexes = [
            models.Index(fields=['plan', 'order']),
        ]
        unique_together = (('plan', 'person',),)
        verbose_name = _('general plan admin')
        verbose_name_plural = _('general plan admins')

    def save(self, *args, **kwargs):
        from notifications.models import GeneralPlanAdminNotificationPreferences
        result = super().save(*args, **kwargs)
        GeneralPlanAdminNotificationPreferences.objects.get_or_create(
            general_plan_admin=self,
        )
        return result

    def __str__(self):
        return str(self.person)


class PlanPublicSiteViewer(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, verbose_name=_('plan'), related_name='public_site_viewers')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, verbose_name=_('person'),
                               related_name='plans_with_public_site_access')

    class Meta:
        unique_together = (('plan', 'person',),)
        verbose_name = _('public site viewer')
        verbose_name_plural = _('public site viewers')

    def __str__(self):
        return str(self.person)


def is_valid_hostname(hostname):
    if len(hostname) > 255:
        return False
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


class PlanDomain(models.Model):
    """A domain (hostname) where an UI for a Plan might live."""
    class DeploymentEnvironment(models.TextChoices):
        PRODUCTION = 'production', _('Production')
        TESTING = 'testing', _('Testing')

    plan = ParentalKey(
        Plan, on_delete=models.CASCADE, related_name='domains', verbose_name=_('plan')
    )
    hostname = models.CharField(
        max_length=200, verbose_name=_('host name'), db_index=True,
        validators=[is_valid_hostname],
        help_text=_('The fully qualified domain name, eg. climate.cityname.gov. Leave blank if not yet known.')
    )
    base_path = models.CharField(
        max_length=200, verbose_name=_('base path'), null=True, blank=True,
        help_text=_('Fill this for a multi-plan site when the plan does not live in the root of the domain.'),
        validators=[RegexValidator(
            regex=r'^\/[a-z0-9_-]+',
            message=_("Base path must begin with a '/' and not end with '/'")
        )],
    )
    deployment_environment = models.CharField(
        max_length=30, choices=DeploymentEnvironment.choices, verbose_name=_('deployment environment'), blank=True,
    )
    redirect_aliases = ArrayField(
        models.CharField(max_length=80),
        blank=True,
        default=[],
        verbose_name='redirect aliases',
        help_text=_(
            "Domain names that will we used to redirect to the main hostname. Multiple domains are separated by commas."
        ),
    )
    google_site_verification_tag = models.CharField(max_length=50, null=True, blank=True)
    matomo_analytics_url = models.CharField(max_length=100, null=True, blank=True)

    # This field is intentionally left out from wagtail admin for now, because the majority of domains are production
    # domains and changing their publication status is dangerous without having confirmations in the form.
    publication_status_override = models.CharField(
        max_length=20,
        choices=PublicationStatus.manual_status_choices(),
        null=True,
        blank=True,
        default=None,
        verbose_name=_('Immediate override of publishing status'),
        help_text=_(
            'Only set this if you are sure you want to override the publication time set in the plan. '
            'Be aware that this will immediately change the publication status of the plan at this domain!'
        )
    )

    @property
    def status(self) -> PublicationStatus:
        if self.publication_status_override is not None:
            return PublicationStatus(self.publication_status_override)
        published_at = self.plan.published_at
        if published_at is None:
            return PublicationStatus.UNPUBLISHED
        now = self.plan.now_in_local_timezone()
        if published_at <= now:
            return PublicationStatus.PUBLISHED
        if published_at > now:
            return PublicationStatus.SCHEDULED
        return PublicationStatus.UNPUBLISHED

    @property
    def status_message(self) -> str | None:
        if self.status != PublicationStatus.PUBLISHED:
            with translation.override(self.plan.primary_language):
                return gettext('The site is not public at this time.')
        return None

    def validate_hostname(self):
        dn = self.hostname
        if not isinstance(dn, str):
            return False
        if not dn.islower():
            return False
        if dn.endswith('.'):
            dn = dn[:-1]
        if len(dn) < 1 or len(dn) > 253:
            return False
        ldh_re = re.compile('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$',
                            re.IGNORECASE)
        return all(ldh_re.match(x) for x in dn.split('.'))

    def clean(self):
        if not self.validate_hostname():
            raise ValidationError({'hostname': _('Hostname must be a fully qualified domain name in lower-case only')})

    def __str__(self):
        s = str(self.hostname)
        if self.base_path:
            s += ':' + self.base_path
        return s

    class Meta:
        verbose_name = _('plan domain')
        verbose_name_plural = _('plan domains')
        unique_together = (('hostname', 'base_path'),)


class Scenario(models.Model, PlanRelatedModel):
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name='scenarios',
        verbose_name=_('plan')
    )
    name = models.CharField(max_length=100, verbose_name=_('name'))
    identifier = IdentifierField()
    description = models.TextField(null=True, blank=True, verbose_name=_('description'))

    public_fields: ClassVar = [
        'id', 'plan', 'name', 'identifier', 'description',
    ]

    class Meta:
        unique_together = (('plan', 'identifier'),)
        verbose_name = _('scenario')
        verbose_name_plural = _('scenarios')

    def __str__(self):
        return self.name


class ImpactGroup(models.Model, PlanRelatedModel):
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name='impact_groups',
        verbose_name=_('plan')
    )
    name = models.CharField(verbose_name=_('name'), max_length=200)
    identifier = IdentifierField()
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, related_name='children', null=True, blank=True,
        verbose_name=pgettext_lazy('impact group', 'parent')
    )
    weight = models.FloatField(verbose_name=_('weight'), null=True, blank=True)
    color = models.CharField(
        max_length=16, verbose_name=_('color'), null=True, blank=True,
        validators=[validate_css_color]
    )

    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'identifier', 'parent', 'weight', 'name', 'color', 'actions',
    ]

    class Meta:
        unique_together = (('plan', 'identifier'),)
        verbose_name = _('impact group')
        verbose_name_plural = _('impact groups')
        ordering = ('plan', '-weight')

    def __str__(self):
        return self.name


class MonitoringQualityPoint(PlanRelatedModel, OrderedModel):  # type: ignore[django-manager-missing]
    name = models.CharField(max_length=100, verbose_name=_('name'))
    description_yes = models.CharField(
        max_length=200,
        verbose_name=_("description when action fulfills criteria")
    )
    description_no = models.CharField(
        max_length=200,
        verbose_name=_("description when action doesn\'t fulfill criteria")
    )

    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name='monitoring_quality_points',
        verbose_name=_('plan')
    )
    identifier = IdentifierField()

    i18n = TranslationField(
        fields=('name', 'description_yes', 'description_no'),
        default_language_field='plan__primary_language_lowercase',
    )

    public_fields: typing.ClassVar = [
        'id', 'name', 'description_yes', 'description_no', 'plan', 'identifier',
    ]

    class Meta:
        verbose_name = _('monitoring quality point')
        verbose_name_plural = _('monitoring quality points')
        unique_together = (('plan', 'order'),)
        ordering = ('plan', 'order')

    def __str__(self):
        return self.name
