# Generated by Django 3.1.2 on 2021-01-14 14:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0064_add_action_implementation_phase'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='action',
            unique_together={('plan', 'identifier')},
        ),
    ]
