# Generated by Django 3.2.13 on 2022-10-04 09:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_delete_organizationadmin'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='ad_groups',
        ),
    ]
