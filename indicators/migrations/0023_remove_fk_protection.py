# Generated by Django 3.2.16 on 2024-02-28 16:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0020_alter_organization_primary_language'),
        ('indicators', '0022_make_indicator_identifiers_longer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='indicator',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indicators', to='orgs.organization', verbose_name='organization'),
        ),
    ]
