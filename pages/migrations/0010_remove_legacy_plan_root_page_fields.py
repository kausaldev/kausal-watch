# Generated by Django 3.2.13 on 2022-11-07 09:00

import actions.blocks
from django.db import migrations, models
import wagtail.blocks
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0009_action_list_page_default_view'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='planrootpage',
            name='action_short_description',
        ),
        migrations.RemoveField(
            model_name='planrootpage',
            name='hero_content',
        ),
        migrations.RemoveField(
            model_name='planrootpage',
            name='indicator_short_description',
        ),
        migrations.AlterField(
            model_name='actionlistpage',
            name='default_view',
            field=models.CharField(choices=[('cards', 'Cards'), ('dashboard', 'Dashboard')], default='cards', help_text='Tab of the action list page that should be visible by default', max_length=30, verbose_name='default view'),
        ),
        migrations.AlterField(
            model_name='actionlistpage',
            name='details_main_bottom',
            field=wagtail.fields.StreamField([('official_name', wagtail.blocks.StructBlock([('field_label', wagtail.blocks.CharBlock(default='', help_text='What label should be used in the public UI for the official name', required=False)), ('caption', wagtail.blocks.CharBlock(default='', help_text='Description to show after the field content', required=False))], label='official name')), ('attribute', wagtail.blocks.StructBlock([('attribute_type', actions.blocks.ActionAttributeTypeChooserBlock(required=True))], label='Attribute')), ('categories', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(required=True))], label='Category')), ('lead_paragraph', actions.blocks.ActionLeadParagraphBlock()), ('description', actions.blocks.ActionDescriptionBlock()), ('links', actions.blocks.ActionLinksBlock()), ('tasks', actions.blocks.ActionTasksBlock()), ('merged_actions', actions.blocks.ActionMergedActionsBlock()), ('related_actions', actions.blocks.ActionRelatedActionsBlock()), ('related_indicators', actions.blocks.ActionRelatedIndicatorsBlock())], blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='actionlistpage',
            name='details_main_top',
            field=wagtail.fields.StreamField([('official_name', wagtail.blocks.StructBlock([('field_label', wagtail.blocks.CharBlock(default='', help_text='What label should be used in the public UI for the official name', required=False)), ('caption', wagtail.blocks.CharBlock(default='', help_text='Description to show after the field content', required=False))], label='official name')), ('attribute', wagtail.blocks.StructBlock([('attribute_type', actions.blocks.ActionAttributeTypeChooserBlock(required=True))], label='Attribute')), ('categories', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(required=True))], label='Category')), ('lead_paragraph', actions.blocks.ActionLeadParagraphBlock()), ('description', actions.blocks.ActionDescriptionBlock()), ('links', actions.blocks.ActionLinksBlock()), ('tasks', actions.blocks.ActionTasksBlock()), ('merged_actions', actions.blocks.ActionMergedActionsBlock()), ('related_actions', actions.blocks.ActionRelatedActionsBlock()), ('related_indicators', actions.blocks.ActionRelatedIndicatorsBlock())], blank=True, null=True),
        ),
    ]
