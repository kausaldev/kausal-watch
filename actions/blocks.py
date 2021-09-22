from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from grapple.helpers import register_streamfield_block
from grapple.models import GraphQLForeignKey, GraphQLString
from wagtail.core import blocks

from .chooser import CategoryChooser
from .models import Category


class CategoryChooserBlock(blocks.ChooserBlock):
    @cached_property
    def target_model(self):
        return Category

    @cached_property
    def widget(self):
        return CategoryChooser


@register_streamfield_block
class ActionHighlightsBlock(blocks.StaticBlock):
    pass


@register_streamfield_block
class ActionListBlock(blocks.StaticBlock):
    pass


@register_streamfield_block
class CategoryListBlock(blocks.StructBlock):
    heading = blocks.CharBlock(classname='full title', label=_('Heading'), required=False)
    lead = blocks.RichTextBlock(label=_('Lead'), required=False)
    style = blocks.ChoiceBlock(choices=[
        ('cards', _('Cards')),
        ('table', _('Table')),
        ('treemap', _('Tree map')),
    ])

    graphql_fields = [
        GraphQLString('heading'),
        GraphQLString('lead'),
        GraphQLString('style'),
    ]
