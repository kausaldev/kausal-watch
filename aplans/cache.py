from __future__ import annotations
from functools import cached_property

from django.contrib.contenttypes.models import ContentType

from aplans.graphql_types import WorkflowStateEnum
from aplans.types import UserOrAnon
from actions.models import (
    ActionStatus, ActionImplementationPhase, Plan, AttributeTypeChoiceOption, AttributeType, Action, ActionSchedule,
    Category
)
from reports.models import Report
from typing import TypeVar, Type
import typing
if typing.TYPE_CHECKING:
    from typing import Sequence, Iterable
    from orgs.models import Organization, OrganizationQuerySet
    from people.models import Person, PersonQuerySet


class PlanSpecificCache:
    plan: 'Plan'
    organizations: dict[int, Organization]
    persons: dict[int, Person]

    def __init__(self, plan: 'Plan'):
        self.plan = plan
        self.organizations = {}
        self.persons = {}

    @cached_property
    def action_statuses(self) -> list[ActionStatus]:
        return list(self.plan.action_statuses.all())

    @cached_property
    def plan_has_action_dependency_roles(self):
        return self.plan.action_dependency_roles.exists()

    @cached_property
    def implementation_phases(self) -> list[ActionImplementationPhase]:
        return list(self.plan.action_implementation_phases.all())

    def populate_organizations(self, organizations: OrganizationQuerySet) -> None:
        '''Add the organizations from a queryset to the cache, keeping any organizations that might already be in the cache.'''
        for org in organizations:
            self.organizations[org.pk] = org

    def populate_persons(self, persons: PersonQuerySet) -> None:
        '''Add the persons from a queryset to the cache, keeping any persons that might already be in the cache.'''
        for person in persons:
            self.persons[person.pk] = person

    def get_organization(self, pk: int) -> Organization | None:
        return self.organizations.get(pk)

    def get_person(self, pk: int) -> Person | None:
        return self.persons.get(pk)

    def get_action_status(self, *, id: int | None = None, identifier: str | None = None) -> ActionStatus | None:
        # Must supply either id or identifier
        assert bool(id is None) != bool(identifier is None)

        for a_s in self.action_statuses:
            if id is not None:
                if a_s.id == id:
                    return a_s
            else:
                if a_s.identifier == identifier:
                    return a_s
        return None

    def get_action_implementation_phase(self, *, id: int | None = None, identifier: str | None = None) -> ActionImplementationPhase | None:
        assert bool(id is None) != bool(identifier is None)
        for implementation_phase in self.implementation_phases:
            if id is not None:
                if implementation_phase.id == id:
                    return implementation_phase
            else:
                if implementation_phase.identifier == identifier:
                    return implementation_phase
        return None

    @cached_property
    def attribute_choice_options(self) -> dict[int, AttributeTypeChoiceOption]:
        result = {}
        plan_content_type = ContentType.objects.get_for_model(Plan)
        choice_formats = (
            AttributeType.AttributeFormat.ORDERED_CHOICE,
            AttributeType.AttributeFormat.OPTIONAL_CHOICE_WITH_TEXT,
            AttributeType.AttributeFormat.UNORDERED_CHOICE
        )
        for attribute_type in (
            AttributeType.objects.filter(
                scope_content_type=plan_content_type
            ).filter(
                scope_id=self.plan.pk
            ).filter(
                format__in=choice_formats
            )
        ).prefetch_related('choice_options'):
            for choice_option in attribute_type.choice_options.all():
                result[choice_option.pk] = choice_option
        return result

    def get_choice_option(self, pk) -> AttributeTypeChoiceOption:
        return self.attribute_choice_options[pk]

    @cached_property
    def latest_reports(self) -> list[Report]:
        qs = (
            Report.objects
                .filter(type__plan=self.plan)
                .order_by('type', '-start_date')
                .distinct('type')
        )
        return list(qs)

    @classmethod
    def fetch(cls, plan_id: int) -> Plan:
        return Plan.objects.get(id=plan_id)

    def enrich_action(self, action: Action) -> None:
        action.plan = self.plan
        if action.status_id is not None:
            action.status = self.get_action_status(id=action.status_id)
        if action.implementation_phase_id is not None:
            action.implementation_phase = self.get_action_implementation_phase(id=action.implementation_phase_id)


class WatchObjectCache:
    plan_caches: dict[int, PlanSpecificCache]
    admin_plan_cache: PlanSpecificCache | None
    query_workflow_state: WorkflowStateEnum
    def __init__(self) -> None:
        self.plan_caches = {}
        self.admin_plan_cache = None
        self.query_workflow_state = WorkflowStateEnum.PUBLISHED

    def for_plan_id(self, plan_id: int) -> PlanSpecificCache:
        plan_cache = self.plan_caches.get(plan_id)
        if plan_cache is None:
            plan = PlanSpecificCache.fetch(plan_id)
            plan_cache = PlanSpecificCache(plan)
            self.plan_caches[plan_id] = plan_cache
        return plan_cache

    def for_plan(self, plan: Plan) -> PlanSpecificCache:
        return self.for_plan_id(plan.id)


T = TypeVar('T')
S = TypeVar('S')


class SerializedDictWithRelatedObjectCache(dict[T, S]):
    cache: PlanSpecificCache

    def __init__(self, *args, cache: PlanSpecificCache | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = cache
