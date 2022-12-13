# Generated by Django 3.2.13 on 2022-12-07 20:44

from django.db import migrations, models


def set_show_action_identifiers(apps, schema_editor):
    model = apps.get_model('actions', 'PlanFeatures')
    model.objects.all().update(show_action_identifiers=models.F('has_action_identifiers'))


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0059_plan_superseded_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='planfeatures',
            name='show_action_identifiers',
            field=models.BooleanField(default=True, help_text='Set if action identifiers should be visible in the public UI', verbose_name='Show action identifiers'),
        ),
        migrations.RunPython(set_show_action_identifiers, migrations.RunPython.noop)
    ]