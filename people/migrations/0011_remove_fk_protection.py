# Generated by Django 3.2.16 on 2024-02-28 16:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0020_alter_organization_primary_language'),
        ('people', '0010_remove_person_public_site_only'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='organization',
            field=models.ForeignKey(help_text="What is this person's organization", on_delete=django.db.models.deletion.CASCADE, related_name='people', to='orgs.organization', verbose_name='organization'),
        ),
    ]
