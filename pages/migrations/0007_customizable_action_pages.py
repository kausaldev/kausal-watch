# Generated by Django 3.2.13 on 2022-09-19 18:28

import actions.blocks
from django.db import migrations, models
import django.db.models.deletion
import indicators.blocks
import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0040_make_help_text_optional'),
        ('pages', '0006_alter_planrootpage_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlistpage',
            name='advanced_filters',
            field=wagtail.fields.StreamField([], blank=True, null=True),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='card_icon_category_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='actions.categorytype'),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='details_aside',
            field=wagtail.fields.StreamField([], blank=True, null=True),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='details_main_bottom',
            field=wagtail.fields.StreamField([('attribute_type', actions.blocks.AttributeTypeChooserBlock(label='Attribute', required=True)), ('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category', required=True)), ('lead_paragraph', actions.blocks.ActionLeadParagraphBlock()), ('description', actions.blocks.ActionDescriptionBlock()), ('official_name', actions.blocks.ActionOfficialNameBlock()), ('links', actions.blocks.ActionLinksBlock()), ('tasks', actions.blocks.ActionTasksBlock()), ('merged_actions', actions.blocks.ActionMergedActionsBlock()), ('related_actions', actions.blocks.ActionRelatedActionsBlock()), ('related_indicators', actions.blocks.ActionRelatedIndicatorsBlock())], blank=True, null=True),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='details_main_top',
            field=wagtail.fields.StreamField([('attribute_type', actions.blocks.AttributeTypeChooserBlock(label='Attribute', required=True)), ('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category', required=True)), ('lead_paragraph', actions.blocks.ActionLeadParagraphBlock()), ('description', actions.blocks.ActionDescriptionBlock()), ('official_name', actions.blocks.ActionOfficialNameBlock()), ('links', actions.blocks.ActionLinksBlock()), ('tasks', actions.blocks.ActionTasksBlock()), ('merged_actions', actions.blocks.ActionMergedActionsBlock()), ('related_actions', actions.blocks.ActionRelatedActionsBlock()), ('related_indicators', actions.blocks.ActionRelatedIndicatorsBlock())], blank=True, null=True),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='main_filters',
            field=wagtail.fields.StreamField([], blank=True, null=True),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='primary_filters',
            field=wagtail.fields.StreamField([], blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='categorypage',
            name='body',
            field=wagtail.fields.StreamField([('text', wagtail.blocks.RichTextBlock(label='Text')), ('indicator_group', indicators.blocks.IndicatorGroupBlock()), ('related_indicators', indicators.blocks.RelatedIndicatorsBlock()), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')]))], label='Category list')), ('action_list', wagtail.blocks.StructBlock([('category_filter', actions.blocks.CategoryChooserBlock(label='Filter on category'))], label='Action list'))], blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='planrootpage',
            name='body',
            field=wagtail.fields.StreamField([('front_page_hero', wagtail.blocks.StructBlock([('layout', wagtail.blocks.ChoiceBlock(choices=[('big_image', 'Big image'), ('small_image', 'Small image')])), ('image', wagtail.images.blocks.ImageChooserBlock()), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading')), ('lead', wagtail.blocks.RichTextBlock(label='Lead'))], label='Front page hero block')), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')]))], label='Category list')), ('indicator_group', indicators.blocks.IndicatorGroupBlock()), ('indicator_highlights', indicators.blocks.IndicatorHighlightsBlock(label='Indicator highlights')), ('indicator_showcase', wagtail.blocks.StructBlock([('title', wagtail.blocks.CharBlock(required=False)), ('body', wagtail.blocks.RichTextBlock(required=False)), ('indicator', indicators.blocks.IndicatorChooserBlock()), ('link_button', wagtail.blocks.StructBlock([('text', wagtail.blocks.CharBlock(required=False)), ('page', wagtail.blocks.PageChooserBlock(required=False))]))])), ('action_highlights', actions.blocks.ActionHighlightsBlock(label='Action highlights')), ('related_plans', actions.blocks.RelatedPlanListBlock(label='Related plans')), ('cards', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock()), ('lead', wagtail.blocks.CharBlock(required=False)), ('cards', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock(required=False)), ('heading', wagtail.blocks.CharBlock()), ('content', wagtail.blocks.CharBlock(required=False)), ('link', wagtail.blocks.CharBlock(required=False))])))])), ('action_links', wagtail.blocks.StructBlock([('cards', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(label='Heading')), ('lead', wagtail.blocks.CharBlock(label='Lead')), ('category', actions.blocks.CategoryChooserBlock(label='Category'))]), label='Links'))], label='Links to actions in specific category'))]),
        ),
        migrations.AlterField(
            model_name='staticpage',
            name='body',
            field=wagtail.fields.StreamField([('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading')), ('paragraph', wagtail.blocks.RichTextBlock(label='Paragraph')), ('qa_section', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='title', heading='Title', required=False)), ('questions', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('question', wagtail.blocks.CharBlock(heading='Question')), ('answer', wagtail.blocks.RichTextBlock(heading='Answer'))])))], icon='help', label='Questions & Answers')), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')]))], label='Category list')), ('category_tree_map', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=True)), ('value_attribute', actions.blocks.AttributeTypeChooserBlock(label='Value attribute', required=True))], label='Category tree map'))], blank=True, null=True),
        ),
    ]
