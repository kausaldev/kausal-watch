# Generated by Django 3.2.12 on 2022-04-25 09:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_organization_i18n'),
        ('actions', '0024_generic_attributes'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='actions.plan', verbose_name='parent'),
        ),
        migrations.AlterField(
            model_name='plan',
            name='archived_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='archived at'),
        ),
        migrations.AlterField(
            model_name='plan',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='published at'),
        ),
        migrations.AlterField(
            model_name='planfeatures',
            name='allow_images_for_actions',
            field=models.BooleanField(default=True, help_text='Should custom images for individual actions be allowed', verbose_name='Allow images for actions'),
        ),
        migrations.AlterField(
            model_name='planfeatures',
            name='has_action_identifiers',
            field=models.BooleanField(default=True, help_text='Set if the plan uses meaningful action identifiers', verbose_name='Has action identifiers'),
        ),
        migrations.AlterField(
            model_name='planfeatures',
            name='has_action_lead_paragraph',
            field=models.BooleanField(default=True, help_text='Set if the plan uses the lead paragraph field', verbose_name='Has action lead paragraph'),
        ),
        migrations.AlterField(
            model_name='planfeatures',
            name='has_action_official_name',
            field=models.BooleanField(default=False, help_text='Set if the plan uses the official name field', verbose_name='Has action official name field'),
        ),
        migrations.AlterField(
            model_name='planfeatures',
            name='show_admin_link',
            field=models.BooleanField(default=False, help_text='Should the public website contain a link to the admin login?', verbose_name='Show admin link'),
        ),
    ]