# Generated by Django 3.2.13 on 2022-08-18 08:04

from django.db import migrations


def initialize_primary_action_classification(apps, schema_editor):
    CategoryType = apps.get_model('actions', 'CategoryType')
    for category_type in CategoryType.objects.filter(identifier='action'):
        plan = category_type.plan
        if plan.primary_action_classification is None:
            plan.primary_action_classification = category_type
        plan.save()


def clear_primary_action_classification(apps, schema_editor):
    Plan = apps.get_model('actions', 'Plan')
    for plan in Plan.objects.all():
        if plan.primary_action_classification is not None:
            plan.primary_action_classification = None
            plan.save()


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0035_add_plan_action_classification_settings'),
    ]

    operations = [
        migrations.RunPython(initialize_primary_action_classification, clear_primary_action_classification),
    ]