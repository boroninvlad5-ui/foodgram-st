import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузить исходный список ингредиентов из CSV.'

    def add_arguments(self, parser):
        backend = Path(__file__).resolve().parents[3]
        local_data = backend.parent / 'data' / 'ingredients.csv'
        container_data = backend / 'data' / 'ingredients.csv'
        default = local_data if local_data.exists() else container_data
        parser.add_argument('path', nargs='?', default=str(default))

    def handle(self, *args, **options):
        count = 0
        with open(options['path'], encoding='utf-8-sig', newline='') as source:
            for name, unit in csv.reader(source):
                _, created = Ingredient.objects.get_or_create(
                    name=name.strip(), measurement_unit=unit.strip()
                )
                count += created
        self.stdout.write(self.style.SUCCESS(f'Загружено: {count}'))
