# Generated by Django 3.2.16 on 2024-04-16 07:46

import actions.blocks.choosers
from django.db import migrations
import indicators.blocks
import kausal_watch_extensions.blocks
import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0032_auto_20240411_1306'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staticpage',
            name='body',
            field=wagtail.fields.StreamField([('paragraph', wagtail.blocks.RichTextBlock(label='Paragraph')), ('qa_section', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='title', heading='Title', required=False)), ('questions', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('question', wagtail.blocks.CharBlock(heading='Question')), ('answer', wagtail.blocks.RichTextBlock(heading='Answer'))])))], icon='help')), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(required=False)), ('category', actions.blocks.choosers.CategoryChooserBlock(required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')], label='Style'))])), ('indicator_group', wagtail.blocks.StructBlock([('title', wagtail.blocks.CharBlock(required=False)), ('indicators', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('indicator', indicators.blocks.IndicatorChooserBlock()), ('style', wagtail.blocks.ChoiceBlock(choices=[('graph', 'Graph'), ('progress', 'Progress'), ('animated', 'Animated')]))])))])), ('embed', wagtail.blocks.StructBlock([('embed', wagtail.blocks.StructBlock([('url', wagtail.blocks.CharBlock(label='URL')), ('height', wagtail.blocks.ChoiceBlock(choices=[('s', 'small'), ('m', 'medium'), ('l', 'large')], label='Size'))])), ('full_width', wagtail.blocks.BooleanBlock(required=False))])), ('category_tree_map', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(required=True)), ('value_attribute', actions.blocks.choosers.CategoryAttributeTypeChooserBlock(label='Value field', required=True))])), ('large_image', wagtail.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock(label='Image')), ('width', wagtail.blocks.ChoiceBlock(choices=[('maximum', 'Maximum'), ('fit_to_column', 'Fit to column')], label='Width'))])), ('cartography_visualisation_block', wagtail.blocks.StructBlock([('account', kausal_watch_extensions.blocks.CartographyProviderCredentialsChooserBlock(label='Map provider credentials')), ('style', wagtail.blocks.CharBlock(choices=[], label='Map style', required=True, validators=[])), ('style_overrides', wagtail.blocks.TextBlock(label='Map labels', required=False))], label='Map visualization'))], blank=True, null=True, use_json_field=True),
        ),
    ]
