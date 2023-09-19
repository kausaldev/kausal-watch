from django.utils.translation import gettext_lazy as _
import graphene
from grapple.helpers import register_streamfield_block
from grapple.models import GraphQLField, GraphQLImage, GraphQLPage, GraphQLStreamfield, GraphQLString, GraphQLForeignKey
from grapple.registry import registry
from grapple.types.streamfield import ListBlock as GrappleListBlock, StructBlockItem
from uuid import UUID
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.embeds.embeds import get_embed

from actions.blocks import CategoryChooserBlock
from actions.models import Category


class ListBlockWithIncrementingChildIds(GrappleListBlock):
    def resolve_items(self, info, **kwargs):
        # Grapple's ListBlock uses self.id also as IDs for the child blocks. We override this to make them unique.
        # FIXME: This causes problems if we rely on the IDs for anything else except uniqueness.
        block_type = self.block.child_block
        id = UUID(self.id).int
        result = []
        for item in self.value:
            id += 1
            result.append(StructBlockItem(str(UUID(int=id)), block_type, item))
        return result


registry.streamfield_blocks.update(
    {
        blocks.ListBlock: ListBlockWithIncrementingChildIds,
    }
)


@register_streamfield_block
class QuestionBlock(blocks.StructBlock):
    question = blocks.CharBlock(heading=_('Question'))
    answer = blocks.RichTextBlock(heading=_('Answer'))

    graphql_fields = [
        GraphQLString('question'),
        GraphQLString('answer'),
    ]


HEIGHTS = {
    'l': 800,
    'm': 600,
    's': 400
}


class EmbedHTMLValue(graphene.ObjectType):
    html = graphene.String()

    def resolve_html(parent, info):
        height_key = parent['height']
        url = parent['url']
        size = HEIGHTS.get(height_key, list(HEIGHTS.values())[0])
        embed = get_embed(url, max_height=size, max_width=size)
        return embed.html


@register_streamfield_block
class AdaptiveEmbedBlock(blocks.StructBlock):
    # Note: Do not try to use Wagtail's EmbedBlock here.
    # It doesn't support dynamic, configurable heights.
    # The extra inner field is just to enable the custom
    # resolve_html method
    embed = blocks.StructBlock(
        [('url', blocks.CharBlock()),
         ('height', blocks.ChoiceBlock(
             choices=[('s', _('small')), ('m', _('medium')), ('l', _('large'))]
         ))]
    )

    graphql_fields = [
        GraphQLField('embed', EmbedHTMLValue)
    ]


@register_streamfield_block
class QuestionAnswerBlock(blocks.StructBlock):
    heading = blocks.CharBlock(classname='title', heading=_('Title'), required=False)
    questions = blocks.ListBlock(QuestionBlock())

    graphql_fields = [
        GraphQLString('heading'),
        GraphQLStreamfield('questions'),
    ]


@register_streamfield_block
class FrontPageHeroBlock(blocks.StructBlock):
    layout = blocks.ChoiceBlock(choices=[
        ('big_image', _('Big image')),
        ('small_image', _('Small image')),
    ])
    image = ImageChooserBlock()
    heading = blocks.CharBlock(classname='full title', label=_('Heading'), required=False)
    lead = blocks.RichTextBlock(label=_('Lead'), required=False)

    graphql_fields = [
        GraphQLString('layout'),
        GraphQLImage('image'),
        GraphQLString('heading'),
        GraphQLString('lead'),
    ]


@register_streamfield_block
class PageLinkBlock(blocks.StructBlock):
    text = blocks.CharBlock(required=False)
    page = blocks.PageChooserBlock(required=False)
    # FIXME: `page` should be required, but so far the only use for PageLinkBlock is in IndicatorShowcaseBlock, where
    # the entire PageLinkBlock should be optional. It is, however, not easily possible to make a StructBlock optional:
    # https://github.com/wagtail/wagtail/issues/2665

    graphql_fields = [
        GraphQLString('text'),
        GraphQLPage('page'),
    ]


@register_streamfield_block
class CardBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    heading = blocks.CharBlock()
    content = blocks.CharBlock(required=False)
    # FIXME: We should also be able to choose internal pages
    link = blocks.CharBlock(required=False)

    graphql_fields = [
        GraphQLImage('image'),
        GraphQLString('heading'),
        GraphQLString('content'),
        GraphQLString('link'),
    ]


@register_streamfield_block
class CardListBlock(blocks.StructBlock):
    heading = blocks.CharBlock()
    lead = blocks.CharBlock(required=False)
    cards = blocks.ListBlock(CardBlock())

    graphql_fields = [
        GraphQLString('heading'),
        GraphQLString('lead'),
        GraphQLStreamfield('cards'),
    ]


@register_streamfield_block
class ActionCategoryFilterCardBlock(blocks.StructBlock):
    heading = blocks.CharBlock(label=_('Heading'))
    lead = blocks.CharBlock(label=_('Lead'))
    category = CategoryChooserBlock(label=_('Category'))
    graphql_fields = [
        GraphQLString('heading'),
        GraphQLString('lead'),
        GraphQLForeignKey('category', Category),
    ]


@register_streamfield_block
class ActionCategoryFilterCardsBlock(blocks.StructBlock):
    cards = blocks.ListBlock(ActionCategoryFilterCardBlock(), label=_('Links'))
    graphql_fields = [
        GraphQLStreamfield('cards')
    ]


@register_streamfield_block
class AccessibilityStatementComplianceStatusBlock(blocks.StaticBlock):
    pass


@register_streamfield_block
class AccessibilityStatementPreparationInformationBlock(blocks.StaticBlock):
    pass


@register_streamfield_block
class AccessibilityStatementContactInformationBlock(blocks.StructBlock):
    publisher_name = blocks.CharBlock(label=_('Publisher name'))
    maintenance_responsibility_paragraph = blocks.CharBlock(
        required=False, label=_('Maintenance responsibility paragraph'),
        help_text=_('If this is set, it will be displayed instead of "This service is published by [publisher]".')
    )
    email = blocks.CharBlock(label=_('Email address'))


@register_streamfield_block
class AccessibilityStatementContactFormBlock(blocks.StaticBlock):
    pass


@register_streamfield_block
class ActionStatusGraphsBlock(blocks.StaticBlock):
    pass
