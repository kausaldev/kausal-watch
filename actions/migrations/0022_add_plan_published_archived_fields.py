# Generated by Django 3.2.12 on 2022-04-13 05:38

from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0021_add_plan_theme_identifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='archived_at',
            field=models.DateTimeField(null=True, verbose_name='archived at'),
        ),
        migrations.AddField(
            model_name='plan',
            name='published_at',
            field=models.DateTimeField(null=True, verbose_name='published at'),
        ),
    ]
