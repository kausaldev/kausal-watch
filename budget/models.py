from __future__ import annotations

import reversion
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from django.db import models
from django.utils.translation import gettext_lazy as _
from modeltrans.fields import TranslationField

from actions.models.action import Action
from actions.models.category import Category, CategoryType
from actions.models.plan import Plan
from aplans.utils import OrderedModel


@reversion.register()
class Dimension(ClusterableModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=100, verbose_name=_('name'))

    i18n = TranslationField(fields=['name'])
    name_i18n: str

    class Meta:  # pyright:ignore
        verbose_name = _('dimension')
        verbose_name_plural = _('dimensions')
        ordering = ['name']

    def __str__(self):
        return self.name_i18n


class DimensionCategory(OrderedModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    dimension = ParentalKey(Dimension, blank=False, on_delete=models.CASCADE, related_name='categories')
    label = models.CharField(max_length=100, verbose_name=_('label'))

    i18n = TranslationField(fields=['label'])
    label_i18n: str

    class Meta:  # pyright:ignore
        verbose_name = _('dimension category')
        verbose_name_plural = _('dimension categories')

    def __str__(self):
        if self.label:
            return f'{self.label_i18n} ({self.uuid})'
        return str(self.uuid)


class DimensionScope(OrderedModel):
    """Link a dimension to a context in which it can be used, such as a plan or a category type."""

    dimension = models.ForeignKey(Dimension, on_delete=models.CASCADE, related_name='scopes')
    scope_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')
    scope_id = models.PositiveIntegerField()
    scope: models.ForeignKey[Plan, Plan] | models.ForeignKey[CategoryType, CategoryType] = GenericForeignKey(
        'scope_content_type', 'scope_id'
    ) # type: ignore[assignment]


class DatasetSchema(models.Model):
    class TimeResolution(models.TextChoices):
        """Time resolution of all data points.

        If a dataset has, e.g., monthly time resolution, then each data point applies to the entire month in which
        the data point's time is.
        """
        # TBD: Could also be separate model. (Some customers might be very creative in their granularities.)
        YEARLY = 'yearly', _('Yearly')  # pyright:ignore
        # QUARTERLY = 'quarterly', _('Quarterly')
        # MONTHLY = 'monthly', _('Monthly')
        # WEEKLY = 'weekly', _('Weekly')
        # DAILY = 'daily', _('Daily')
        # HOURLY = 'hourly', _('Hourly')

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    time_resolution = models.CharField(
        max_length=16, choices=TimeResolution.choices,
        default=TimeResolution.YEARLY,
        help_text=_('Time resolution of the time stamps of data points in this dataset'),
    )
    unit = models.CharField(max_length=100, blank=True, verbose_name=_('unit'))
    name = models.CharField(max_length=100, blank=True, verbose_name=_('name'))

    i18n = TranslationField(fields=['unit', 'name'])
    unit_i18n: str
    name_i18n: str

    def __str__(self):
        if self.name_i18n:
            return f'{self.name_i18n} ({self.uuid})'
        return str(self.uuid)


class DatasetSchemaDimensionCategory(OrderedModel):
    schema = models.ForeignKey(DatasetSchema, on_delete=models.PROTECT, related_name='dimension_categories', null=False, blank=False)
    category = models.ForeignKey(DimensionCategory, related_name='schemas', on_delete=models.PROTECT, null=False, blank=False)

    def filter_siblings(self, qs: models.QuerySet[DatasetSchemaDimensionCategory]) -> models.QuerySet[DatasetSchemaDimensionCategory]:
        return qs.filter(schema=self.schema, category__dimension=self.category.dimension)


def schema_default():
    '''
    By default, new datasets will have their own unique schema.
    '''
    schema = DatasetSchema.objects.create()
    return schema.pk


class Dataset(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    schema = models.ForeignKey(
        DatasetSchema, null=False, blank=False, related_name='datasets',
        verbose_name=_('schema'), on_delete=models.PROTECT,
        default=schema_default
    )
    # The "scope" generic foreign key links this dataset to an action or category
    scope_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+',
        null=True, blank=True
    )
    scope_id = models.PositiveIntegerField(null=True, blank=True)
    scope: models.ForeignKey[Action, Action] | models.ForeignKey[Category, Category] = GenericForeignKey(
        'scope_content_type', 'scope_id'
    ) # type: ignore[assignment]

    class Meta:  # pyright:ignore
        verbose_name = _('dataset')
        verbose_name_plural = _('datasets')
        ordering = ['id']


class DatasetSchemaScope(models.Model):
    """Link a dataset schema to a context in which it can be used, such as a plan."""
    schema = models.ForeignKey(DatasetSchema, on_delete=models.CASCADE, related_name='scopes')
    scope_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')
    scope_id = models.PositiveIntegerField()
    # If scope is a Plan, this schema can be used for Actions in that plan
    scope: models.ForeignKey[Plan, Plan] | models.ForeignKey[CategoryType, CategoryType] = GenericForeignKey(
        'scope_content_type', 'scope_id'
    ) # type: ignore[assignment]


class DataPoint(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    dataset = models.ForeignKey(
        Dataset, related_name='data_points', on_delete=models.CASCADE, verbose_name=_('dataset')
    )
    dimension_categories = models.ManyToManyField(
        DimensionCategory, related_name='data_points', blank=True, verbose_name=_('dimension categories')
    )
    date = models.DateField(
        verbose_name=_('date'),
        help_text=_("Date of this data point in context of the dataset's time resolution"),
    )
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_('value'))

    class Meta:  # pyright:ignore
        verbose_name = _('data point')
        verbose_name_plural = _('data points')
        ordering = ['date']
        # TODO: Enforce uniqueness constraint.
        # This doesn't work because dimension_categories is a many-to-many field.
        # constraints = [
        #     models.UniqueConstraint(fields=['dataset', 'dimension_categories', 'date'],
        #                             name='unique_data_point_value')
        # ]
