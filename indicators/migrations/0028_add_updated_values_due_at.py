# Generated by Django 3.1.5 on 2021-04-08 09:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('indicators', '0027_indicator_organization_not_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicator',
            name='updated_values_due_at',
            field=models.DateField(blank=True, null=True, verbose_name='updated values due at'),
        ),
    ]