# Generated by Django 3.2.16 on 2023-09-28 19:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0008_alter_sitegeneralcontent_action_term'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitegeneralcontent',
            name='action_task_term',
            field=models.CharField(choices=[('task', 'Task'), ('milestone', 'Milestone')], default='task', max_length=30, verbose_name="Term to use for 'task'"),
        ),
    ]
