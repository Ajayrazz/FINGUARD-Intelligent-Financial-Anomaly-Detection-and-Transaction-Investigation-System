import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.model_registry.services import register_results


class Command(BaseCommand):
    help = "Register an ml_engine experiment (results.json) in the model registry."

    def add_arguments(self, parser):
        parser.add_argument("results", nargs="+", help="path(s) to results.json")
        parser.add_argument("--code-commit", default="")

    def handle(self, *args, **opts):
        for path in opts["results"]:
            p = Path(path)
            if not p.exists():
                raise CommandError(f"{p} not found")
            mv = register_results(json.loads(p.read_text()), code_commit=opts["code_commit"])
            self.stdout.write(f"registered {mv} ({mv.evaluations.count()} evaluations)")
