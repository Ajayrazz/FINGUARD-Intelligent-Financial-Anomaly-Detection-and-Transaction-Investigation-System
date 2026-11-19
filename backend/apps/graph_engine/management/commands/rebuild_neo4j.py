import json

from django.core.management.base import BaseCommand, CommandError

from apps.datasets.models import Dataset
from apps.graph_engine import services


class Command(BaseCommand):
    help = "Wipe and reload the Neo4j projection of a dataset from PostgreSQL, then print the drift check."

    def add_arguments(self, parser):
        parser.add_argument("dataset", type=int)
        parser.add_argument("--incremental", action="store_true", help="only project transactions after the watermark")

    def handle(self, *args, **opts):
        if not Dataset.objects.filter(pk=opts["dataset"]).exists():
            raise CommandError("unknown dataset")
        state = services.sync_dataset(opts["dataset"], rebuild=not opts["incremental"])
        self.stdout.write(f"status={state.status} edges_synced={state.edges_synced} error={state.last_error or '-'}")
        self.stdout.write(json.dumps(services.drift_check(opts["dataset"])))
