# Generated by Django 3.2.13 on 2023-01-11 20:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0064_remove_uuid_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='plandomain',
            name='publication_status_override',
            field=models.CharField(blank=True, choices=[('published', 'Published'), ('unpublished', 'Unpublished')], default=None, help_text='Only set this if you are sure you want to override the publication time set in the plan.Be aware that this will immediately change the publication status of the plan at this domain!', max_length=20, null=True, verbose_name='Immediate override of publishing status'),
        ),
    ]