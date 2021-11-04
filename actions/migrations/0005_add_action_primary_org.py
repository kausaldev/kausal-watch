# Generated by Django 3.1.5 on 2021-11-04 06:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0003_auto_20210929_0049'),
        ('actions', '0004_add_category_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='primary_org',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='orgs.organization', verbose_name='primary organization'),
        ),
        migrations.AddField(
            model_name='plan',
            name='has_action_primary_orgs',
            field=models.BooleanField(default=False, help_text='Set if actions have a clear primary organisation', verbose_name='Has primary organisations for actions'),
        ),
    ]
