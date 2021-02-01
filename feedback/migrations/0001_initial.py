# Generated by Django 3.1 on 2020-10-26 20:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('actions', '0060_add_plan_cache_invalidated_at_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserFeedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('comment', models.TextField()),
                ('url', models.URLField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='actions.plan')),
            ],
        ),
    ]