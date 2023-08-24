# Generated by Django 3.2.13 on 2023-03-24 13:26

import actions.blocks.choosers
from django.db import migrations, models
import wagtail.blocks
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0020_modify_page_streamfields'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlistpage',
            name='include_related_plans',
            field=models.BooleanField(default=False, help_text='Enable to make this page include actions from related plans.', verbose_name='Include related plans'),
        ),
        migrations.AlterField(
            model_name='staticpage',
            name='body',
            field=wagtail.fields.StreamField([('paragraph', wagtail.blocks.RichTextBlock(label='Paragraph')), ('qa_section', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='title', heading='Title', required=False)), ('questions', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('question', wagtail.blocks.CharBlock(heading='Question')), ('answer', wagtail.blocks.RichTextBlock(heading='Answer'))])))], icon='help', label='Questions & Answers')), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(label='Category type', required=False)), ('category', actions.blocks.choosers.CategoryChooserBlock(label='Category', required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')]))], label='Category list')), ('category_tree_map', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(label='Category type', required=True)), ('value_attribute', actions.blocks.choosers.CategoryAttributeTypeChooserBlock(label='Value attribute', required=True))], label='Category tree map')), ('cartography_visualisation_block', wagtail.blocks.StructBlock([('style', wagtail.blocks.CharBlock(choices=[], label='Map style', required=True, validators=[])), ('style_overrides', wagtail.blocks.TextBlock(label='Map labels', required=False))], label='Map Visualisation'))], blank=True, null=True),
        ),
    ]
