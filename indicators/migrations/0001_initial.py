# Generated by Django 3.1.5 on 2021-09-28 21:37

import aplans.utils
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields
import modeltrans.fields
import wagtail.core.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('actions', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActionIndicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('effect_type', models.CharField(choices=[('increases', 'increases'), ('decreases', 'decreases')], help_text='What type of effect should the action cause?', max_length=40, verbose_name='effect type')),
                ('indicates_action_progress', models.BooleanField(default=False, help_text='Set if the indicator should be used to determine action progress', verbose_name='indicates action progress')),
            ],
            options={
                'verbose_name': 'action indicator',
                'verbose_name_plural': 'action indicators',
            },
        ),
        migrations.CreateModel(
            name='CommonIndicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', aplans.utils.IdentifierField(max_length=50, validators=[aplans.utils.IdentifierValidator()], verbose_name='identifier')),
                ('name', models.CharField(max_length=200, verbose_name='name')),
                ('description', wagtail.core.fields.RichTextField(blank=True, null=True, verbose_name='description')),
                ('i18n', modeltrans.fields.TranslationField(fields=['name', 'description'], required_languages=(), virtual_fields=True)),
            ],
            options={
                'verbose_name': 'common indicator',
                'verbose_name_plural': 'common indicators',
            },
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('url', models.URLField(blank=True, null=True, verbose_name='URL')),
                ('last_retrieved_at', models.DateField(blank=True, null=True, verbose_name='last retrieved at')),
                ('owner_name', models.CharField(blank=True, help_text='Set if owner organization is not available', max_length=100, null=True, verbose_name='owner name')),
            ],
            options={
                'verbose_name': 'dataset',
                'verbose_name_plural': 'datasets',
            },
        ),
        migrations.CreateModel(
            name='DatasetLicense',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='name')),
            ],
            options={
                'verbose_name': 'dataset license',
                'verbose_name_plural': 'dataset licenses',
            },
        ),
        migrations.CreateModel(
            name='Dimension',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
            ],
            options={
                'verbose_name': 'dimension',
                'verbose_name_plural': 'dimensions',
            },
        ),
        migrations.CreateModel(
            name='DimensionCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='order')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
            ],
            options={
                'verbose_name': 'dimension category',
                'verbose_name_plural': 'dimension categories',
                'ordering': ['dimension', 'order'],
            },
        ),
        migrations.CreateModel(
            name='Framework',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='name')),
                ('i18n', modeltrans.fields.TranslationField(fields=['name'], required_languages=(), virtual_fields=True)),
            ],
            options={
                'verbose_name': 'framework',
                'verbose_name_plural': 'frameworks',
            },
        ),
        migrations.CreateModel(
            name='FrameworkIndicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', aplans.utils.IdentifierField(blank=True, max_length=50, null=True, validators=[aplans.utils.IdentifierValidator()], verbose_name='identifier')),
            ],
            options={
                'verbose_name': 'framework indicator',
                'verbose_name_plural': 'framework indicators',
            },
        ),
        migrations.CreateModel(
            name='Indicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', aplans.utils.IdentifierField(blank=True, max_length=50, null=True, validators=[aplans.utils.IdentifierValidator()], verbose_name='identifier')),
                ('name', models.CharField(max_length=200, verbose_name='name')),
                ('min_value', models.FloatField(blank=True, help_text='What is the minimum value this indicator can reach? It is used in visualizations as the Y axis minimum.', null=True, verbose_name='minimum value')),
                ('max_value', models.FloatField(blank=True, help_text='What is the maximum value this indicator can reach? It is used in visualizations as the Y axis maximum.', null=True, verbose_name='maximum value')),
                ('description', wagtail.core.fields.RichTextField(blank=True, null=True, verbose_name='description')),
                ('time_resolution', models.CharField(choices=[('year', 'year'), ('month', 'month'), ('week', 'week'), ('day', 'day')], default='year', max_length=50, verbose_name='time resolution')),
                ('updated_values_due_at', models.DateField(blank=True, null=True, verbose_name='updated values due at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
            ],
            options={
                'verbose_name': 'indicator',
                'verbose_name_plural': 'indicators',
                'ordering': ('-updated_at',),
            },
        ),
        migrations.CreateModel(
            name='Quantity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40, unique=True, verbose_name='name')),
            ],
            options={
                'verbose_name': 'quantity',
                'verbose_name_plural': 'quantities',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40, unique=True, verbose_name='name')),
                ('short_name', models.CharField(blank=True, max_length=40, null=True, verbose_name='short name')),
                ('verbose_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='verbose name')),
                ('verbose_name_plural', models.CharField(blank=True, max_length=100, null=True, verbose_name='verbose name plural')),
            ],
            options={
                'verbose_name': 'unit',
                'verbose_name_plural': 'units',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='RelatedIndicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('effect_type', models.CharField(choices=[('increases', 'increases'), ('decreases', 'decreases'), ('part_of', 'is a part of')], help_text='What type of causal effect is there between the indicators', max_length=40, verbose_name='effect type')),
                ('confidence_level', models.CharField(choices=[('high', 'high'), ('medium', 'medium'), ('low', 'low')], help_text='How confident we are that the causal effect is present', max_length=20, verbose_name='confidence level')),
                ('causal_indicator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_effects', to='indicators.indicator', verbose_name='causal indicator')),
                ('effect_indicator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_causes', to='indicators.indicator', verbose_name='effect indicator')),
            ],
            options={
                'verbose_name': 'related indicator',
                'verbose_name_plural': 'related indicators',
            },
        ),
        migrations.CreateModel(
            name='IndicatorValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.FloatField(verbose_name='value')),
                ('date', models.DateField(verbose_name='date')),
                ('categories', models.ManyToManyField(blank=True, related_name='values', to='indicators.DimensionCategory', verbose_name='categories')),
                ('indicator', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='indicators.indicator', verbose_name='indicator')),
            ],
            options={
                'verbose_name': 'indicator value',
                'verbose_name_plural': 'indicator values',
                'ordering': ('indicator', 'date'),
                'get_latest_by': 'date',
            },
        ),
        migrations.CreateModel(
            name='IndicatorLevel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(choices=[('strategic', 'strategic'), ('tactical', 'tactical'), ('operational', 'operational')], max_length=30, verbose_name='level')),
                ('indicator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='levels', to='indicators.indicator', verbose_name='indicator')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indicator_levels', to='actions.plan', verbose_name='plan')),
            ],
            options={
                'verbose_name': 'indicator levels',
                'verbose_name_plural': 'indicator levels',
            },
        ),
        migrations.CreateModel(
            name='IndicatorGraph',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', django.contrib.postgres.fields.jsonb.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('indicator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='graphs', to='indicators.indicator')),
            ],
            options={
                'get_latest_by': 'created_at',
            },
        ),
        migrations.CreateModel(
            name='IndicatorGoal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.FloatField()),
                ('date', models.DateField(verbose_name='date')),
                ('indicator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to='indicators.indicator', verbose_name='indicator')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indicator_goals', to='actions.plan', verbose_name='plan')),
                ('scenario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='indicator_goals', to='actions.scenario', verbose_name='scenario')),
            ],
            options={
                'verbose_name': 'indicator goal',
                'verbose_name_plural': 'indicator goals',
                'ordering': ('indicator', 'date'),
                'get_latest_by': 'date',
            },
        ),
        migrations.CreateModel(
            name='IndicatorDimension',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='order')),
                ('dimension', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='instances', to='indicators.dimension')),
                ('indicator', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='dimensions', to='indicators.indicator')),
            ],
            options={
                'verbose_name': 'indicator dimension',
                'verbose_name_plural': 'indicator dimensions',
                'ordering': ['indicator', 'order'],
            },
        ),
        migrations.CreateModel(
            name='IndicatorContactPerson',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='order')),
                ('indicator', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='contact_persons', to='indicators.indicator', verbose_name='indicator')),
            ],
            options={
                'verbose_name': 'indicator contact person',
                'verbose_name_plural': 'indicator contact persons',
                'ordering': ['indicator', 'order'],
            },
        ),
    ]
