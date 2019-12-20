# Generated by Django 2.2.8 on 2019-12-20 12:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0035_migrate_actiontask_states'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='merged_with',
            field=models.ForeignKey(blank=True, help_text='Set if this action is merged with another action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merged_actions', to='actions.Action', verbose_name='merged with action'),
        ),
    ]
