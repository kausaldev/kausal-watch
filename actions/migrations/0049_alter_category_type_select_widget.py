# Generated by Django 3.2.13 on 2022-11-07 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0048_hide_identifiers_to_common_ct'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorytype',
            name='select_widget',
            field=models.CharField(choices=[('single', 'Single'), ('multiple', 'Multiple')], default='single', help_text='Choose "Multiple" only if more than one category can be selected at a time, otherwise choose "Single" which is the default.', max_length=30, verbose_name='single or multiple selection'),
        ),
        migrations.AlterField(
            model_name='commoncategorytype',
            name='select_widget',
            field=models.CharField(choices=[('single', 'Single'), ('multiple', 'Multiple')], default='single', help_text='Choose "Multiple" only if more than one category can be selected at a time, otherwise choose "Single" which is the default.', max_length=30, verbose_name='single or multiple selection'),
        ),
    ]