import datetime
from factory import RelatedFactory, SelfAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from wagtail.core.rich_text import RichText
from wagtail_factories import StructBlockFactory

import actions
from actions.models import CategoryTypeMetadata
from images.tests.factories import AplansImageFactory
from pages.tests.factories import CategoryPageFactory
from people.tests.factories import PersonFactory
from content.tests.factories import SiteGeneralContentFactory


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = 'django_orghierarchy.Organization'

    id = Sequence(lambda i: f'organization{i}')
    name = Sequence(lambda i: f"Organization {i}")
    abbreviation = Sequence(lambda i: f'org{i}')
    parent = None


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Plan'

    organization = SubFactory(OrganizationFactory)
    name = Sequence(lambda i: f"Plan {i}")
    identifier = Sequence(lambda i: f'plan{i}')
    image = SubFactory(AplansImageFactory)
    site_url = Sequence(lambda i: f'https://plan{i}.example.com')
    general_content = RelatedFactory(SiteGeneralContentFactory, factory_related_name='plan')
    show_admin_link = False

    _domain = RelatedFactory('actions.tests.factories.PlanDomainFactory', factory_related_name='plan')


class PlanDomainFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.PlanDomain'

    plan = SubFactory(PlanFactory, _domain=None)
    hostname = Sequence(lambda i: f'plandomain{i}.example.org')


class ActionStatusFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionStatus'

    plan = SubFactory(PlanFactory)
    name = Sequence(lambda i: f"Action status {i}")
    identifier = Sequence(lambda i: f'action-status-{i}')


class ActionImplementationPhaseFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionImplementationPhase'

    plan = SubFactory(PlanFactory)
    name = Sequence(lambda i: f"Action implementation phase {i}")
    identifier = Sequence(lambda i: f'aip{i}')


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
    identifier = Sequence(lambda i: f'action-impact-{i}')
    name = Sequence(lambda i: f"Action impact {i}")


class CategoryTypeFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryType'

    plan = SubFactory(PlanFactory)
    identifier = Sequence(lambda i: f'ct{i}')
    name = Sequence(lambda i: f"Category type {i}")


class CategoryTypeMetadataFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryTypeMetadata'

    type = SubFactory(CategoryTypeFactory)
    identifier = Sequence(lambda i: f'ctm{i}')
    name = Sequence(lambda i: f"Category type metadata {i}")
    format = CategoryTypeMetadata.MetadataFormat.RICH_TEXT


class CategoryTypeMetadataChoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryTypeMetadataChoice'

    metadata = SubFactory(CategoryTypeMetadataFactory, format=CategoryTypeMetadata.MetadataFormat.ORDERED_CHOICE)
    identifier = Sequence(lambda i: f'ctmc{i}')
    name = Sequence(lambda i: f"Category type metadata choice {i}")


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Category'

    type = SubFactory(CategoryTypeFactory)
    identifier = Sequence(lambda i: f'category{i}')
    name = Sequence(lambda i: f"Category {i}")
    image = SubFactory(AplansImageFactory)

    _category_page = RelatedFactory(CategoryPageFactory,
                                    factory_related_name='category',
                                    parent=SelfAttribute('..type.plan.root_page'))


class CategoryMetadataRichTextFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryMetadataRichText'

    metadata = SubFactory(CategoryTypeMetadataFactory, format=CategoryTypeMetadata.MetadataFormat.RICH_TEXT)
    category = SubFactory(CategoryFactory)
    text = Sequence(lambda i: f'CategoryMetadataRichText {i}')


class CategoryMetadataChoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryMetadataChoice'

    metadata = SubFactory(CategoryTypeMetadataFactory, format=CategoryTypeMetadata.MetadataFormat.ORDERED_CHOICE)
    category = SubFactory(CategoryFactory)
    choice = SubFactory(CategoryTypeMetadataChoiceFactory)


class CategoryLevelFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.CategoryLevel'

    type = SubFactory(CategoryTypeFactory)
    name = Sequence(lambda i: f"Category level name {i}")
    name_plural = Sequence(lambda i: f'Category level name plural {i}')


class ScenarioFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Scenario'

    plan = SubFactory(PlanFactory)
    name = Sequence(lambda i: f"Scenario {i}")
    identifier = Sequence(lambda i: f'scenario{i}')
    description = "Scenario description"


class ImpactGroupFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ImpactGroup'

    plan = SubFactory(PlanFactory)
    name = Sequence(lambda i: f"Impact group {i}")
    identifier = Sequence(lambda i: f'impact-group-{i}')
    parent = None
    weight = 1.0
    color = 'red'

    _action = RelatedFactory('actions.tests.factories.ImpactGroupActionFactory',
                             factory_related_name='group',
                             group__plan=SelfAttribute('..plan'))


class MonitoringQualityPointFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.MonitoringQualityPoint'

    name = Sequence(lambda i: f"Monitoring quality point {i}")
    description_yes = "Yes"
    description_no = "No"
    plan = SubFactory(PlanFactory)
    identifier = Sequence(lambda i: f'monitoring-quality-point-{i}')


class ActionFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.Action'

    plan = SubFactory(PlanFactory)
    name = Sequence(lambda i: f"Action {i}")
    identifier = Sequence(lambda i: f'action{i}')
    official_name = name
    description = "Action description"
    impact = SubFactory(ActionImpactFactory, plan=SelfAttribute('..plan'))
    status = SubFactory(ActionStatusFactory, plan=SelfAttribute('..plan'))
    implementation_phase = SubFactory(ActionImplementationPhaseFactory, plan=SelfAttribute('..plan'))
    completion = 99


class ActionTaskFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ActionTask'

    action = SubFactory(ActionFactory)
    name = Sequence(lambda i: f"Action task {i}")
    state = actions.models.ActionTask.NOT_STARTED
    comment = "Comment"
    due_at = '2020-01-01'
    completed_at = None
    completed_by = None
    # created_at = None  # Should be set automatically
    # modified_at = None  # Should be set automatically


class ImpactGroupActionFactory(DjangoModelFactory):
    class Meta:
        model = 'actions.ImpactGroupAction'

    group = SubFactory(ImpactGroupFactory)
    action = SubFactory(ActionFactory, plan=SelfAttribute('..group.plan'))
    impact = SubFactory(ActionImpactFactory, plan=SelfAttribute('..group.plan'))


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
