# Generated by Django 3.2.13 on 2022-12-19 15:34

import actions.blocks
import django.core.validators
from django.db import migrations, models
import pages.blocks
import wagtail.blocks
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0016_fill_maintenance_responsibility_paragraph'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlistpage',
            name='heading_hierarchy_depth',
            field=models.IntegerField(default=1, help_text='Depth of category hierarchy to present as subheadings starting from the root.', validators=[django.core.validators.MinValueValidator(1)], verbose_name='Subheading hierarchy depth'),
        ),
        migrations.AlterField(
            model_name='accessibilitystatementpage',
            name='body',
            field=wagtail.fields.StreamField([('text', wagtail.blocks.RichTextBlock(label='Text')), ('compliance_status', pages.blocks.AccessibilityStatementComplianceStatusBlock()), ('preparation', pages.blocks.AccessibilityStatementPreparationInformationBlock()), ('contact_information', wagtail.blocks.StructBlock([('publisher_name', wagtail.blocks.CharBlock(label='Publisher name')), ('maintenance_responsibility_paragraph', wagtail.blocks.CharBlock(help_text='If this is set, it will be displayed instead of "This service is published by [publisher]."', label='Maintenance responsibility paragraph', required=False)), ('email', wagtail.blocks.CharBlock(label='Email address'))])), ('contact_form', pages.blocks.AccessibilityStatementContactFormBlock())], blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='accessibilitystatementpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='actionlistpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='categorypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='emptypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='impactgrouppage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='indicatorlistpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='planrootpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='privacypolicypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
        migrations.AlterField(
            model_name='staticpage',
            name='body',
            field=wagtail.fields.StreamField([('paragraph', wagtail.blocks.RichTextBlock(label='Paragraph')), ('qa_section', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='title', heading='Title', required=False)), ('questions', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('question', wagtail.blocks.CharBlock(heading='Question')), ('answer', wagtail.blocks.RichTextBlock(heading='Answer'))])))], icon='help', label='Questions & Answers')), ('category_list', wagtail.blocks.StructBlock([('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=False)), ('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table')]))], label='Category list')), ('category_tree_map', wagtail.blocks.StructBlock([('heading', wagtail.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.blocks.RichTextBlock(label='Lead', required=False)), ('category_type', actions.blocks.CategoryTypeChooserBlock(label='Category type', required=True)), ('value_attribute', actions.blocks.CategoryAttributeTypeChooserBlock(label='Value attribute', required=True))], label='Category tree map'))], blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='staticpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, help_text='Should subpages of this page use secondary navigation?', verbose_name='children use secondary navigation'),
        ),
    ]
