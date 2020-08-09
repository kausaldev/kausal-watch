# Generated by Django 3.0.6 on 2020-08-07 09:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wagtailimages', '0022_uploadedimage'),
        ('people', '0006_add_postal_address_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='main_image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='images.AplansImage'),
        ),
    ]
