import json
import pytest
from graphene_django.utils.testing import graphql_query
from pytest_factoryboy import LazyFixture, register

from actions.tests import factories as actions_factories
from content.tests import factories as content_factories
from users.tests import factories as users_factories
from people.tests import factories as people_factories

register(actions_factories.ActionContactFactory, 'action_contact')
register(actions_factories.ActionFactory)
register(actions_factories.ActionScheduleFactory)
register(actions_factories.ActionStatusFactory)
register(actions_factories.ActionImplementationPhaseFactory)
register(actions_factories.ActionImpactFactory)
register(actions_factories.ActionResponsiblePartyFactory)
register(actions_factories.CategoryFactory)
register(actions_factories.CategoryTypeMetadataFactory)
register(actions_factories.OrganizationFactory)
register(actions_factories.PlanFactory)
register(content_factories.SiteGeneralContentFactory)
register(people_factories.PersonFactory)
register(users_factories.UserFactory)
register(users_factories.UserFactory, 'superuser', is_superuser=True)
register(users_factories.UserFactory, 'plan_admin_user', general_admin_plans=LazyFixture(lambda plan: [plan]))


@pytest.fixture
def graphql_client_query(client):
    def func(*args, **kwargs):
        return graphql_query(*args, **kwargs, client=client, graphql_url='/v1/graphql/')
    return func


@pytest.fixture
def graphql_client_query_data(graphql_client_query):
    """Make a GraphQL request, make sure the `error` field is not present and return the `data` field."""
    def func(*args, **kwargs):
        response = graphql_client_query(*args, **kwargs)
        content = json.loads(response.content)
        assert 'errors' not in content
        return content['data']
    return func
