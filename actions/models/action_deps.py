from __future__ import annotations
import functools

import typing
from typing import ClassVar, Self, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, ForeignKey
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modeltrans.fields import TranslationField

import networkx as nx

from aplans.types import UserOrAnon
from aplans.utils import OrderedModel

if typing.TYPE_CHECKING:
    from .plan import Plan
    from .action import Action


class ActionDependencyRole(OrderedModel):
    plan = ParentalKey('actions.Plan', on_delete=models.CASCADE, related_name='action_dependency_roles')
    name = models.CharField(max_length=1000, verbose_name=_('name'))

    i18n = TranslationField(
        fields=('name',),
        default_language_field='plan__primary_language_lowercase',
    )

    public_fields: ClassVar = [
        'id', 'name',
    ]

    class Meta:
        constraints = [
            models.UniqueConstraint(name='unique_plan_order', fields=['plan', 'order']),
            models.UniqueConstraint(name='unique_plan_name', fields=['plan', 'name']),
        ]

    def __str__(self):
        return self.name


MAX_DEPENDENCY_LEVELS = 3


class ActionDependencyRelationshipQuerySet(models.QuerySet['ActionDependencyRelationship']):
    def all_for_action(self, action: Action) -> Self:
        queries = []
        for level in range(MAX_DEPENDENCY_LEVELS):
            kwargs = {}
            parts = ['preceding__preceding_relationships'] * level + ['preceding']
            kwargs = {'__'.join(parts): action}
            queries.append(Q(**kwargs))
            parts = ['dependent__dependent_relationships'] * level + ['dependent']
            kwargs = {'__'.join(parts): action}
            queries.append(Q(**kwargs))

        chains = self.filter(functools.reduce(lambda x, y: x | y, queries)).distinct()
        return chains

    def visible_for_user(self, user: UserOrAnon | None, plan: Plan | None = None):
        from actions.models import Action
        actions = Action.objects.visible_for_user(user, plan)
        return self.filter(Q(preceding__in=actions) | Q(dependent__in=actions)).distinct()

    def for_plan(self, plan: Plan) -> Self:
        return self.filter(
            Q(preceding__plan=plan) | Q(dependent__plan=plan)
        )


class ActionDependencyRelationship(models.Model):
    preceding: ForeignKey['Action'] = ParentalKey(
        'actions.Action', on_delete=models.CASCADE, related_name='dependent_relationships',
        verbose_name=_("Preceding action")
    )
    dependent = ForeignKey(
        'actions.Action', on_delete=models.CASCADE, related_name='preceding_relationships',
        verbose_name=_("Dependent action")
    )

    objects = ActionDependencyRelationshipQuerySet.as_manager()

    public_fields: ClassVar = [
        'id', 'preceding', 'dependent',
    ]

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['preceding', 'dependent'], name='unique_pairs') # , nulls_distinct=False)  # type: ignore[call-overload]
        ]

    @classmethod
    def get_graph(cls, plan: Plan):
        g = nx.DiGraph()  # Initialize a directed graph

        # Fetch all ActionDependencyRelationship instances that involve actions from the same plan.
        relationships: ActionDependencyRelationshipQuerySet = cls.objects.for_plan(plan)

        # Create dictionaries to map action IDs to their corresponding
        preceding_map = {r.preceding_id: r for r in relationships}

        # Populate the graph with edges representing the dependency relationships
        for relationship in relationships:
            if not relationship.dependent_id:
                continue

            dep_id = relationship.dependent_id
            dependent_rel = preceding_map.get(dep_id)
            if not dependent_rel:
                continue
            # Add an edge from `preceding` to `dependent`
            g.add_edge(str(relationship.id), str(dependent_rel.id))

        return g

    def _has_cycle(self):
        """Checks if the dependency graph has a cycle."""
        g = self.get_graph(self.preceding.plan).copy()
        if not self.dependent:
            return False

        if self.id and g.has_node(str(self.id)):
            g.remove_node(str(self.id))

        deps = ActionDependencyRelationship.objects.filter(Q(preceding=self.dependent) | Q(dependent=self.preceding))
        if not deps:
            return False
        for dep in deps:
            if dep.dependent == self.preceding:
                g.add_edge(str(dep.id), 'new')
            else:
                g.add_edge('new', str(dep.id))

        g.add_edge('new', str(self.dependent.id))
        if nx.is_directed_acyclic_graph(g):
            return False
        return True

    def _validate_max_chain_length(self):
        """Ensures that the max length of a dependency chain does not exceed `MAX_DEPENDENCY_LEVELS`."""

        if not self.dependent:
            return

        g = self.get_graph(self.preceding.plan)
        if self.id and g.has_node(str(self.id)):
            g.remove_node(str(self.id))

        deps = ActionDependencyRelationship.objects.filter(Q(preceding=self.dependent) | Q(dependent=self.preceding))
        for dep in deps:
            if dep.dependent == self.preceding:
                g.add_edge(str(dep.id), 'new')
            else:
                g.add_edge('new', str(dep.id))

        # Check only the chains that are connected to `self`
        longest = nx.dag_longest_path_length(g)
        if longest + 1 >= MAX_DEPENDENCY_LEVELS:
            raise ValidationError(_("Maximum dependency chain length exceeded."))

    def clean(self):
        super().clean()
        # FIXME: Disabled validation for now since `preceding` won't be set when creating an
        # ActionDependencyRelationship with an InlinePanel because then there is no guarantee that the action is already
        # in the DB.
        # if getattr(self, 'preceding', None) is None:
        #     raise ValidationError(dict(preceding=_("Must be set.")))
        #
        # # Determine the plan based on the set action (preceding or dependent)
        # plan = cast('Plan', self.preceding.plan if self.preceding else self.dependent.plan)  # type: ignore[union-attr]
        #
        # # Ensure the other action (if set) has the same plan
        # if self.preceding and self.dependent and self.preceding.plan != self.dependent.plan:
        #     raise ValidationError(_("The preceding and dependent actions must belong to the same plan."))
        #
        # # Check for cycles in the dependency relationships
        # if self._has_cycle():
        #     raise ValidationError(_("The dependency relationships contain a cycle."))
        #
        # self._validate_max_chain_length()

    def __str__(self):
        p = str(self.preceding.identifier) if self.preceding is not None else ''
        d = str(self.dependent.identifier) if self.dependent is not None else ''
        return ' → '.join([p, d])
