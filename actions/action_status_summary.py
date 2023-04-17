import datetime
from enum import Enum
import typing

from aplans.utils import MetadataEnum, ConstantMetadata

if typing.TYPE_CHECKING:
    from actions.models import Action, Plan
from typing import Callable


from django.utils.translation import gettext_lazy as _
from django.utils import timezone


Sentiment = Enum('Sentiment', names='POSITIVE NEGATIVE NEUTRAL')


class ActionStatusSummary(ConstantMetadata):
    default_label: str
    color: str
    is_completed: bool
    is_active: bool
    sentiment: Sentiment

    def __init__(self,
                 default_label=None,
                 color=None,
                 is_completed=False,
                 is_active=False,
                 sentiment=None):
        self.default_label = default_label
        self.color = color
        self.is_completed = is_completed
        self.is_active = is_active
        self.sentiment = sentiment


class ActionStatusSummaryIdentifier(MetadataEnum):
    # The ordering is significant
    COMPLETED = ActionStatusSummary(
        default_label=_('Completed'),
        color='green090',
        is_completed=True,
        is_active=False,
        sentiment=Sentiment.POSITIVE
    )
    ON_TIME = ActionStatusSummary(
        default_label=_('On time'),
        color='green050',
        is_completed=False,
        is_active=True,
        sentiment=Sentiment.POSITIVE
    )
    IN_PROGRESS = ActionStatusSummary(
        default_label=_('In progress'),
        color='green050',
        is_completed=False,
        is_active=True,
        sentiment=Sentiment.POSITIVE
    )
    NOT_STARTED = ActionStatusSummary(
        default_label=_('Not started'),
        color='green010',
        is_completed=False,
        is_active=True,
        sentiment=Sentiment.NEUTRAL
    )
    LATE = ActionStatusSummary(
        default_label=_('Late'),
        color='yellow050',
        is_completed=False,
        is_active=True,
        sentiment=Sentiment.NEGATIVE
    )
    CANCELLED = ActionStatusSummary(
        default_label=_('Cancelled'),
        color='grey030',
        is_completed=False,
        is_active=False,
        sentiment=Sentiment.NEUTRAL
    )
    OUT_OF_SCOPE = ActionStatusSummary(
        default_label=_('Out of scope'),
        color='grey030',
        is_completed=False,
        is_active=False,
        sentiment=Sentiment.NEUTRAL
    )
    MERGED = ActionStatusSummary(
        default_label=_('Merged'),
        color='grey030',
        is_completed=True,
        is_active=False,
        sentiment=Sentiment.NEUTRAL
    )
    POSTPONED = ActionStatusSummary(
        default_label=_('Postponed'),
        color='blue030',
        is_completed=False,
        is_active=False,
        sentiment=Sentiment.NEUTRAL
    )
    UNDEFINED = ActionStatusSummary(
        default_label=_('Unknown'),
        color='grey010',
        is_completed=False,
        is_active=True,
        sentiment=Sentiment.NEUTRAL
    )

    def get_identifier(self):
        return self.name.lower()

    def __str__(self):
        return f'{self.name}.{str(self.value)}'

    @classmethod
    def for_action(cls, action: 'Action'):
        # Some plans in production have inconsistent Capitalized identifiers
        # Once the db has been cleaned up, this match logic
        # should be revisited
        status = action.status.identifier.lower() if action.status else None
        phase = action.implementation_phase.identifier.lower() if action.implementation_phase else None
        if action.merged_with is not None:
            return cls.MERGED
        # TODO: check phase "completed" property
        if phase == 'completed':
            return cls.COMPLETED
        # phase: "begun"? "implementation?"
        if phase == 'not_started' and status == 'on_time':
            return cls.ON_TIME
        if status is None:
            return cls.UNDEFINED
        try:
            return next(a for a in cls if a.name.lower() == action.status.identifier)
        except StopIteration:
            return cls.UNDEFINED


Comparison = Enum('Comparison', names='LTE GT')


class ActionTimeliness(ConstantMetadata):
    color: str
    sentiment: Sentiment
    label: str
    boundary: Callable[['Plan'], int]
    comparison: Comparison
    identifier: 'ActionTimelinessIdentifier'
    days: int

    def __init__(self,
                 boundary: Callable[['Plan'], int],
                 color: str = None,
                 sentiment: Sentiment = None,
                 label: str = None,
                 comparison: Comparison = None,
                 ):
        self.color = color
        self.sentiment = sentiment
        self.label = label
        self.comparison = comparison
        self.boundary = boundary

    def _get_label(self, plan: 'Plan'):
        if self.comparison == Comparison.LTE:
            return _('Under %d days') % self._get_days(plan)
        return _('Over %d days') % self._get_days(plan)

    def _get_days(self, plan: 'Plan'):
        return self.boundary(plan)

    def with_context(self, context):
        if context is None:
            raise ValueError('Context with plan required to resolve timeliness')
        if 'plan' not in context:
            raise KeyError('Action timeliness values depend on the plan')
        if self.identifier is None:
            raise ValueError('with_identifier must be called before with_context')
        self.days = self._get_days(context['plan'])
        self.label = self._get_label(context['plan'])
        return self


class ActionTimelinessIdentifier(MetadataEnum):
    OPTIMAL = ActionTimeliness(
        color='green070',
        sentiment=Sentiment.POSITIVE,
        boundary=(lambda plan: plan.action_update_target_interval),
        comparison=Comparison.LTE
    )
    ACCEPTABLE = ActionTimeliness(
        color='green030',
        sentiment=Sentiment.NEUTRAL,
        boundary=(lambda plan: plan.action_update_acceptable_interval),
        comparison=Comparison.LTE
    )
    LATE = ActionTimeliness(
        color='yellow050',
        sentiment=Sentiment.NEGATIVE,
        boundary=(lambda plan: plan.action_update_acceptable_interval),
        comparison=Comparison.GT
    )
    STALE = ActionTimeliness(
        color='red050',
        sentiment=Sentiment.NEGATIVE,
        boundary=(lambda plan: plan.get_action_days_until_considered_stale()),
        comparison=Comparison.GT
    )

    @classmethod
    def for_action(cls, action: 'Action'):
        plan = action.plan
        age = timezone.now() - action.updated_at
        if age <= datetime.timedelta(days=cls.OPTIMAL.value.boundary(plan)):
            return cls.OPTIMAL
        if age <= datetime.timedelta(days=cls.ACCEPTABLE.value.boundary(plan)):
            return cls.ACCEPTABLE
        # We do not distinguish between late and stale for now
        return cls.LATE