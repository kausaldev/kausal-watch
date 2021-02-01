# Generated by Django 3.1 on 2020-11-10 19:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0001_initial'),
        ('admin_site', '0003_add_admin_hostname_order'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='adminhostname',
            options={'ordering': ('client', 'order')},
        ),
        migrations.RemoveField(
            model_name='client',
            name='logo',
        ),
        migrations.AddField(
            model_name='client',
            name='logo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='images.aplansimage'),
        ),
    ]