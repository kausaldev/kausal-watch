# Generated by Django 5.0.4 on 2024-07-01 13:59

import budget.models
import django.db.models.deletion
import modeltrans.fields
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('budget', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='datapoint',
            options={'ordering': ['date'], 'verbose_name': 'data point', 'verbose_name_plural': 'data points'},
        ),
        migrations.AlterModelOptions(
            name='dataset',
            options={'ordering': ['id'], 'verbose_name': 'dataset', 'verbose_name_plural': 'datasets'},
        ),
        migrations.AlterModelOptions(
            name='dimension',
            options={'ordering': ['name'], 'verbose_name': 'dimension', 'verbose_name_plural': 'dimensions'},
        ),
        migrations.RemoveField(
            model_name='dataset',
            name='i18n',
        ),
        migrations.RemoveField(
            model_name='dataset',
            name='time_resolution',
        ),
        migrations.RemoveField(
            model_name='dataset',
            name='unit',
        ),
        migrations.AddField(
            model_name='dataset',
            name='scope_content_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='scope_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='DatasetSchema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('time_resolution', models.CharField(choices=[('yearly', 'Yearly')], default='yearly', help_text='Time resolution of the time stamps of data points in this dataset', max_length=16)),
                ('unit', models.CharField(blank=True, max_length=100, verbose_name='unit')),
                ('name', models.CharField(blank=True, max_length=100, verbose_name='name')),
                ('i18n', modeltrans.fields.TranslationField(fields=['unit', 'name'], required_languages=(), virtual_fields=True)),
                ('dimension_categories', models.ManyToManyField(blank=True, related_name='+', to='budget.dimensioncategory', verbose_name='dimension categories')),
            ],
        ),
        migrations.AddField(
            model_name='dataset',
            name='schema',
            field=models.ForeignKey(default=budget.models.schema_default, on_delete=django.db.models.deletion.PROTECT, related_name='datasets', to='budget.datasetschema', verbose_name='schema'),
        ),
        migrations.CreateModel(
            name='DatasetSchemaScope',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope_id', models.PositiveIntegerField()),
                ('schema', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='budget.datasetschema')),
                ('scope_content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype')),
            ],
        ),
        migrations.DeleteModel(
            name='DatasetScope',
        ),
    ]
