from django.core.management.base import BaseCommand, CommandError

from apps.datasets.models import Dataset
from apps.graph_engine import scenario


class Command(BaseCommand):
    help = "Create the DEMO graph scenario dataset (planted cycle, rapid chain, fan-in, shared beneficiaries)."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="DEMO graph scenario (synthetic)")

    def handle(self, *args, **opts):
        name = opts["name"]
        if not name.upper().startswith("DEMO"):
            raise CommandError("The dataset name must start with DEMO so it is never mistaken for real data.")
        if Dataset.objects.filter(name=name).exists():
            raise CommandError(f"Dataset {name!r} already exists.")
        ds = scenario.build(name)
        self.stdout.write(f"created {ds.name} (id {ds.pk}) with {ds.transactions.count()} transactions")
