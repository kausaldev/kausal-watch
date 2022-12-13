# Generated by Django 3.2.13 on 2022-12-06 13:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0058_action_superseded_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='superseded_by',
            field=models.ForeignKey(blank=True, help_text='Set if this plan is superseded by another plan', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='superseded_plans', to='actions.plan', verbose_name='superseded by'),
        ),
    ]