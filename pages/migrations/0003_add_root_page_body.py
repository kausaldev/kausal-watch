# Generated by Django 3.1 on 2020-08-16 16:30

from django.db import migrations
import pages.models
import wagtail.core.blocks
import wagtail.core.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_add_new_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='planrootpage',
            name='body',
            field=wagtail.core.fields.StreamField([('front_page_hero', wagtail.core.blocks.StructBlock([('layout', wagtail.core.blocks.ChoiceBlock(choices=[('big_image', 'Big image'), ('small_image', 'Small image')])), ('image', wagtail.images.blocks.ImageChooserBlock()), ('heading', wagtail.core.blocks.CharBlock(classname='full title', label='Heading')), ('lead', wagtail.core.blocks.RichTextBlock(label='Lead'))])), ('indicator_highlights', pages.models.IndicatorHighlightsBlock()), ('action_highlights', pages.models.ActionHighlightsBlock())], default=[]),
            preserve_default=False,
        ),
    ]