# Generated by Django 3.2.13 on 2022-09-14 12:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0039_add_help_text_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attributetype',
            name='help_text',
            field=models.TextField(blank=True, verbose_name='help text'),
        ),
        migrations.AlterField(
            model_name='category',
            name='help_text',
            field=models.TextField(blank=True, verbose_name='help text'),
        ),
        migrations.AlterField(
            model_name='categorytype',
            name='help_text',
            field=models.TextField(blank=True, verbose_name='help text'),
        ),
        migrations.AlterField(
            model_name='commoncategory',
            name='help_text',
            field=models.TextField(blank=True, verbose_name='help text'),
        ),
        migrations.AlterField(
            model_name='commoncategorytype',
            name='help_text',
            field=models.TextField(blank=True, verbose_name='help text'),
        ),
    ]