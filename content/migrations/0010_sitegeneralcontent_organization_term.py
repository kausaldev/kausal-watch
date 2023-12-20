# Generated by Django 3.2.16 on 2023-11-29 13:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0009_sitegeneralcontent_action_task_term'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitegeneralcontent',
            name='organization_term',
            field=models.CharField(choices=[('organization', 'Organization'), ('division', 'Division')], default='organization', max_length=30, verbose_name="Term to use for 'organization'"),
        ),
    ]