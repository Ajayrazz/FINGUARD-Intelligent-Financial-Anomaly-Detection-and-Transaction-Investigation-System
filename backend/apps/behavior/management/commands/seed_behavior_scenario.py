from django.core.management.base import BaseCommand, CommandError

from apps.behavior import scenario
from apps.datasets.models import Dataset


class Command(BaseCommand):
    help = "Create the DEMO behavioral scenario dataset (5 x 40,000 in 10 minutes). Clearly labelled synthetic."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="DEMO behavior scenario (synthetic)")

    def handle(self, *args, **opts):
        name = opts["name"]
        if not name.upper().startswith("DEMO"):
            raise CommandError("The dataset name must start with DEMO so it is never mistaken for real data.")
        if Dataset.objects.filter(name=name).exists():
            raise CommandError(f"Dataset {name!r} already exists.")
        ds = scenario.build(name)
        self.stdout.write(f"created {ds.name} (id {ds.pk}) with {ds.transactions.count()} transactions")
