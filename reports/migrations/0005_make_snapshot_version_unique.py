# Generated by Django 3.2.16 on 2023-12-19 12:28

import actions.blocks.choosers
from django.db import migrations
import reports.blocks.action_content
import wagtail.blocks
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('reversion', '0002_add_index_on_version_for_content_type_and_db'),
        ('reports', '0004_alter_report_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='report',
            name='fields',
            field=wagtail.fields.StreamField([('implementation_phase', reports.blocks.action_content.ActionImplementationPhaseReportFieldBlock()), ('attribute_type', wagtail.blocks.StructBlock([('attribute_type', actions.blocks.choosers.ActionAttributeTypeChooserBlock(required=True))])), ('responsible_party', wagtail.blocks.StructBlock([('target_ancestor_depth', wagtail.blocks.IntegerBlock(help_text="In addition to the organization itself, an organizational unit containing the organization is included in the report. Counting from the top-level root organisation at level 1, which level in the organizational hierarchy should be used to find this containing organization? If left empty, don't add the containing organization to the report.", label='Level of containing organization', max_value=10, min_value=1, required=False))])), ('category', wagtail.blocks.StructBlock([('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(required=True)), ('category_level', actions.blocks.choosers.CategoryLevelChooserBlock(required=False))])), ('status', reports.blocks.action_content.ActionStatusReportFieldBlock())], blank=True, null=True, use_json_field=True),
        ),
        migrations.AlterField(
            model_name='reporttype',
            name='fields',
            field=wagtail.fields.StreamField([('implementation_phase', reports.blocks.action_content.ActionImplementationPhaseReportFieldBlock()), ('attribute_type', wagtail.blocks.StructBlock([('attribute_type', actions.blocks.choosers.ActionAttributeTypeChooserBlock(required=True))])), ('responsible_party', wagtail.blocks.StructBlock([('target_ancestor_depth', wagtail.blocks.IntegerBlock(help_text="In addition to the organization itself, an organizational unit containing the organization is included in the report. Counting from the top-level root organisation at level 1, which level in the organizational hierarchy should be used to find this containing organization? If left empty, don't add the containing organization to the report.", label='Level of containing organization', max_value=10, min_value=1, required=False))])), ('category', wagtail.blocks.StructBlock([('category_type', actions.blocks.choosers.CategoryTypeChooserBlock(required=True)), ('category_level', actions.blocks.choosers.CategoryLevelChooserBlock(required=False))])), ('status', reports.blocks.action_content.ActionStatusReportFieldBlock())], blank=True, null=True, use_json_field=True),
        ),
        migrations.AlterUniqueTogether(
            name='actionsnapshot',
            unique_together={('report', 'action_version')},
        ),
    ]
