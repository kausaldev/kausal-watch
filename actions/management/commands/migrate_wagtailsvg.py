import logging
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from pathlib import Path
from wagtailsvg.models import Svg

from actions.models.category import CategoryIcon, CommonCategoryIcon
from images.models import AplansImage

logger = logging.getLogger(__name__)


# def safe_copy(source, dest):
#     # The file referenced in svg might not exist (e.g., on development machines), or the destination might already
#     # exist. In these cases, don't copy anything and keep the Svg instances as they are.
#     copied = False
#     if os.path.isfile(dest):
#         logger.warning(f"Copy destination {dest} already exists")
#     elif os.path.isfile(source):
#         logger.info(f"Copying {source} to {dest}")
#         copyfile(source, dest)
#         copied = True
#     else:
#         logger.warning(f"Copy source {source} is no file")
#     return copied


class Command(BaseCommand):
    help = "Migrate wagtailsvg's Svg instances to Wagtail images"

    def handle(self, *args, **options):
        self.migrate()

    def migrate_svg(self, svg: Svg) -> AplansImage | None:
        filename = Path(svg.file.path).name
        try:
            with open(svg.file.path, 'rb') as f:
                image_file = ImageFile(f, filename)
                aplans_image = AplansImage.objects.create(
                    title=svg.title,
                    file=image_file,
                    collection=svg.collection,
                )
                return aplans_image
        except FileNotFoundError as e:
            logger.warning(f"Skipping {filename}: {e}")
        return None

    @transaction.atomic
    def migrate(self):
        created_image_ids = []
        deleted_svg_ids = []
        updated_usages = {
            CategoryIcon: [],
            CommonCategoryIcon: [],
        }

        for svg in Svg.objects.all():
            image = self.migrate_svg(svg)
            if image:
                created_image_ids.append(image.id)
                for model in (CategoryIcon, CommonCategoryIcon):
                    qs = model.objects.filter(svg=svg);
                    updated_usages[model].extend(qs.values_list('id', flat=True))
                    qs.update(svg=None, image=image)
                deleted_svg_ids.append(svg.id)
                svg.delete()

        if created_image_ids:
            logger.info(f"IDs of created AplansImage instances: {', '.join([str(id) for id in created_image_ids])}")
        else:
            logger.info("No AplansImage instances created.")

        if deleted_svg_ids:
            logger.info(f"IDs of deleted Svg instances: {', '.join([str(id) for id in deleted_svg_ids])}")
        else:
            logger.info("No Svg instances deleted.")

        num_remaining_svg_instances = Svg.objects.count()
        if num_remaining_svg_instances:
            logger.info(f"There are {num_remaining_svg_instances} remaining Svg instances.")
        else:
            logger.info("There are no remaining Svg instances.")

        for model in (CategoryIcon, CommonCategoryIcon):
            usage_ids = updated_usages[model]
            if usage_ids:
                logger.info(f"IDs of updated {model.__name__} instances: {', '.join([str(id) for id in usage_ids])}")
            else:
                logger.info(f"No {model.__name__} instances updated.")
