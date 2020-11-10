# Generated by Django 3.1.3 on 2020-11-27 09:45

import aplans.fields
from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):

    dependencies = [
        ('admin_site', '0004_convert_client_logo_to_foreign_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminhostname',
            name='hostname',
            field=aplans.fields.HostnameField(max_length=254, unique=True),
        ),
        migrations.CreateModel(
            name='EmailDomains',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='order')),
                ('domain', aplans.fields.HostnameField(max_length=254, unique=True)),
                ('client', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_domains', to='admin_site.client')),
            ],
            options={
                'ordering': ('client', 'order'),
            },
        ),
    ]
