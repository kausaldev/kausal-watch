from __future__ import annotations
import typing

import reversion
from autoslug.fields import AutoSlugField
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.constraints import Deferrable
from django.utils.translation import gettext_lazy as _
from modelcluster.models import ClusterableModel, ParentalKey, ParentalManyToManyField
from modeltrans.fields import TranslationField
from modeltrans.manager import MultilingualManager
from wagtail.fields import RichTextField

from aplans.types import UserOrAnon
from aplans.utils import (
    ChoiceArrayField, InstancesEditableByMixin, InstancesVisibleForMixin, OrderedModel, ReferenceIndexedModelMixin,
    get_supported_languages, ModelWithPrimaryLanguage
)
from indicators.models import Unit

from typing import Any, ClassVar, Self
if typing.TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from .plan import Plan
    from .category import CategoryType
    from actions.attributes import AttributeType as AttributeTypeWrapper, DraftAttributes


class AttributeTypeQuerySet(models.QuerySet['AttributeType']):
    def for_categories(self, plan: 'Plan'):
        from .category import CategoryType

        ct = ContentType.objects.get_for_model(CategoryType)
        ct_qs = CategoryType.objects.filter(plan=plan).values('id')
        f = Q(scope_content_type=ct) & Q(scope_id__in=ct_qs)
        return self.filter(f)

    def for_actions(self, plan: 'Plan'):
        from .plan import Plan

        ct = ContentType.objects.get_for_model(Plan)
        f = Q(scope_content_type=ct) & Q(scope_id=plan.id)
        return self.filter(f)


@reversion.register(follow=['choice_options'])
class AttributeType(  # type: ignore[django-manager-missing]
        InstancesEditableByMixin, InstancesVisibleForMixin, ReferenceIndexedModelMixin, ClusterableModel, OrderedModel,
        ModelWithPrimaryLanguage
):
    class AttributeFormat(models.TextChoices):
        ORDERED_CHOICE = 'ordered_choice', _('Ordered choice')
        OPTIONAL_CHOICE_WITH_TEXT = 'optional_choice', _('Optional choice with optional text')
        # TODO: combine the different choice attributes under one format
        UNORDERED_CHOICE = 'unordered_choice', _('Choice')
        TEXT = 'text', _('Text')
        RICH_TEXT = 'rich_text', _('Rich text')
        NUMERIC = 'numeric', _('Numeric')
        CATEGORY_CHOICE = 'category_choice', _('Category')

    # Model to whose instances attributes of this type can be attached
    # TODO: Enforce Action or Category
    object_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')

    # An instance that this attribute type is specific to (e.g., a plan or a category type) so that it is only shown for
    # objects within the that scope.
    # TODO: Enforce Plan or CategoryType
    scope_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')
    scope_id = models.PositiveIntegerField()
    scope: models.ForeignKey[Plan, Plan] | models.ForeignKey[CategoryType, CategoryType] = GenericForeignKey(
        'scope_content_type', 'scope_id'
    ) #type: ignore

    name = models.CharField(max_length=100, verbose_name=_('name'))
    name_i18n: str

    identifier = AutoSlugField(
        always_update=True,
        populate_from='name',
        unique_with=('object_content_type', 'scope_content_type', 'scope_id'),
    )
    help_text = models.TextField(verbose_name=_('help text'), blank=True)
    format = models.CharField(max_length=50, choices=AttributeFormat.choices, verbose_name=_('Format'))
    unit = models.ForeignKey(
        Unit, blank=True, null=True, on_delete=models.PROTECT, related_name='+',
        verbose_name=_('Unit (only if format is numeric)'),
    )
    attribute_category_type = models.ForeignKey(
        'actions.CategoryType', blank=True, null=True, on_delete=models.CASCADE, related_name='+',
        verbose_name=_('Category type (if format is category)'),
        help_text=_('If the format is "Category", choose which category type the field values can be chosen from'),
    )
    show_choice_names = models.BooleanField(
        default=True, verbose_name=_('show choice names'),
        help_text=_('If the format is "ordered choice", determines whether the choice names are displayed'),
    )
    has_zero_option = models.BooleanField(
        default=False, verbose_name=_('has zero option'),
        help_text=_('If the format is "ordered choice", determines whether the first option is displayed with zero '
                    'bullets instead of one'),
    )
    max_length = models.PositiveIntegerField(blank=True, null=True, verbose_name=_('character limit for text fields'))
    show_in_reporting_tab = models.BooleanField(default=False, verbose_name=_('show in reporting tab'))
    choice_attributes: models.manager.RelatedManager[AttributeChoice]

    # Intentionally overrides ModelWithPrimaryLanguage.primary_language
    # leaving out the default keyword argument
    primary_language = models.CharField(max_length=8, choices=get_supported_languages())
    other_languages = ChoiceArrayField(
        models.CharField(max_length=8, choices=get_supported_languages()),
        default=list, null=True, blank=True
    )

    i18n = TranslationField(
        fields=('name', 'help_text'),
        # FIXME: This unfortunately duplicates the primary language of the plan of `scope` because we have no way of
        # easily accessing it with modeltrans. It should be kept in sync with the language of the plan of `scope`, but
        # it isn't at the moment because we hopefully will never change the primary language of a plan.
        default_language_field='primary_language_lowercase',
    )
    name_i18n: str
    help_text_i18n: str

    public_fields: ClassVar = [
        'id', 'identifier', 'name', 'help_text', 'format', 'unit', 'attribute_category_type', 'show_choice_names',
        'has_zero_option', 'choice_options',
    ]

    objects: models.Manager[AttributeType] = models.Manager.from_queryset(AttributeTypeQuerySet)()

    id: int
    choice_options: RelatedManager[AttributeTypeChoiceOption]

    class Meta:
        unique_together = (('object_content_type', 'scope_content_type', 'scope_id', 'identifier'),)
        verbose_name = _('field')
        verbose_name_plural = _('fields')
        ordering = ('scope_content_type', 'scope_id', 'order',)

    def clean(self):
        from actions.models.action import Action
        super().clean()
        if self.unit is not None and self.format != self.AttributeFormat.NUMERIC:
            raise ValidationError({'unit': _('Unit must only be used for numeric fields')})
        if not self.primary_language and self.other_languages:
            raise ValidationError(_('If no primary language is set, there must not be other languages'))
        action_ct = ContentType.objects.get_for_model(Action)
        if self.instance_editability_is_action_specific and self.object_content_type != action_ct:
            raise ValidationError({'instances_editable_by': _('This value is only allowed for action fields')})
        if self.instance_visibility_is_action_specific and self.object_content_type != action_ct:
            raise ValidationError({'instances_visible_for': _('This value is only allowed for action fields')})

    def save(self, *args, **kwargs):
        if not self.primary_language:
            assert not self.other_languages
            scope_app_label = self.scope_content_type.app_label
            scope_model = self.scope_content_type.model
            if scope_app_label == 'actions' and scope_model == 'plan':
                from .plan import Plan
                assert isinstance(self.scope, Plan)
                plan = self.scope
            elif scope_app_label == 'actions' and scope_model == 'categorytype':
                from .category import CategoryType
                assert isinstance(self.scope, CategoryType)
                plan = self.scope.plan
            else:
                raise Exception(f"Unexpected AttributeType scope content type {scope_app_label}:{scope_model}")
            self.primary_language = plan.primary_language
            self.other_languages = plan.other_languages
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_i18n


class Attribute(models.Model):
    class Meta:
        abstract = True

    # Must define a ParentalKey `type` in subclasses
    type: AttributeType
    # `content_object` must fit `type`
    # TODO: Enforce this
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def is_visible_for_user(self, user: UserOrAnon, plan: Plan) -> bool:
        from actions.models.action import Action
        assert plan is not None
        if self.content_type_id == ContentType.objects.get_for_model(Action).id:
            action = self.content_object
        else:
            action = None
        return self.type.is_instance_visible_for(user, plan, action)


@reversion.register()
class AttributeTypeChoiceOption(ClusterableModel, OrderedModel):  # type: ignore[django-manager-missing]
    type = ParentalKey(AttributeType, on_delete=models.CASCADE, related_name='choice_options')
    name = models.CharField(max_length=100, verbose_name=_('name'))
    identifier = AutoSlugField(
        always_update=True,
        populate_from='name',
        unique_with='type',
    )

    i18n = TranslationField(
        fields=('name',),
        default_language_field='type__primary_language_lowercase',
    )

    objects: models.Manager[AttributeTypeChoiceOption] = MultilingualManager()

    public_fields: ClassVar = ['id', 'identifier', 'name']

    override_order = False  # see OrderedModel

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['type', 'identifier'],
                name='unique_identifier_per_type',
            ),
            models.UniqueConstraint(
                fields=['type', 'order'],
                name='unique_order_per_type',
                deferrable=Deferrable.DEFERRED,
            ),
        ]
        ordering = ('type', 'order')
        verbose_name = _('attribute choice option')
        verbose_name_plural = _('attribute choice options')

    def __str__(self):
        return self.name

    def filter_siblings(self, qs: models.QuerySet[Self]) -> models.QuerySet[Self]:
        # Used by OrderedModel to make sure order starts at 0 for each attribute type
        return qs.filter(type=self.type)


@reversion.register(follow=['categories'])
class AttributeCategoryChoice(Attribute, ClusterableModel):
    type = ParentalKey(
        AttributeType, on_delete=models.CASCADE, related_name='category_choice_attributes'
    )
    categories = ParentalManyToManyField('actions.Category', related_name='+')

    public_fields: ClassVar = ['id', 'categories']

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return "; ".join([str(c) for c in self.categories.all()])


@reversion.register(follow=['choice'])
class AttributeChoice(Attribute):
    type = ParentalKey(AttributeType, on_delete=models.CASCADE, related_name='choice_attributes')
    choice = models.ForeignKey(
        AttributeTypeChoiceOption, on_delete=models.CASCADE, related_name='choice_attributes'
    )

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return str(self.choice)


@reversion.register(follow=['choice'])
class AttributeChoiceWithText(Attribute):
    type = ParentalKey(
        AttributeType, on_delete=models.CASCADE, related_name='choice_with_text_attributes'
    )
    choice = models.ForeignKey(
        AttributeTypeChoiceOption, blank=True, null=True, on_delete=models.CASCADE,
        related_name='choice_with_text_attributes',
    )
    text = RichTextField(verbose_name=_('Text'), blank=True, null=True)

    i18n = TranslationField(
        fields=('text',),
        default_language_field='type__primary_language_lowercase',
    )

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return f'{self.choice}; {self.text}'


@reversion.register()
class AttributeText(Attribute):
    type = ParentalKey(
        AttributeType,
        on_delete=models.CASCADE,
        related_name='text_attributes',
    )
    text = models.TextField(verbose_name=_('Text'))
    text_i18n: str

    i18n = TranslationField(
        fields=('text',),
        default_language_field='type__primary_language_lowercase',
    )

    public_fields: ClassVar = ['id', 'type', 'text']

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return self.text_i18n


@reversion.register()
class AttributeRichText(Attribute):
    type = ParentalKey(
        AttributeType,
        on_delete=models.CASCADE,
        related_name='rich_text_attributes',
    )
    text = RichTextField(verbose_name=_('Text'))
    text_i18n: str

    i18n = TranslationField(
        fields=('text',),
        default_language_field='type__primary_language_lowercase',
    )

    public_fields: ClassVar = ['id', 'type', 'text']

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return self.text_i18n


@reversion.register()
class AttributeNumericValue(Attribute):
    type = ParentalKey(AttributeType, on_delete=models.CASCADE, related_name='numeric_value_attributes')
    value = models.FloatField()

    public_fields: ClassVar = ['id', 'type', 'value']

    class Meta:
        unique_together = ('type', 'content_type', 'object_id')

    def __str__(self):
        return str(self.value)


class ModelWithAttributes(models.Model):
    """Fields for models with attributes.

    Models inheriting from this should implement a couple of abstract methods (see below). Unfortunately Django models
    don't get along well with the `abc` package. (Decorating with `@abstractmethod` only has an effect if deriving from
    `ABC`, which conflicts with the metaclass of `Model`.).
    """
    choice_attributes = GenericRelation(to='actions.AttributeChoice')
    choice_with_text_attributes = GenericRelation(to='actions.AttributeChoiceWithText')
    text_attributes = GenericRelation(to='actions.AttributeText')
    rich_text_attributes = GenericRelation(to='actions.AttributeRichText')
    numeric_value_attributes = GenericRelation(to='actions.AttributeNumericValue')
    category_choice_attributes = GenericRelation(to='actions.AttributeCategoryChoice')

    ATTRIBUTE_RELATIONS = [
        'choice_attributes', 'choice_with_text_attributes', 'text_attributes', 'rich_text_attributes',
        'numeric_value_attributes', 'category_choice_attributes',
    ]

    # Register models inheriting from this one using:
    # @reversion.register(follow=ModelWithAttributes.REVERSION_FOLLOW)
    REVERSION_FOLLOW = ATTRIBUTE_RELATIONS

    draft_attributes: DraftAttributes | None
    id: int

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.draft_attributes = None

    def get_editable_attribute_types(self, user: UserOrAnon) -> list[AttributeTypeWrapper]:
        raise NotImplementedError("Implement in subclass")

    def get_visible_attribute_types(self, user: UserOrAnon) -> list[AttributeTypeWrapper]:
        raise NotImplementedError("Implement in subclass")

    @classmethod
    def from_serializable_data(cls, data, check_fks=True, strict_fks=False):
        """Called by Wagtail when editing a draft."""
        from actions.attributes import DraftAttributes
        serialized_attributes = data.pop('attributes', {})
        result = super().from_serializable_data(data, check_fks=check_fks, strict_fks=strict_fks)
        result.draft_attributes = DraftAttributes.from_revision_content(serialized_attributes)
        return result

    def _value_is_empty(self, value: dict[str, Any]):
        return len([v for v in value.values() if v is not None or v == '' or v == []]) == 0

    def set_attribute(
            self,
            attribute_type: AttributeTypeWrapper,
            existing_attribute: Attribute,
            value_parameters: dict[str, Any],
            attribute_value_input: Any
    ):
        if existing_attribute is None:
            if self._value_is_empty(value_parameters):
                return (None, None)

            attribute_value_class = attribute_type.VALUE_CLASS
            attribute_value = attribute_value_class.from_serialized_value(attribute_value_input)
            new_attribute = attribute_value.instantiate_attribute(attribute_type, self)
            return ('create', new_attribute)
        if self._value_is_empty(value_parameters):
            return ('delete', existing_attribute)
        for k, v in value_parameters.items():
            setattr(existing_attribute, k, v)
        return ('update', existing_attribute, value_parameters.keys())

    def set_category_choice_attribute(self, attribute_type, existing_attribute, category_ids):
        if existing_attribute is None:
            if category_ids == []:
                return (None, None)
            attribute_value_class = attribute_type.VALUE_CLASS
            attribute_value = attribute_value_class.from_serialized_value(category_ids)
            new_attribute = attribute_value.instantiate_attribute(attribute_type, self)
            return ('create_and_set_related', new_attribute, 'categories', category_ids)
        if category_ids == []:
            return ('delete', existing_attribute)
        return ('set_related', existing_attribute, 'categories', category_ids)

    class Meta:
        abstract = True
