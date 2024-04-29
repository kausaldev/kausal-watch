# Generated by Django 5.0.4 on 2024-07-05 12:39

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0126_plandomain_deployment_environment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="plandomain",
            name="redirect_aliases",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=80),
                blank=True,
                default=[],
                help_text="Domain names that will we used to redirect to the main hostname. Multiple domains are separated by commas.",
                size=None,
                verbose_name="redirect aliases",
            ),
        ),
    ]