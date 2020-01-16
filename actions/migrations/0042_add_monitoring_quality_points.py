# Generated by Django 2.2.9 on 2020-01-16 14:15

import aplans.utils
from django.db import migrations, models
import django.db.models.deletion
import parler.fields
import parler.models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0041_add_impact_group_color'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonitoringQualityPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='order')),
                ('identifier', aplans.utils.IdentifierField(max_length=50, validators=[aplans.utils.IdentifierValidator()], verbose_name='identifier')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='monitoring_quality_points', to='actions.Plan', verbose_name='plan')),
            ],
            options={
                'verbose_name': 'monitoring quality point',
                'verbose_name_plural': 'monitoring quality points',
                'ordering': ('plan', 'order'),
                'unique_together': {('plan', 'order')},
            },
            bases=(parler.models.TranslatableModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name='action',
            name='monitoring_quality_points',
            field=models.ManyToManyField(blank=True, editable=False, related_name='actions', to='actions.MonitoringQualityPoint'),
        ),
        migrations.CreateModel(
            name='MonitoringQualityPointTranslation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
                ('description_yes', models.CharField(max_length=200, verbose_name='description when action fulfills criteria')),
                ('description_no', models.CharField(max_length=200, verbose_name="description when action doesn't fulfill criteria")),
                ('master', parler.fields.TranslationsForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='actions.MonitoringQualityPoint')),
            ],
            options={
                'verbose_name': 'monitoring quality point Translation',
                'db_table': 'actions_monitoringqualitypoint_translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
                'unique_together': {('language_code', 'master')},
            },
            bases=(parler.models.TranslatedFieldsModelMixin, models.Model),
        ),
    ]
