# Generated by Django 3.2.13 on 2022-12-22 16:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0061_plan_version_name'),
        ('feedback', '0003_userfeedback_is_processed'),
    ]

    operations = [
        migrations.AddField(
            model_name='userfeedback',
            name='action',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_feedbacks', to='actions.action', verbose_name='action'),
        ),
        migrations.AddField(
            model_name='userfeedback',
            name='type',
            field=models.CharField(blank=True, choices=[('', 'General'), ('accessibility', 'Accessibility'), ('action', 'Action')], max_length=30, verbose_name='type'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='comment',
            field=models.TextField(verbose_name='comment'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='created at'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='email address'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='is_processed',
            field=models.BooleanField(default=False, verbose_name='is processed'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='name',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_feedbacks', to='actions.plan', verbose_name='plan'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='url',
            field=models.URLField(verbose_name='URL'),
        ),
    ]
