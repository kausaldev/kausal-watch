# Generated by Django 3.2.13 on 2022-08-11 15:59

import actions.blocks
from django.db import migrations
import indicators.blocks
import wagtail.core.blocks
import wagtail.core.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0005_alter_planlink_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planrootpage',
            name='body',
            field=wagtail.core.fields.StreamField([('front_page_hero', wagtail.core.blocks.StructBlock([('layout', wagtail.core.blocks.ChoiceBlock(choices=[('big_image', 'Big image'), ('small_image', 'Small image')])), ('image', wagtail.images.blocks.ImageChooserBlock()), ('heading', wagtail.core.blocks.CharBlock(form_classname='full title', label='Heading')), ('lead', wagtail.core.blocks.RichTextBlock(label='Lead'))], label='Front page hero block')), ('category_list', wagtail.core.blocks.StructBlock([('heading', wagtail.core.blocks.CharBlock(form_classname='full title', label='Heading', required=False)), ('lead', wagtail.core.blocks.RichTextBlock(label='Lead', required=False)), ('style', wagtail.core.blocks.ChoiceBlock(choices=[('cards', 'Cards'), ('table', 'Table'), ('treemap', 'Tree map')]))], label='Category list')), ('indicator_group', indicators.blocks.IndicatorGroupBlock()), ('indicator_highlights', indicators.blocks.IndicatorHighlightsBlock(label='Indicator highlights')), ('indicator_showcase', wagtail.core.blocks.StructBlock([('title', wagtail.core.blocks.CharBlock(required=False)), ('body', wagtail.core.blocks.RichTextBlock(required=False)), ('indicator', indicators.blocks.IndicatorChooserBlock()), ('link_button', wagtail.core.blocks.StructBlock([('text', wagtail.core.blocks.CharBlock(required=False)), ('page', wagtail.core.blocks.PageChooserBlock(required=False))]))])), ('action_highlights', actions.blocks.ActionHighlightsBlock(label='Action highlights')), ('related_plans', actions.blocks.RelatedPlanListBlock(label='Related plans')), ('cards', wagtail.core.blocks.StructBlock([('heading', wagtail.core.blocks.CharBlock()), ('lead', wagtail.core.blocks.CharBlock(required=False)), ('cards', wagtail.core.blocks.ListBlock(wagtail.core.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock(required=False)), ('heading', wagtail.core.blocks.CharBlock()), ('content', wagtail.core.blocks.CharBlock(required=False)), ('link', wagtail.core.blocks.CharBlock(required=False))])))])), ('action_links', wagtail.core.blocks.StructBlock([('cards', wagtail.core.blocks.ListBlock(wagtail.core.blocks.StructBlock([('heading', wagtail.core.blocks.CharBlock(label='Heading')), ('lead', wagtail.core.blocks.CharBlock(label='Lead')), ('category', actions.blocks.CategoryChooserBlock(label='Category'))]), label='Links'))], label='Links to actions in specific category'))]),
        ),
    ]