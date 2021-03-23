import datetime
from factory import RelatedFactory, SelfAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from wagtail.core.rich_text import RichText
from wagtail_factories import StructBlockFactory

import actions
from actions.models import CategoryTypeMetadata
from images.tests.factories import AplansImageFactory
from people.tests.factories import PersonFactory
from content.tests.factories import SiteGeneralContentFactory


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = 'django_orghierarchy.Organization'

    id = Sequence(lambda i: f'organization{i}')
    name = Sequence(lambda i: f'Organization {i}')
    abbreviation = Sequence(lambda i: f'org{i}')
    parent = None


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Plan'

    organization = SubFactory(OrganizationFactory)
    name = Sequence(lambda i: f'Plan {i}')
    identifier = Sequence(lambda i: f'plan{i}')
    image = SubFactory(AplansImageFactory)
    site_url = Sequence(lambda i: f'https://plan{i}.example.com')
    general_content = RelatedFactory(SiteGeneralContentFactory, factory_related_name='plan')
    show_admin_link = False

    _action = RelatedFactory('actions.tests.factories.ActionFactory', factory_related_name='plan')
    _category_type = RelatedFactory('actions.tests.factories.CategoryTypeFactory', factory_related_name='plan')
    _domain = RelatedFactory('actions.tests.factories.PlanDomainFactory', factory_related_name='plan')
    _impact_group = RelatedFactory('actions.tests.factories.ImpactGroupFactory', factory_related_name='plan')


class PlanDomainFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.PlanDomain'

    plan = SubFactory(PlanFactory, _domain=None)
    hostname = Sequence(lambda i: f'plandomain{i}.example.org')


class ActionStatusFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionStatus'

    plan = SubFactory(PlanFactory)
    name = "Test action status"
    identifier = 'test-action-status'


class ActionImplementationPhaseFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionImplementationPhase'

    plan = SubFactory(PlanFactory)
    name = "Test action implementation phase"
    identifier = 'test-aip'


class ActionScheduleFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionSchedule'

    plan = SubFactory(PlanFactory)
    name = "Test action schedule"
    begins_at = datetime.date(2020, 1, 1)


class ActionImpactFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionImpact'

    plan = SubFactory(PlanFactory)
    name = "Test action impact"
    identifier = 'test-action-impact'


class CategoryTypeFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryType'

    plan = SubFactory(PlanFactory)
    identifier = Sequence(lambda i: f'ct{i}')
    name = Sequence(lambda i: f'CategoryType {i}')


class CategoryTypeMetadataFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryTypeMetadata'

    type = SubFactory(CategoryTypeFactory)
    identifier = Sequence(lambda i: f'ctm{i}')
    name = Sequence(lambda i: f'CategoryTypeMetadata {i}')
    format = CategoryTypeMetadata.MetadataFormat.RICH_TEXT


class CategoryTypeMetadataChoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryTypeMetadataChoice'

    metadata = SubFactory(CategoryTypeMetadataFactory)
    identifier = Sequence(lambda i: f'ctmc{i}')
    name = Sequence(lambda i: f'CategoryTypeMetadataChoice {i}')


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Category'

    type = SubFactory(CategoryTypeFactory)
    identifier = Sequence(lambda i: f'category{i}')
    name = Sequence(lambda i: f'Category {i}')


class CategoryTypeMetadataFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryTypeMetadata'

    type = SubFactory(CategoryTypeFactory)
    identifier = Sequence(lambda i: f'category-type-metadata-{i}')
    name = Sequence(lambda i: f'Category type metadata {i}')
    format = CategoryTypeMetadata.MetadataFormat.RICH_TEXT


class CategoryMetadataRichTextFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryMetadataRichText'

    metadata = SubFactory(CategoryTypeMetadataFactory)
    category = SubFactory(CategoryFactory)
    text = Sequence(lambda i: f'CategoryMetadataRichText {i}')


class ImpactGroupFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ImpactGroup'

    plan = SubFactory(PlanFactory, _impact_group=None)
    identifier = Sequence(lambda i: f'Impact group {i}')
    identifier = Sequence(lambda i: f'impact-group-{i}')
    parent = None
    weight = None
    color = None


class ActionFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Action'

    plan = SubFactory(PlanFactory, _action=None)
    name = "Test action"
    identifier = 'test-action'
    official_name = name
    description = "Action description"
    impact = SubFactory(ActionImpactFactory, plan=SelfAttribute('..plan'))
    status = SubFactory(ActionStatusFactory, plan=SelfAttribute('..plan'))
    implementation_phase = SubFactory(ActionImplementationPhaseFactory, plan=SelfAttribute('..plan'))
    completion = 99


class ActionResponsiblePartyFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionResponsibleParty'

    action = SubFactory(ActionFactory)
    organization = SubFactory(OrganizationFactory)


# FIXME: The factory name does not correspond to the model name because this would suggest that we build a Person
# object. We might want to consider renaming the model ActionContactPerson to ActionContact or similar.
class ActionContactFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionContactPerson'

    action = SubFactory(ActionFactory)
    person = SubFactory(PersonFactory)


class ActionListBlockFactory(StructBlockFactory):
    class Meta:
        model = actions.blocks.ActionListBlock

    category_filter = SubFactory(CategoryFactory)


class CategoryListBlockFactory(StructBlockFactory):
    class Meta:
        model = actions.blocks.CategoryListBlock

    heading = "Category list heading"
    lead = RichText("<p>Category list lead</p>")
    style = 'cards'
