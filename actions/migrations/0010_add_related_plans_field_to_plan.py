# Generated by Django 3.2.12 on 2022-02-19 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0009_update_languages'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='related_plans',
            field=models.ManyToManyField(blank=True, related_name='_actions_plan_related_plans_+', to='actions.Plan'),
        ),
    ]