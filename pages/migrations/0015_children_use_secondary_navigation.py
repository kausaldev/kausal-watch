# Generated by Django 3.2.13 on 2022-12-06 12:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0014_remove_heading_block_from_staticpage_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessibilitystatementpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='actionlistpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='categorypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='emptypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='impactgrouppage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='indicatorlistpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='planrootpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='privacypolicypage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
        migrations.AddField(
            model_name='staticpage',
            name='children_use_secondary_navigation',
            field=models.BooleanField(default=False, verbose_name='children use secondary navigation'),
        ),
    ]