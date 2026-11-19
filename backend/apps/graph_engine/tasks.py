from celery import shared_task

from .services import execute_snapshot, sync_dataset


@shared_task(name="graph.build_snapshot", time_limit=2 * 3600)
def build_snapshot_task(snapshot_id: int) -> None:
    execute_snapshot(snapshot_id)


@shared_task(name="graph.sync_neo4j", time_limit=4 * 3600)
def sync_neo4j_task(dataset_id: int, rebuild: bool = False) -> None:
    sync_dataset(dataset_id, rebuild=rebuild)
