from __future__ import annotations

from functools import cache
import logging
import reversion
import typing
from typing import TYPE_CHECKING, ClassVar, Iterable, Literal, Optional, Protocol, Self, TypedDict
import uuid

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin import display
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models import IntegerField, Max, Q
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel, model_from_serializable_data
from modeltrans.fields import TranslationField, TranslatedVirtualField
from modeltrans.translator import get_i18n_field
from reversion.models import Version
from wagtail.fields import RichTextField
from wagtail.models import DraftStateMixin, LockableMixin, RevisionMixin, Task, WorkflowMixin
from wagtail.search import index
from wagtail.search.queryset import SearchableQuerySetMixin


from aplans.types import UserOrAnon
from aplans.utils import (
    IdentifierField, OrderedModel, PlanRelatedModel, generate_identifier, get_available_variants_for_language,
    ConstantMetadata, DateFormatField
)
from orgs.models import Organization
from users.models import User
from search.backends import TranslatedSearchField, TranslatedAutocompleteField

from ..action_status_summary import ActionStatusSummaryIdentifier, ActionTimelinessIdentifier, SummaryContext
from ..attributes import AttributeFieldPanel, AttributeType
from ..monitoring_quality import determine_monitoring_quality
from .attributes import AttributeType as AttributeTypeModel, ModelWithAttributes

if typing.TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from django.db.models.expressions import Combinable
    from actions.attributes import DraftAttributes
    from aplans.cache import WatchObjectCache
    from people.models import Person
    from .plan import Plan
    from .action_deps import ActionDependencyRelationshipQuerySet


logger = logging.getLogger(__name__)


class ActionQuerySet(SearchableQuerySetMixin, models.QuerySet):
    def modifiable_by(self, user: User) -> Self:
        if user.is_superuser:
            return self
        person = user.get_corresponding_person()
        query = Q(responsible_parties__organization__in=user.get_adminable_organizations())
        if person:
            query |= Q(plan__in=person.general_admin_plans.all())
            query |= Q(contact_persons__person=person)
        return self.filter(query).distinct()

    def user_is_contact_for(self, user: User):
        person = user.get_corresponding_person()
        if person is None:
            return self.none()
        qs = self.filter(Q(contact_persons__person=person)).distinct()
        return qs

    def user_is_org_admin_for(self, user: User, plan: Optional[Plan] = None):
        plan_admin_orgs = Organization.objects.user_is_plan_admin_for(user, plan)
        query = Q(responsible_parties__organization__in=plan_admin_orgs) | Q(primary_org__in=plan_admin_orgs)
        return self.filter(query).distinct()

    def user_has_staff_role_for(self, user: User, plan: Optional[Plan] = None):
        qs = self.user_is_contact_for(user) | self.user_is_org_admin_for(user, plan)
        return qs

    def unmerged(self) -> Self:
        return self.filter(merged_with__isnull=True)

    def active(self) -> Self:
        return self.unmerged().exclude(status__is_completed=True)

    def visible_for_user(self, user: UserOrAnon | None, plan: Plan | None = None) -> Self:
        """ A None value is interpreted identically a non-authenticated user"""
        if user is None or not user.is_authenticated:
            return self.filter(visibility=RestrictedVisibilityModel.VisibilityState.PUBLIC)
        return self

    def visible_for_public(self) -> Self:
        return self.visible_for_user(None)

    def complete_for_report(self, report):
        from reports.models import ActionSnapshot
        action_ids = (
            ActionSnapshot.objects.filter(report=report)
            .annotate(action_id=Cast('action_version__object_id', output_field=IntegerField()))
            .values_list('action_id')
        )
        return self.filter(id__in=action_ids)


class HasGetValue(Protocol):
    def get_value(self, obj: Action): ...


class ActionIdentifierSearchMixin(HasGetValue):
    def get_value(self, obj: Action):
        # If the plan doesn't have meaningful action identifiers,
        # do not index them.
        if not obj.plan.features.has_action_identifiers:
            return None
        return super().get_value(obj)


class ActionIdentifierSearchField(ActionIdentifierSearchMixin, index.SearchField):
    pass


class ActionIdentifierAutocompleteField(ActionIdentifierSearchMixin, index.AutocompleteField):
    pass


class ResponsiblePartyDict(TypedDict):
    organization: Organization
    # Allowed roles in ActionResponsibleParty.Role.values
    # https://stackoverflow.com/a/67292548/14595546
    role: Literal['primary', 'collaborator', None]


class RestrictedVisibilityModel(models.Model):
    class VisibilityState(models.TextChoices):
        INTERNAL = 'internal', _('Internal')
        PUBLIC = 'public', _('Public')

    visibility = models.CharField(
        blank=False, null=False,
        default=VisibilityState.PUBLIC,
        choices=VisibilityState.choices,
        max_length=20,
        verbose_name=_('visibility'),
    )

    class Meta:
        abstract = True


if TYPE_CHECKING:
    class ActionManager(models.Manager['Action']):
        def get_queryset(self) -> ActionQuerySet: ...
else:
    ActionManager = models.Manager.from_queryset(ActionQuerySet)


@reversion.register(follow=ModelWithAttributes.REVERSION_FOLLOW + ['responsible_parties', 'tasks'])
class Action(  # type: ignore[django-manager-missing]
    WorkflowMixin, DraftStateMixin, LockableMixin, RevisionMixin,
    ModelWithAttributes, PlanRelatedModel, OrderedModel, ClusterableModel, RestrictedVisibilityModel, index.Indexed
):
    """One action/measure tracked in an action plan."""

    def revision_enabled(self):
        return self.plan.features.enable_moderation_workflow

    def save_revision(self, *args, **kwargs):
        # This method has been overridden temporarily.
        #
        # The reason is that for plans without the moderation workflow enabled, RevisionMixin.save_revision is still called for all
        # subclasses of RevisionMixin.
        #
        # This results in newly created actions to have has_unpublished_changes == True and a revision to be created for them. This in turn
        # results in the action edit form not showing the actual saved action data but the data of a "draft" revision (which itself cannot
        # be edited in a plan with workflows disabled currently).
        #
        # In the future we will probably want to have drafting enabled by default for all plans and we can remove this.
        if not self.revision_enabled():
            return None
        return super().save_revision(*args, **kwargs)

    def commit_attributes(self, attributes: dict[str, typing.Any], user):
        """Called when the serialized draft contents of attribute values must be persisted to the actual Attribute models
        when publishing an action from a draft"""
        from actions.attributes import DraftAttributes
        draft_attributes = DraftAttributes.from_revision_content(attributes)
        attribute_types = self.get_editable_attribute_types(user)
        for attribute_type in attribute_types:
            try:
                attribute_value = draft_attributes.get_value_for_attribute_type(attribute_type)
            except KeyError:
                pass
            else:
                attribute_type.commit_attribute(self, attribute_value)

    def publish(self, revision, user=None, **kwargs):
        attributes = revision.content.pop('attributes')
        super().publish(revision, user=user, **kwargs)
        self.commit_attributes(attributes, user)

    def serializable_data(self, *args, **kwargs):
        # Do not serialize translated virtual fields
        i18n_field = get_i18n_field(self)
        assert i18n_field
        for field in i18n_field.get_translated_fields():
            assert field.serialize is True
            field.serialize = False
        try:
            result = super().serializable_data(*args, **kwargs)
            if self.draft_attributes is None:
                # This is a newly created action
                attributes = {}
            else:
                attributes = self.draft_attributes.get_serialized_data()
            result['attributes'] = attributes
            return result
        finally:
            for field in i18n_field.get_translated_fields():
                field.serialize = True

    id: int
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    plan: ParentalKey[Plan | Combinable, Plan] = ParentalKey(
        'actions.Plan', on_delete=models.CASCADE, related_name='actions',
        verbose_name=_('plan')
    )
    primary_org = models.ForeignKey(
        'orgs.Organization', verbose_name=_('primary organization'),
        blank=True, null=True, on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=1000, verbose_name=_('name'))
    official_name = models.TextField(
        null=True, blank=True, verbose_name=_('official name'),
        help_text=_('The name as approved by an official party')
    )
    identifier = IdentifierField(
        help_text=_('The identifier for this action (e.g. number)')
    )
    image = models.ForeignKey(
        'images.AplansImage', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name=_('Image')
    )
    lead_paragraph = models.TextField(blank=True, verbose_name=_('Lead paragraph'))
    description = RichTextField(
        null=True, blank=True,
        verbose_name=_('description'),
        help_text=_('What does this action involve in more detail?'))
    impact = models.ForeignKey(
        'ActionImpact', blank=True, null=True, related_name='actions', on_delete=models.SET_NULL,
        verbose_name=_('impact'), help_text=_('The impact of this action'),
    )
    internal_priority = models.PositiveIntegerField(
        blank=True, null=True, verbose_name=_('internal priority')
    )
    internal_admin_notes = models.TextField(
        blank=True, null=True, verbose_name=_('internal notes for plan administrators')
    )
    internal_notes = models.TextField(
        blank=True, null=True, verbose_name=_('internal notes')
    )
    status = models.ForeignKey(
        'ActionStatus', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('status'),
    )
    implementation_phase = models.ForeignKey(
        'ActionImplementationPhase', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('implementation phase'),
    )
    manual_status = models.BooleanField(
        default=False, verbose_name=_('override status manually'),
        help_text=_('Set if you want to prevent the action status from being determined automatically')
    )
    manual_status_reason = models.TextField(
        blank=True, null=True, verbose_name=_('specifier for status'),
        help_text=_('Describe the reason why this action has has this status')
    )

    merged_with = models.ForeignKey(
        'Action', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('merged with action'), help_text=_('Set if this action is merged with another action'),
        related_name='merged_actions'
    )
    completion = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_('completion'), editable=False,
        help_text=_('The completion percentage for this action')
    )
    schedule = models.ManyToManyField(
        'ActionSchedule', blank=True, verbose_name=_('schedule')
    )
    schedule_continuous = models.BooleanField(
        default=False, verbose_name=_('continuous action'),
        help_text=_('Set if the action does not have a start or an end date')
    )
    decision_level = models.ForeignKey(
        'ActionDecisionLevel', blank=True, null=True, related_name='actions', on_delete=models.SET_NULL,
        verbose_name=_('decision-making level')
    )
    categories = models.ManyToManyField(
        'Category', blank=True, verbose_name=_('categories'), related_name='actions',
    )
    indicators = models.ManyToManyField(
        'indicators.Indicator', blank=True, verbose_name=_('indicators'),
        through='indicators.ActionIndicator', related_name='actions'
    )
    related_actions = models.ManyToManyField('self', blank=True, verbose_name=_('related actions'))

    responsible_organizations = models.ManyToManyField(
        Organization, through='ActionResponsibleParty', blank=True,
        related_name='responsible_for_actions', verbose_name=_('responsible organizations')
    )

    contact_persons_unordered = models.ManyToManyField(
        'people.Person', through='ActionContactPerson', blank=True,
        related_name='contact_for_actions', verbose_name=_('contact persons')
    )

    monitoring_quality_points = models.ManyToManyField(
        'MonitoringQualityPoint', blank=True, related_name='actions',
        editable=False,
    )

    updated_at = models.DateTimeField(
        editable=False, verbose_name=_('updated at'), default=timezone.now
    )
    start_date = models.DateField(
        verbose_name=_('start date'),
        help_text=_('The date when implementation of this action starts'),
        blank=True,
        null=True,
    )
    end_date = models.DateField(
        verbose_name=_('end date'),
        help_text=_('The date when implementation of this action ends'),
        blank=True,
        null=True,
    )
    date_format = DateFormatField(
        verbose_name=_('Date format'),
        help_text=_(
            'Format of action start and end dates shown in the public UI. \
            The default for all actions can be specified on the actions page.'
        ),
        blank=True,
        null=True,
        default=None
    )
    superseded_by = models.ForeignKey(
        'self', verbose_name=pgettext_lazy('action', 'superseded by'), blank=True, null=True, on_delete=models.SET_NULL,
        related_name='superseded_actions', help_text=_('Set if this action is superseded by another action')
    )
    dependency_role = models.ForeignKey(
        'ActionDependencyRole', on_delete=models.SET_NULL, null=True, blank=True, related_name='actions',
        verbose_name=_('Role in dependencies'),
        help_text=_('Set if this action has the same role in all its dependency relationships with other actions'),
    )

    sent_notifications = GenericRelation('notifications.SentNotification', related_query_name='action')

    i18n = TranslationField(
        fields=('name', 'official_name', 'description', 'manual_status_reason', 'lead_paragraph'),
        default_language_field='plan__primary_language_lowercase',
    )

    # Add reverse GenericRelation to add the ability to prefetch the related workflowstates
    # to optimize the performance of querying actions in GQL.
    # See ActionNode.resolve_workflow_status and its prefetch_related hint
    _workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="action",
        for_concrete_model=False,
    )

    objects: ActionManager = ActionManager()

    search_fields = [
        TranslatedSearchField('name', boost=10),
        TranslatedAutocompleteField('name'),
        ActionIdentifierSearchField('identifier', boost=10),
        ActionIdentifierAutocompleteField('identifier'),
        TranslatedSearchField('official_name', boost=8),
        TranslatedAutocompleteField('official_name'),
        TranslatedSearchField('description'),
        index.RelatedFields('tasks', [
            TranslatedSearchField('name'),
            TranslatedSearchField('comment'),
        ]),
        index.FilterField('plan'),
        index.FilterField('updated_at'),
        index.FilterField('visibility'),
    ]
    search_auto_update = True

    # Used by GraphQL + REST API code
    public_fields = [
        'id', 'uuid', 'plan', 'name', 'official_name', 'identifier', 'lead_paragraph', 'description', 'status',
        'completion', 'schedule', 'schedule_continuous', 'decision_level', 'responsible_parties',
        'categories', 'indicators', 'contact_persons', 'updated_at', 'start_date', 'end_date', 'date_format', 'tasks',
        'related_actions', 'related_indicators', 'impact', 'status_updates', 'merged_with', 'merged_actions',
        'impact_groups', 'monitoring_quality_points', 'implementation_phase', 'manual_status_reason', 'links',
        'primary_org', 'order', 'superseded_by', 'superseded_actions', 'dependent_relationships', 'dependency_role',
    ]

    # type annotations for related objects
    contact_persons: RelatedManager[ActionContactPerson]
    merged_actions: RelatedManager[Action]
    superseded_actions: RelatedManager[Action]
    tasks: RelatedManager[ActionTask]
    dependent_relationships: RelatedManager['ActionDependencyRelationship']
    preceding_relationships: RelatedManager['ActionDependencyRelationship']

    verbose_name_partitive = pgettext_lazy('partitive', 'action')

    class Meta:
        verbose_name = _('action')
        verbose_name_plural = _('actions')
        ordering = ('plan', 'order')
        indexes = [
            models.Index(fields=['plan', 'order']),
        ]
        unique_together = (('plan', 'identifier'),)
        permissions = (
            ('admin_action', _("Can administrate all actions")),
        )

    MODEL_ADMIN_CLASS = 'actions.action_admin.ActionAdmin'  # for AdminButtonsMixin

    def __str__(self):
        s = ''
        if self.plan is not None and self.plan.features.has_action_identifiers:
            s += '%s. ' % self.identifier
        s += self.name_i18n
        return s

    def clean(self):
        if self.merged_with is not None:
            other = self.merged_with
            if other.merged_with == self:
                raise ValidationError({'merged_with': _('Other action is merged with this one')})
        # FIXME: Make sure FKs and M2Ms point to objects that are within the
        # same action plan.

    def save(self, *args, **kwargs):
        if self.pk is None:
            qs = self.plan.actions.values('order').order_by()
            max_order = qs.aggregate(Max('order'))['order__max']
            if max_order is None:
                self.order = 0
            else:
                self.order = max_order + 1
        # Invalidate the plan's action cache because, e.g., we might have changed the order
        try:
            del self.plan.cached_actions
        except AttributeError:
            pass
        return super().save(*args, **kwargs)

    def is_merged(self):
        return self.merged_with_id is not None

    def is_active(self):
        return not self.is_merged() and (self.status is None or not self.status.is_completed)

    def get_next_action(self, user: User):
        return (
            Action.objects.get_queryset()
            .visible_for_user(user)
            .filter(plan=self.plan_id, order__gt=self.order)
            .unmerged()
            .first()
        )

    def get_previous_action(self, user: User) -> Action | None:
        return (
            Action.objects.get_queryset()
            .visible_for_user(user)
            .filter(plan=self.plan_id, order__lt=self.order)
            .unmerged()
            .order_by('-order')
            .first()
        )

    @property
    def visibility_display(self):
        return self.get_visibility_display()


    def _calculate_status_from_indicators(self):
        progress_indicators = self.related_indicators.filter(indicates_action_progress=True)
        total_completion = 0.0
        total_indicators = 0
        is_late = False

        for action_ind in progress_indicators:
            ind = action_ind.indicator
            try:
                latest_value = ind.values.latest()
            except ind.values.model.DoesNotExist:
                continue

            start_value = ind.values.first()
            assert start_value is not None

            try:
                last_goal = ind.goals.latest()
            except ind.goals.model.DoesNotExist:
                continue

            diff = last_goal.value - start_value.value

            if not diff:
                # Avoid divide by zero
                continue

            completion = (latest_value.value - start_value.value) / diff
            total_completion += completion
            total_indicators += 1

            # Figure out if the action is late or not by comparing
            # the latest measured value to the closest goal
            closest_goal = ind.goals.filter(date__lte=latest_value.date).last()
            if closest_goal is None:
                continue

            # Are we supposed to up or down?
            if diff > 0:
                # Up!
                if closest_goal.value - latest_value.value > 0:
                    is_late = True
            else:
                # Down
                if closest_goal.value - latest_value.value < 0:
                    is_late = True

        if not total_indicators:
            return None

        # Return average completion
        completion = int((total_completion / total_indicators) * 100)
        if completion <= 0:
            return None
        return dict(completion=completion, is_late=is_late)

    def _calculate_completion_from_tasks(self, tasks):
        if not tasks:
            return None
        n_completed = len(list(filter(lambda x: x.completed_at is not None, tasks)))
        return dict(completion=int(n_completed * 100 / len(tasks)))

    def _determine_status(self, tasks, indicator_status, today=None):
        if today is None:
            today = self.plan.now_in_local_timezone().date()

        statuses = self.plan.action_statuses.all()
        if not statuses:
            return None

        by_id = {x.identifier: x for x in statuses}
        KNOWN_IDS = {'not_started', 'on_time', 'late'}
        # If the status set is not something we can handle, bail out.
        if not KNOWN_IDS.issubset(set(by_id.keys())):
            logger.warning(
                'Unable to determine action statuses for plan %s: '
                'right statuses missing' % self.plan.identifier
            )
            return None

        if indicator_status is not None and indicator_status.get('is_late'):
            return by_id['late']

        def is_late(task):
            if task.due_at is None or task.completed_at is not None:
                return False
            return today > task.due_at

        late_tasks = list(filter(is_late, tasks))
        if not late_tasks:
            completed_tasks = list(filter(lambda x: x.completed_at is not None, tasks))
            if not completed_tasks:
                return by_id['not_started']
            else:
                return by_id['on_time']

        return by_id['late']

    def recalculate_status(self, force_update=False):
        if self.merged_with is not None or self.manual_status:
            return

        if self.status is not None and self.status.is_completed:
            if self.status.identifier == 'completed' and self.completion != 100:
                self.completion = 100
                self.save(update_fields=['completion'])
            return

        determine_monitoring_quality(self, self.plan.monitoring_quality_points.all())

        indicator_status = self._calculate_status_from_indicators()
        if indicator_status:
            new_completion = indicator_status['completion']
        else:
            new_completion = None

        if self.completion != new_completion or force_update:
            self.completion = new_completion
            self.updated_at = timezone.now()
            self.save(update_fields=['completion', 'updated_at'])

        if self.plan.statuses_updated_manually:
            return

        tasks = self.tasks.exclude(state=ActionTask.CANCELLED).only('due_at', 'completed_at')
        status = self._determine_status(tasks, indicator_status)
        if status is not None and status.id != self.status_id:
            self.status = status
            self.save(update_fields=['status'])

    def handle_admin_save(self, context: Optional[dict] = None):
        self.recalculate_status(force_update=True)

    def set_categories(self, type, categories):
        if isinstance(type, str):
            type = self.plan.category_types.get(identifier=type)
        all_cats = {x.id: x for x in type.categories.all()}

        existing_cats = set(self.categories.filter(type=type))
        new_cats = set()
        for cat in categories:
            if isinstance(cat, int):
                cat = all_cats[cat]
            new_cats.add(cat)

        for cat in existing_cats - new_cats:
            self.categories.remove(cat)
        for cat in new_cats - existing_cats:
            self.categories.add(cat)

    def set_responsible_parties(self, data: list[ResponsiblePartyDict]):
        existing_orgs = set((p.organization for p in self.responsible_parties.all()))
        new_orgs = set(d['organization'] for d in data)
        ActionResponsibleParty.objects.filter(
            action=self, organization__in=(existing_orgs - new_orgs)
        ).delete()
        for d in data:
            ActionResponsibleParty.objects.update_or_create(
                action=self,
                organization=d['organization'],
                defaults={'role': d['role']},
            )

    def set_contact_persons(self, data: list):
        existing_persons = set((p.person for p in self.contact_persons.all()))
        new_persons = set(d['person'] for d in data)
        ActionContactPerson.objects.filter(
            action=self, person__in=(existing_persons - new_persons)
        ).delete()
        for d in data:
            ActionContactPerson.objects.update_or_create(
                action=self,
                person=d['person'],
                defaults={'role': d['role']},
            )

    def generate_identifier(self):
        self.identifier = generate_identifier(self.plan.actions.all(), 'a', 'identifier')

    def get_notification_context(self, plan=None):
        if plan is None:
            plan = self.plan
        change_url = reverse('actions_action_modeladmin_edit', kwargs=dict(instance_pk=self.id))
        return {
            'id': self.id, 'identifier': self.identifier, 'name': self.name, 'change_url': change_url,
            'updated_at': self.updated_at, 'view_url': self.get_view_url(plan=plan), 'order': self.order,
        }

    @display(boolean=True, description=_('Has contact persons'))
    def has_contact_persons(self):
        return self.contact_persons.exists()

    @display(description=_('Active tasks'))
    def active_task_count(self):
        def task_active(task):
            return task.state != ActionTask.CANCELLED and not task.completed_at

        active_tasks = [task for task in self.tasks.all() if task_active(task)]
        return len(active_tasks)

    def get_view_url(self, plan: Optional[Plan] = None, client_url: Optional[str] = None) -> str:
        if plan is None:
            plan = self.plan
        return '%s/actions/%s' % (plan.get_view_url(client_url=client_url, active_locale=translation.get_language()), self.identifier)

    @classmethod
    def get_indexed_objects(cls):
        # Return only the actions whose plan supports the current language
        lang = translation.get_language()

        qs = super().get_indexed_objects()
        lang_variants = get_available_variants_for_language(lang)
        q = Q(plan__primary_language__startswith=lang)
        for variant in lang_variants:
            q |= Q(plan__other_languages__contains=[variant])
        qs = qs.filter(q)
        # FIXME find out how to use action default manager here
        qs = qs.filter(visibility=RestrictedVisibilityModel.VisibilityState.PUBLIC)
        return qs

    def get_editable_attribute_types(
        self, user: UserOrAnon, only_in_reporting_tab: bool = False, unless_in_reporting_tab: bool = False
    ) -> list[AttributeType]:
        attribute_types = self.__class__.get_attribute_types_for_plan(
            self.plan,
            only_in_reporting_tab=only_in_reporting_tab,
            unless_in_reporting_tab=unless_in_reporting_tab
        )
        return [at for at in attribute_types if at.instance.is_instance_editable_by(user, self.plan, self)]

    def get_visible_attribute_types(
        self, user: UserOrAnon, only_in_reporting_tab: bool = False, unless_in_reporting_tab: bool = False
    ) -> list[AttributeType]:
        attribute_types = self.__class__.get_attribute_types_for_plan(
            self.plan,
            only_in_reporting_tab=only_in_reporting_tab,
            unless_in_reporting_tab=unless_in_reporting_tab
        )
        return [at for at in attribute_types if at.instance.is_instance_visible_for(user, self.plan, self)]

    @classmethod
    @cache
    def get_attribute_types_for_plan(cls, plan: Plan, only_in_reporting_tab=False, unless_in_reporting_tab=False):
        action_ct = ContentType.objects.get_for_model(Action)
        plan_ct = ContentType.objects.get_for_model(plan)
        at_qs: Iterable[AttributeTypeModel] = AttributeTypeModel.objects.filter(
            object_content_type=action_ct,
            scope_content_type=plan_ct,
            scope_id=plan.id,
        )
        if only_in_reporting_tab:
            at_qs = at_qs.filter(show_in_reporting_tab=True)
        if unless_in_reporting_tab:
            at_qs = at_qs.filter(show_in_reporting_tab=False)
        # Convert to wrapper objects
        return [AttributeType.from_model_instance(at) for at in at_qs]

    def get_attribute_panels(self, user: User, draft_attributes: DraftAttributes | None = None):
        # Return a triple `(main_panels, reporting_panels, i18n_panels)`, where `main_panels` is a list of panels to be
        # put on the main tab, `reporting_panels` is a list of panels to be put on the reporting tab, and `i18n_panels`
        # is a dict mapping a non-primary language to a list of panels to be put on the tab for that language.
        main_panels: list[AttributeFieldPanel] = []
        reporting_panels: list[AttributeFieldPanel] = []
        i18n_panels: dict[str, list[AttributeFieldPanel]] = {}
        plan = user.get_active_admin_plan()  # not sure if this is reasonable...
        for panels, kwargs in [(main_panels, {'unless_in_reporting_tab': True}),
                               (reporting_panels, {'only_in_reporting_tab': True})]:
            attribute_types = self.get_visible_attribute_types(user, **kwargs)
            for attribute_type in attribute_types:
                fields = attribute_type.get_form_fields(user, plan, self, draft_attributes=draft_attributes)
                for field in fields:
                    if field.language:
                        i18n_panels.setdefault(field.language, []).append(field.get_panel())
                    else:
                        panels.append(field.get_panel())
        return (main_panels, reporting_panels, i18n_panels)

    def get_siblings(self, force_refresh=False):
        if force_refresh:
            del self.plan.cached_actions
        return self.plan.cached_actions

    def get_prev_sibling(self):
        all_actions = self.plan.cached_actions
        for i, sibling in enumerate(all_actions):
            if sibling.id == self.id:
                if i == 0:
                    return None
                return all_actions[i - 1]
        assert False  # should have returned above at some point

    def get_snapshots(self, report=None):
        """Return the snapshots of this action, optionally restricted to those for the given report."""
        from reports.models import ActionSnapshot
        versions = Version.objects.get_for_object(self)
        qs = ActionSnapshot.objects.filter(action_version__in=versions)
        if report is not None:
            qs = qs.filter(report=report)
        return qs

    def get_latest_snapshot(self, report=None):
        """Return the latest snapshot of this action, optionally restricted to those for the given report.

        Raises ActionSnapshot.DoesNotExist if no such snapshot exists.
        """
        return self.get_snapshots(report).latest()

    def is_complete_for_report(self, report):
        from reports.models import ActionSnapshot
        try:
            self.get_latest_snapshot(report)
        except ActionSnapshot.DoesNotExist:
            return False
        return True

    def mark_as_complete_for_report(self, report, user):
        from reports.models import ActionSnapshot
        if self.is_complete_for_report(report):
            raise ValueError(_("The action is already marked as complete for report %s.") % report)
        with reversion.create_revision():
            reversion.add_to_revision(self)
            reversion.set_comment(
                _("Marked action '%(action)s' as complete for report '%(report)s'") % {
                    'action': self, 'report': report})
            reversion.set_user(user)
        ActionSnapshot.for_action(
            report=report,
            action=self,
        ).save()

    def undo_marking_as_complete_for_report(self, report, user):
        from reports.models import ActionSnapshot
        snapshots = ActionSnapshot.objects.filter(
            report=report,
            action_version__in=Version.objects.get_for_object(self),
        )
        num_snapshots = snapshots.count()
        if num_snapshots != 1:
            raise ValueError(_("Cannot undo marking action as complete as there are %s snapshots") % num_snapshots)
        with reversion.create_revision():
            reversion.add_to_revision(self)
            reversion.set_comment(
                _("Undid marking action '%(action)s' as complete for report '%(report)s'") % {
                    'action': self, 'report': report})
            reversion.set_user(user)
        snapshots.delete()

    def get_status_summary(
            self, cache: WatchObjectCache | None = None
    ) -> ConstantMetadata['ActionStatusSummaryIdentifier', SummaryContext]:
        return ActionStatusSummaryIdentifier.for_action(self).get_data({'plan_id': self.plan_id, 'cache': cache})

    def get_timeliness(self, cache: WatchObjectCache | None = None):
        return ActionTimelinessIdentifier.for_action(self).get_data({'plan': self.plan, 'cache': cache})

    def get_color(self, cache: WatchObjectCache | None = None):
        if self.status and self.status.color:
            return self.status.color
        if self.implementation_phase and self.implementation_phase.color:
            return self.implementation_phase.color
        # No plan context needed just to get the color
        summary = ActionStatusSummaryIdentifier.for_action(self)
        return summary.value.color

    def get_workflow(self):
        return self.plan.features.moderation_workflow

    def get_dependency_relationships(self, user: UserOrAnon | None, plan: Plan | None) -> ActionDependencyRelationshipQuerySet:
        from .action_deps import ActionDependencyRelationship
        return ActionDependencyRelationship.objects.all_for_action(self).visible_for_user(user, plan)


class ModelWithRole:
    class Role(models.TextChoices):
        # If your model allows blank values for the role field, specify it using `__empty__ = _("Text")`, but bear in
        # mind that this won't be included when you iterate over the enum.
        pass

    @classmethod
    def get_roles(cls) -> typing.Iterable[ModelWithRole.Role | None]:
        roles: list[ModelWithRole.Role | None] = list(cls.Role)
        if cls.role.field.blank:
            # None is not part of list(cls.Role) even if it's an allowed value in the DB field
            roles.append(None)
        return roles

    @classmethod
    def get_roles_editable_in_action_by(cls, action: Action, person: Person) -> typing.Iterable[ModelWithRole.Role | None]:
        raise NotImplementedError


@reversion.register()
class ActionResponsibleParty(OrderedModel, ModelWithRole):
    class Role(ModelWithRole.Role):
        PRIMARY = 'primary', _('Primary responsible party')
        COLLABORATOR = 'collaborator', _('Collaborator')
        __empty__ = _('Unspecified')

    action = ParentalKey(
        Action, on_delete=models.CASCADE, related_name='responsible_parties',
        verbose_name=_('action')
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='responsible_actions', verbose_name=_('organization'),
        # FIXME: The following leads to a weird error in the action edit page, but only if Organization.i18n is there.
        # WTF? Commented out for now.
        # limit_choices_to=Q(dissolution_date=None),
    )
    role = models.CharField(max_length=40, choices=Role.choices, blank=True, null=True, verbose_name=_('role'))
    specifier = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('specifier'),
        help_text=_('The responsibility domain for the organization'),
    )

    public_fields: ClassVar = [
        'id', 'action', 'organization', 'role', 'specifier', 'order',
    ]

    class Meta:
        ordering = ['action', 'order']
        indexes = [
            models.Index(fields=['action', 'order']),
        ]
        unique_together = (('action', 'organization'),)
        verbose_name = _('action responsible party')
        verbose_name_plural = _('action responsible parties')

    def get_label(self):
        label = ''
        if self.role:
            label += self.get_role_display()
        if self.specifier:
            label += f' ({self.specifier})'
        return label

    def get_value(self):
        return self.organization.name

    def __str__(self):
        return str(self.organization)

    @classmethod
    def get_roles_editable_in_action_by(cls, action: Action, person: Person) -> typing.Iterable[ModelWithRole.Role | None]:
        is_contact_person = person is not None and action.contact_persons.filter(
            person_id=person.pk,
        ).exists()
        if is_contact_person:
            return [
                ActionResponsibleParty.Role.COLLABORATOR,
                None,  # for responsible parties with unspecified role
            ]
        return []


class ActionContactPerson(OrderedModel, ModelWithRole):
    """A Person acting as a contact for an action"""
    class Role(ModelWithRole.Role):
        EDITOR = 'editor', _('Editor')
        MODERATOR = 'moderator', _('Moderator')

    role = models.CharField(max_length=40, choices=Role.choices, default='moderator', blank=False, null=False, verbose_name=_('role'))

    action = ParentalKey(
        Action, on_delete=models.CASCADE, verbose_name=_('action'), related_name='contact_persons'
    )
    person: models.ForeignKey[Person | Combinable, Person] = models.ForeignKey(
        'people.Person', on_delete=models.CASCADE, verbose_name=_('person')
    )
    primary_contact = models.BooleanField(
        default=False,
        verbose_name=_('primary contact person'),
        help_text=_('Is this person the primary contact person for the action?'),
    )

    public_fields: ClassVar = [
        'id', 'action', 'person', 'order', 'primary_contact', 'role',
    ]

    class Meta:
        ordering = ['action', 'order']
        indexes = [
            models.Index(fields=['action', 'order']),
        ]
        unique_together = (('action', 'person',),)
        verbose_name = _('action contact person')
        verbose_name_plural = _('action contact persons')

    def __str__(self):
        return f'{str(self.person)}: {str(self.action)}'

    def get_label(self):
        if self.role:
            return self.get_role_display()
        return ''

    def get_value(self):
        return str(self.person)

    def is_moderator(self) -> bool:
        return self.role == self.Role.MODERATOR

    @classmethod
    def get_roles_editable_in_action_by(cls, action: Action, person: Person) -> typing.Iterable[ModelWithRole.Role | None]:
        is_moderator = person is not None and action.contact_persons.filter(
            role=cls.Role.MODERATOR,
            person_id=person.pk,
        ).exists()
        if is_moderator:
            return [cls.Role.EDITOR]
        return []



class ActionSchedule(models.Model, PlanRelatedModel):  # type: ignore[django-manager-missing]
    """A schedule for an action with begin and end dates."""

    plan = ParentalKey('actions.Plan', on_delete=models.CASCADE, related_name='action_schedules')
    name = models.CharField(max_length=100)
    begins_at = models.DateField()
    ends_at = models.DateField(null=True, blank=True)
    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'name', 'begins_at', 'ends_at'
    ]

    class Meta:
        ordering = ('plan', 'begins_at')
        verbose_name = _('action schedule')
        verbose_name_plural = _('action schedules')

    def __str__(self):
        return self.name


@reversion.register()
class ActionStatus(models.Model, PlanRelatedModel):  # type: ignore[django-manager-missing]
    """The current status for the action ("on time", "late", "completed", etc.)."""
    plan = ParentalKey(
        'actions.Plan', on_delete=models.CASCADE, related_name='action_statuses',
        verbose_name=_('plan')
    )
    name = models.CharField(max_length=50, verbose_name=_('name'))
    identifier = IdentifierField(max_length=20)
    is_completed = models.BooleanField(default=False, verbose_name=_('is completed'))
    color = models.CharField(max_length=50, verbose_name=_('color'), blank=True, null=True)

    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'name', 'identifier', 'is_completed'
    ]

    class Meta:
        unique_together = (('plan', 'identifier'),)
        verbose_name = _('action status')
        verbose_name_plural = _('action statuses')

    def get_color(self, cache: WatchObjectCache | None = None):
        if self.color:
            return self.color
        summary = ActionStatusSummaryIdentifier.for_status(self).get_data({'plan': self.plan, 'cache': cache})
        return summary.color

    def __str__(self):
        return str(self.name)


@reversion.register()
class ActionImplementationPhase(PlanRelatedModel, OrderedModel):  # type: ignore[django-manager-missing]
    plan = ParentalKey(
        'actions.Plan', on_delete=models.CASCADE, related_name='action_implementation_phases',
        verbose_name=_('plan')
    )
    name = models.CharField(max_length=50, verbose_name=_('name'))
    identifier = IdentifierField(max_length=20)
    color = models.CharField(max_length=50, verbose_name=_('color'), blank=True, null=True)

    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'order', 'name', 'identifier', 'color'
    ]

    class Meta:
        ordering = ('plan', 'order')
        unique_together = (('plan', 'identifier'),)
        verbose_name = _('action implementation phase')
        verbose_name_plural = _('action implementation phases')

    def __str__(self):
        return self.name


class ActionDecisionLevel(models.Model, PlanRelatedModel):  # type: ignore[django-manager-missing]
    plan = models.ForeignKey(
        'actions.Plan', on_delete=models.CASCADE, related_name='action_decision_levels',
        verbose_name=_('plan')
    )
    name = models.CharField(max_length=200, verbose_name=_('name'))
    identifier = IdentifierField()

    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'name', 'identifier',
    ]

    class Meta:
        unique_together = (('plan', 'identifier'),)

    def __str__(self):
        return self.name


class ActionTaskQuerySet(models.QuerySet):
    def active(self):
        return self.exclude(state__in=(ActionTask.CANCELLED, ActionTask.COMPLETED))


class ActionRelatedModelTransModelMixin():
    @classmethod
    def from_serializable_data(cls, data, check_fks=True, strict_fks=True):
        if 'i18n' in data:
            del data['i18n']
        kwargs = {}
        to_delete = set()
        for field_name, value in data.items():
            field = None
            try:
                field = cls._meta.get_field(field_name)
            except FieldDoesNotExist:
                kwargs[field_name] = value
            if isinstance(field, TranslatedVirtualField):
                to_delete.add(field_name)
        for f in to_delete:
            del data[f]
        del data['action']
        return model_from_serializable_data(cls, data, check_fks=check_fks, strict_fks=strict_fks)


@reversion.register()
class ActionTask(ActionRelatedModelTransModelMixin, models.Model):
    """A task that should be completed during the execution of an action.

    The task will have at least a name and an estimate of the due date.
    """

    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'

    STATES = (
        (NOT_STARTED, _('not started')),
        (IN_PROGRESS, _('in progress')),
        (COMPLETED, _('completed')),
        (CANCELLED, _('cancelled')),
    )

    action = ParentalKey(
        Action, on_delete=models.CASCADE, related_name='tasks',
        verbose_name=_('action')
    )
    name = models.CharField(max_length=250, verbose_name=_('name'))
    state = models.CharField(max_length=20, choices=STATES, default=NOT_STARTED, verbose_name=_('state'))
    comment = RichTextField(null=True, blank=True, verbose_name=_('comment'))
    due_at = models.DateField(
        verbose_name=_('due date'),
        help_text=_('The date by which the task should be completed (deadline)')
    )
    date_format = DateFormatField(
        verbose_name=_('Due date format'),
        help_text=_(
            'Format of action task due dates shown in the public UI. \
            The default for all actions can be specified on the actions page.'
        ),
        blank=True,
        null=True,
        default=None
    )
    completed_at = models.DateField(
        null=True, blank=True, verbose_name=_('completion date'),
        help_text=_('The date when the task was completed')
    )

    completed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name=_('completed by'), editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False, verbose_name=_('created at'))
    modified_at = models.DateTimeField(auto_now=True, editable=False, verbose_name=_('modified at'))

    sent_notifications = GenericRelation('notifications.SentNotification', related_query_name='action_task')

    i18n = TranslationField(fields=('name', 'comment'), default_language_field='action__plan__primary_language_lowercase')

    objects = ActionTaskQuerySet.as_manager()

    verbose_name_partitive = pgettext_lazy('partitive', 'action task')

    public_fields: ClassVar = [
        'id', 'action', 'name', 'state', 'comment', 'due_at', 'date_format', 'completed_at', 'created_at',
        'modified_at',
    ]

    class Meta:
        ordering = ('action', '-due_at')
        verbose_name = _('action task')
        verbose_name_plural = _('action tasks')
        constraints = [
            # Ensure a task is completed if and only if it has completed_at
            models.CheckConstraint(check=~Q(state='completed') | Q(completed_at__isnull=False),
                                   name='%(app_label)s_%(class)s_completed_at_if_completed'),
            models.CheckConstraint(check=Q(completed_at__isnull=True) | Q(state='completed'),
                                   name='%(app_label)s_%(class)s_completed_if_completed_at'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.state != ActionTask.COMPLETED and self.completed_at is not None:
            raise ValidationError({'completed_at': _('Non-completed tasks cannot have a completion date')})
        if self.state == ActionTask.COMPLETED and self.completed_at is None:
            raise ValidationError({'completed_at': _('Completed tasks must have a completion date')})
        # TODO: Put this check in, but the following won't work because self.action is None when creating a new
        # ActionTask as it is a ParentalKey.
        # today = self.action.plan.now_in_local_timezone().date()
        # if self.completed_at is not None and self.completed_at > today:
        #     raise ValidationError({'completed_at': _("Date can't be in the future")})

    def get_notification_context(self, plan=None):
        if plan is None:
            plan = self.action.plan
        return {
            'action': self.action.get_notification_context(plan),
            'name': self.name,
            'due_at': self.due_at,
            'state': self.state
        }


class ActionImpact(PlanRelatedModel, OrderedModel):  # type: ignore[django-manager-missing]
    """An impact classification for an action in an action plan."""

    plan = ParentalKey(
        'actions.Plan', on_delete=models.CASCADE, related_name='action_impacts',
        verbose_name=_('plan')
    )
    name = models.CharField(max_length=200, verbose_name=_('name'))
    identifier = IdentifierField()

    i18n = TranslationField(fields=('name',), default_language_field='plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'plan', 'name', 'identifier', 'order',
    ]

    class Meta:
        unique_together = (('plan', 'identifier'),)
        ordering = ('plan', 'order')
        verbose_name = _('action impact class')
        verbose_name_plural = _('action impact classes')

    def __str__(self):
        return '%s (%s)' % (self.name, self.identifier)


class ActionLink(ActionRelatedModelTransModelMixin, OrderedModel):
    """A link related to an action."""

    action = ParentalKey(Action, on_delete=models.CASCADE, verbose_name=_('action'), related_name='links')
    url = models.URLField(max_length=400, verbose_name=_('URL'), validators=[URLValidator(('http', 'https'))])
    title = models.CharField(max_length=254, verbose_name=_('title'), blank=True)

    i18n = TranslationField(fields=('url', 'title'), default_language_field='action__plan__primary_language_lowercase')

    public_fields: ClassVar = [
        'id', 'action', 'url', 'title', 'order'
    ]

    class Meta:
        ordering = ['action', 'order']
        indexes = [
            models.Index(fields=['action', 'order']),
        ]
        verbose_name = _('action link')
        verbose_name_plural = _('action links')

    def __str__(self):
        if self.title:
            return f'{self.title}: {self.url}'
        return self.url


class ActionStatusUpdate(models.Model):
    action = models.ForeignKey(
        Action, on_delete=models.CASCADE, related_name='status_updates',
        verbose_name=_('action')
    )
    title = models.CharField(max_length=200, verbose_name=_('title'))
    date = models.DateField(verbose_name=_('date'), blank=True)
    author = models.ForeignKey(
        'people.Person', on_delete=models.SET_NULL, related_name='status_updates',
        null=True, blank=True, verbose_name=_('author')
    )
    content = models.TextField(verbose_name=_('content'))

    created_at = models.DateField(verbose_name=_('created at'), editable=False, blank=True)
    modified_at = models.DateField(verbose_name=_('created at'), editable=False, blank=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name=_('created by'), editable=False,
    )

    public_fields: ClassVar = [
        'id', 'action', 'title', 'date', 'author', 'content', 'created_at', 'modified_at',
    ]

    class Meta:
        verbose_name = _('action status update')
        verbose_name_plural = _('action status updates')
        ordering = ('-date',)

    def save(self, *args, **kwargs):
        now = self.action.plan.now_in_local_timezone()
        if self.pk is None:
            if self.date is None:
                self.date = now.date()
            if self.created_at is None:
                self.created_at = now.date()
        if self.modified_at is None:
            self.modified_at = now.date()
        return super().save(*args, **kwargs)

    def __str__(self):
        return '%s – %s – %s' % (self.action, self.created_at, self.title)


class ImpactGroupAction(models.Model):
    group = models.ForeignKey(
        'actions.ImpactGroup', verbose_name=_('name'), on_delete=models.CASCADE,
        related_name='actions',
    )
    action = models.ForeignKey(
        Action, verbose_name=_('action'), on_delete=models.CASCADE,
        related_name='impact_groups',
    )
    impact = models.ForeignKey(
        ActionImpact, verbose_name=_('impact'), on_delete=models.CASCADE,
        related_name='+',
    )

    public_fields: ClassVar = [
        'id', 'group', 'action', 'impact',
    ]

    class Meta:
        unique_together = (('group', 'action'),)
        verbose_name = _('impact group action')
        verbose_name_plural = _('impact group actions')

    def __str__(self):
        return "%s ➜ %s" % (self.action, self.group)


class ActionModeratorApprovalTask(Task):
    def locked_for_user(self, obj: Action, user: User):
        return not user.can_approve_action(obj)

    def get_actions(self, obj: Action, user: User):
        if user.can_approve_action(obj):
            return [
                ("approve", _("Approve"), False),
                # ("approve", _("Approve with comment"), True),
                ("reject", _("Request changes"), True),
            ]
        else:
            return []
