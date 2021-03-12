import pytest

from pages.models import CategoryPage

MULTI_USE_IMAGE_FRAGMENT = '''
    fragment MultiUseImageFragment on Image {
      title
      width
      height
      focalPointX
      focalPointY
      rendition(size:"300x200") {
        width
        height
        src
      }
    }
    '''

STREAMFIELD_FRAGMENT = '''
    fragment StreamFieldFragment on StreamFieldInterface {
      id
      blockType
      field
      ... on CharBlock {
        value
      }
      ... on TextBlock {
        value
      }
      ... on RichTextBlock {
        value
      }
      ... on ChoiceBlock {
        value
        choices {
          key
          value
        }
      }
      ...on QuestionAnswerBlock {
        heading
        questions {
          ... on QuestionBlock {
            question
            answer
          }
        }
      }
      ... on IndicatorBlock {
        style
        indicator {
          id
        }
      }
      ... on IndicatorGroupBlock {
        id
        blockType
        rawValue
        items {
          ... on IndicatorBlock {
            id
            style
            indicator {
              id
              identifier
              name
              unit {
                id
                name
              }
              description
              timeResolution
              latestValue {
                id
                date
                value
              }
              goals {
                id
                date
                value
              }
              level(plan: $plan)
            }
          }
        }
      }
      ... on ActionListBlock {
        categoryFilter {
          id
        }
      }
      ... on CategoryListBlock {
        style
      }
      ... on FrontPageHeroBlock {
        id
        layout
        image {
          ...MultiUseImageFragment
        }
        heading
        lead
      }
      ... on IndicatorShowcaseBlock {
        id
        blockType
        field
        rawValue
        blocks {
          __typename
        }
        title
        body
        indicator {
          id
          identifier
          name
          unit {
            id
            shortName
          }
          minValue
          maxValue
          latestValue {
            date
            value
          }
          values {
            date
            value
          }
          goals {
            date
            value
          }
        }
        linkButton {
          blockType
          ... on PageLinkBlock {
            text
            page {
              url
              urlPath
              slug
            }
          }

        }
      }
      ... on CardListBlock {
        id
        heading
        lead
        cards {
          ... on CardBlock {
            image {
              ...MultiUseImageFragment
            }
            heading
            content
            link
          }
        }
      }
      ... on ActionHighlightsBlock {
        field
      }
      ... on IndicatorHighlightsBlock {
        field
      }
    }
    '''


@pytest.mark.django_db
def test_plan_root_page(graphql_client_query_data, plan, front_page_hero_block):
    page = plan.root_page
    page.body = [
        ('front_page_hero', front_page_hero_block),
        # ('category_list', None),  # TODO
        # ('indicator_group', None),  # TODO
        # ('indicator_highlights', None),  # TODO
        # ('indicator_showcase', None),  # TODO
        # ('action_highlights', None),  # TODO
        # ('cards', None),  # TODO
    ]
    page.save()
    data = graphql_client_query_data(
        '''
        query($plan: ID!, $path: String!) {
          planPage(plan: $plan, path: $path) {
            id
            slug
            title
            ... on PlanRootPage {
              body {
                ...StreamFieldFragment
              }
            }
          }
        }
        ''' + STREAMFIELD_FRAGMENT + MULTI_USE_IMAGE_FRAGMENT,
        variables={
            'plan': plan.identifier,
            'path': '/',
        }
    )
    expected = {
        'planPage': {
            'id': str(page.id),
            'slug': page.slug,
            'title': page.title,
            'body': [{
                'id': page.body[0].id,
                'blockType': 'FrontPageHeroBlock',
                'field': 'front_page_hero',
                'heading': front_page_hero_block['heading'],
                'image': {
                    'title': front_page_hero_block['image'].title,
                    'focalPointX': None,
                    'focalPointY': None,
                    'width': front_page_hero_block['image'].width,
                    'height': front_page_hero_block['image'].height,
                    'rendition': {
                        'width': front_page_hero_block['image'].get_rendition('fill-300x200-c50').width,
                        'height': front_page_hero_block['image'].get_rendition('fill-300x200-c50').height,
                        'src': ('http://testserver'
                                + front_page_hero_block['image'].get_rendition('fill-300x200-c50').url),
                    },
                },
                'layout': 'big_image',
                'lead': str(front_page_hero_block['lead']),
            }],
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_static_page(graphql_client_query_data, plan, static_page):
    data = graphql_client_query_data(
        '''
        query($plan: ID!, $path: String!) {
          planPage(plan: $plan, path: $path) {
            id
            slug
            title
            ... on StaticPage {
              leadParagraph
            }
          }
        }
        ''',
        variables={
            'plan': plan.identifier,
            'path': static_page.url_path,
        }
    )
    expected = {
        'planPage': {
            'id': str(static_page.id),
            'slug': static_page.slug,
            'title': static_page.title,
            'leadParagraph': static_page.lead_paragraph,
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_static_page_body(graphql_client_query_data, plan, static_page):
    data = graphql_client_query_data(
        '''
        query($plan: ID!, $path: String!) {
          planPage(plan: $plan, path: $path) {
            ... on StaticPage {
              body {
                ...StreamFieldFragment
              }
            }
          }
        }
        ''' + STREAMFIELD_FRAGMENT + MULTI_USE_IMAGE_FRAGMENT,
        variables={
            'plan': plan.identifier,
            'path': static_page.url_path,
        }
    )
    expected = {
        'planPage': {
            'body': [{
                'blockType': 'CharBlock',
                'field': 'heading',
                'id': static_page.body[0].id,
                'value': static_page.body[0].value,
            }, {
                'blockType': 'RichTextBlock',
                'field': 'paragraph',
                'id': static_page.body[1].id,
                # FIXME: The newline is added by grapple in RichTextBlock.resolve_value()
                'value': f'{static_page.body[1].value}\n',
            }, {
                'blockType': 'QuestionAnswerBlock',
                'field': 'qa_section',
                'heading': static_page.body[2].value['heading'],
                'id': static_page.body[2].id,
                'questions': [{
                    'question': static_page.body[2].value['questions'][0]['question'],
                    'answer': str(static_page.body[2].value['questions'][0]['answer']),
                }],
            }],
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_static_page_header_image(graphql_client_query_data, plan, static_page):
    data = graphql_client_query_data(
        '''
        query($plan: ID!, $path: String!) {
          planPage(plan: $plan, path: $path) {
            ... on StaticPage {
              headerImage {
                ...MultiUseImageFragment
              }
            }
          }
        }
        ''' + MULTI_USE_IMAGE_FRAGMENT,
        variables={
            'plan': plan.identifier,
            'path': static_page.url_path,
        }
    )
    expected = {
        'planPage': {
            'headerImage': {
                'title': static_page.header_image.title,
                'focalPointX': None,
                'focalPointY': None,
                'width': static_page.header_image.width,
                'height': static_page.header_image.height,
                'rendition': {
                    'width': static_page.header_image.get_rendition('fill-300x200-c50').width,
                    'height': static_page.header_image.get_rendition('fill-300x200-c50').height,
                    'src': 'http://testserver' + static_page.header_image.get_rendition('fill-300x200-c50').url,
                },
            },
        }
    }
    assert data == expected


@pytest.mark.django_db
def test_categorymetadata_order_as_in_categorytypemetadata(
    graphql_client_query_data, plan, category, category_type, category_type_metadata_factory,
    category_metadata_rich_text_factory
):
    ctm0 = category_type_metadata_factory(type=category_type)
    ctm1 = category_type_metadata_factory(type=category_type)
    assert ctm0.order < ctm1.order
    cmrt0 = category_metadata_rich_text_factory(metadata=ctm0, category=category)
    cmrt1 = category_metadata_rich_text_factory(metadata=ctm1, category=category)
    category_page = CategoryPage(title='Category', slug='category-slug', category=category)
    plan.root_page.add_child(instance=category_page)

    query = '''
        query($plan: ID!, $path: String!) {
          planPage(plan: $plan, path: $path) {
            ... on CategoryPage {
              category {
                metadata {
                  ... on CategoryMetadataRichText {
                    keyIdentifier
                    value
                  }
                }
              }
            }
          }
        }
        '''
    query_variables = {
        'plan': category_page.category.type.plan.identifier,
        'path': f'/{category.identifier}-category-slug',
    }
    expected = {
        'planPage': {
            'category': {
                'metadata': [{
                    'keyIdentifier': ctm0.identifier,
                    'value': cmrt0.text,
                }, {
                    'keyIdentifier': ctm1.identifier,
                    'value': cmrt1.text,
                }],
            }
        }
    }
    data = graphql_client_query_data(query, variables=query_variables)
    assert data == expected

    ctm0.order, ctm1.order = ctm1.order, ctm0.order
    ctm0.save()
    ctm1.save()
    expected_metadata = expected['planPage']['category']['metadata']
    expected_metadata[0], expected_metadata[1] = expected_metadata[1], expected_metadata[0]
    data = graphql_client_query_data(query, variables=query_variables)
    assert data == expected
