import json
import pytest
from django.urls import reverse

from actions.models import CategoryTypeMetadata
from pages.models import StaticPage


def expected_menu_item_for_page(page):
    return {
        'id': str(page.id),
        'linkText': page.title,
        'page': {
            # We strip the trailing slash of url_path in pages/apps.py
            'urlPath': page.url_path.rstrip('/'),
            'slug': page.slug,
        },
    }


def menu_query(menu_field='mainMenu', with_descendants=False):
    if with_descendants:
        with_descendants_str = 'true'
    else:
        with_descendants_str = 'false'
    return '''
        query($plan: ID!) {
          plan(id: $plan) {
            %(menu)s {
              items(withDescendants: %(with_descendants_str)s) {
                id
                linkText
                page {
                  urlPath
                  slug
                }
              }
            }
          }
        }
        ''' % {'menu': menu_field, 'with_descendants_str': with_descendants_str}


def add_menu_test_pages(root_page, menu_key='show_in_menus'):
    # Build hierarchy:
    # root_page
    #   page_not_in_menu
    #     subpage1_in_menu (should be shown if and only if we set the parameter `with_descendants` to true)
    #   page1_in_menu
    #     subpage_not_in_menu
    #     subpage2_in_menu (should be shown if and only if we set the parameter `with_descendants` to true)
    #   page2_in_menu
    pages = {}

    pages['page_not_in_menu'] = StaticPage(title="Page not in menu")
    root_page.add_child(instance=pages['page_not_in_menu'])

    pages['subpage1_in_menu'] = StaticPage(title="Subpage 1 in menu", **{menu_key: True})
    pages['page_not_in_menu'].add_child(instance=pages['subpage1_in_menu'])

    pages['page1_in_menu'] = StaticPage(title="Page 1 in menu", **{menu_key: True})
    root_page.add_child(instance=pages['page1_in_menu'])

    pages['subpage_not_in_menu'] = StaticPage(title="Subpage not in menu")
    pages['page1_in_menu'].add_child(instance=pages['subpage_not_in_menu'])

    pages['subpage2_in_menu'] = StaticPage(title="Subpage 2 in menu", **{menu_key: True})
    pages['page1_in_menu'].add_child(instance=pages['subpage2_in_menu'])

    pages['page2_in_menu'] = StaticPage(title="Page 2 in menu", **{menu_key: True})
    root_page.add_child(instance=pages['page2_in_menu'])

    return pages


@pytest.fixture
def suborganization(organization_factory, organization):
    return organization_factory(parent=organization)


@pytest.fixture
def another_organization(organization_factory):
    return organization_factory()


@pytest.mark.django_db
def test_nonexistent_domain(graphql_client_query_data):
    data = graphql_client_query_data(
        '''
        {
          plan(domain: "foo.localhost") {
            id
          }
        }
        ''',
    )
    assert data['plan'] is None


@pytest.mark.django_db
def test_plan_exists(graphql_client_query_data, plan):
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
          plan(id: $plan) {
            id
          }
        }
        ''',
        variables=dict(plan=plan.identifier)
    )
    assert data['plan']['id'] == plan.identifier


@pytest.mark.django_db
@pytest.mark.parametrize('plan__show_admin_link', [True, False])
def test_plan_admin_url(graphql_client_query_data, plan):
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
          plan(id: $plan) {
            adminUrl
          }
        }
        ''',
        variables=dict(plan=plan.identifier)
    )
    if plan.show_admin_link:
        admin_path = reverse('wagtailadmin_home')
        assert data == {'plan': {'adminUrl': f'http://testserver{admin_path}'}}
    else:
        assert data == {'plan': {'adminUrl': None}}


@pytest.mark.django_db
def test_categorytypes(graphql_client_query_data, plan, category_type, category_factory):
    c0 = category_factory(type=category_type)
    c1 = category_factory(type=category_type, parent=c0)
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
          plan(id: $plan) {
            categoryTypes {
              id
              identifier
              name
              usableForActions
              categories {
                id
                identifier
                name
                parent {
                  id
                }
              }
            }
          }
        }
        ''',
        variables=dict(plan=plan.identifier)
    )
    expected = {
        'plan': {
            'categoryTypes': [{
                'id': str(category_type.id),
                'identifier': category_type.identifier,
                'name': category_type.name,
                'usableForActions': category_type.usable_for_actions,
                'categories': [{
                    'id': str(c0.id),
                    'identifier': c0.identifier,
                    'name': c0.name,
                    'parent': None
                }, {
                    'id': str(c1.id),
                    'identifier': c1.identifier,
                    'name': c1.name,
                    'parent': {
                        'id': str(c0.id)
                    }
                }]
            }]
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_category_types(
    graphql_client_query_data, plan, category_type_factory, category_type_metadata_factory,
    category_type_metadata_choice_factory
):
    ct = category_type_factory(plan=plan)
    ctm1 = category_type_metadata_factory(type=ct)
    ctm2 = category_type_metadata_factory(type=ct, format=CategoryTypeMetadata.MetadataFormat.ORDERED_CHOICE)
    ctm2c1 = category_type_metadata_choice_factory(metadata=ctm2)
    ctm2c2 = category_type_metadata_choice_factory(metadata=ctm2)
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
            plan(id: $plan) {
                categoryTypes {
                    identifier
                    name
                    metadata {
                        format
                        identifier
                        name
                        choices {
                            identifier
                            name
                        }
                    }
                }
            }
        }
        ''',
        variables=dict(plan=plan.identifier)
    )
    expected = {
        'plan': {
            'categoryTypes': [{
                'identifier': ct.identifier,
                'name': ct.name,
                'metadata': [{
                    'format': 'RICH_TEXT',
                    'identifier': ctm1.identifier,
                    'name': ctm1.name,
                    'choices': [],
                }, {
                    'format': 'ORDERED_CHOICE',
                    'identifier': ctm2.identifier,
                    'name': ctm2.name,
                    'choices': [{
                        'identifier': ctm2c1.identifier,
                        'name': ctm2c1.name,
                    }, {
                        'identifier': ctm2c2.identifier,
                        'name': ctm2c2.name,
                    }],
                }],
            }]
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_plan_root_page_exists(graphql_client_query_data, plan):
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
          plan(id: $plan) {
            pages {
              ... on PlanRootPage {
                id
              }
            }
          }
        }
        ''',
        variables=dict(plan=plan.identifier)
    )
    pages = data['plan']['pages']
    assert len(pages) == 1
    page = pages[0]
    assert page['id'] == str(plan.root_page.id)


@pytest.mark.django_db
def test_plan_root_page_contains_block(graphql_client_query_data, plan):
    hero_data = {'layout': 'big_image', 'heading': 'foo', 'lead': 'bar'}
    plan.root_page.body = json.dumps([
        {'type': 'front_page_hero', 'value': hero_data},
    ])
    plan.root_page.save()
    data = graphql_client_query_data(
        '''
        query($plan: ID!) {
          plan(id: $plan) {
            pages {
              ... on PlanRootPage {
                body {
                  ... on FrontPageHeroBlock {
                    %s
                  }
                }
              }
            }
          }
        }
        ''' % " ".join(hero_data.keys()),
        variables=dict(plan=plan.identifier)
    )
    pages = data['plan']['pages']
    assert len(pages) == 1
    blocks = pages[0]['body']
    assert len(blocks) == 1
    block = blocks[0]
    for key, value in hero_data.items():
        assert block[key] == value


@pytest.mark.django_db
@pytest.mark.parametrize('menu_field,menu_key,with_descendants,expected_pages', [
    ('mainMenu', 'show_in_menus', False, ['page1_in_menu', 'page2_in_menu']),
    ('mainMenu', 'show_in_menus', True, ['subpage1_in_menu', 'page1_in_menu', 'subpage2_in_menu', 'page2_in_menu']),
    ('footer', 'show_in_footer', False, ['page1_in_menu', 'page2_in_menu']),
    ('footer', 'show_in_footer', True, ['subpage1_in_menu', 'page1_in_menu', 'subpage2_in_menu', 'page2_in_menu']),
])
def test_menu(graphql_client_query_data, plan, menu_field, menu_key, with_descendants, expected_pages):
    pages = add_menu_test_pages(plan.root_page, menu_key)
    data = graphql_client_query_data(
        menu_query(menu_field, with_descendants),
        variables=dict(plan=plan.identifier)
    )
    expected = {
        'plan': {
            menu_field: {
                'items': [expected_menu_item_for_page(pages[page_name]) for page_name in expected_pages]
            }
        }
    }
    assert data == expected