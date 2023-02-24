# Generated by Django 3.2.13 on 2023-01-17 17:30

import aplans.utils
import datetime
from django.db import migrations, models
import django.db.models.deletion


def migrate_notification_settings(apps, schema_editor):
    NotificationSettings = apps.get_model('notifications', 'NotificationSettings')
    Plan = apps.get_model('actions', 'Plan')
    # This is the latest crontab from the previous commit's settings.py
    crontab = {
        'helsinki-kierto': {'hour': 7, 'minute': 40},
        'lahti-ilmasto': {'hour': 8, 'minute': 10},
        'viitasaari-ilmasto': {'hour': 8, 'minute': 40},
        'akaa-ilmasto':  {'hour': 8, 'minute': 55},
        'valkeakoski-ilmasto': {'hour': 9, 'minute': 10},
        'palkane-ilmasto': {'hour': 9, 'minute': 25},
        'urjala-ilmasto': {'hour': 9, 'minute': 40},
    }
    for plan in Plan.objects.all():
        create_kwargs = {}
        crontab_time = crontab.get(plan.identifier)
        if crontab_time:
            plan.timezone = 'Europe/Helsinki'
            plan.country = 'FI'
            plan.save()
            create_kwargs['notifications_enabled'] = True
            create_kwargs['send_at_time'] = datetime.time(crontab_time['hour'], crontab_time['minute'])
        NotificationSettings.objects.create(plan=plan, **create_kwargs)


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0067_country_and_timezone'),
        ('notifications', '0009_notification_preferences'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='basetemplate',
            options={'verbose_name': 'base template', 'verbose_name_plural': 'base templates'},
        ),
        migrations.CreateModel(
            name='NotificationSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notifications_enabled', models.BooleanField(default=False, help_text='Should notifications be sent?', verbose_name='notifications enabled')),
                ('send_at_time', models.TimeField(default=datetime.time(9, 0), help_text='The local time of day when notifications are sent', verbose_name='notification sending time')),
                ('plan', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_settings', to='actions.plan', verbose_name='plan')),
            ],
            options={
                'verbose_name': 'notification settings',
                'verbose_name_plural': 'notification settings',
            },
            bases=(models.Model, aplans.utils.PlanRelatedModel),
        ),
        migrations.RunPython(migrate_notification_settings, reverse_code=migrations.RunPython.noop),
    ]