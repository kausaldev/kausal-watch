# Generated by Django 5.0.4 on 2024-05-29 15:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0013_alter_sentnotification_type_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='NotificationTemplate',
            new_name='AutomaticNotificationTemplate',
        ),
    ]
