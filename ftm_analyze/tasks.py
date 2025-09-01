from followthemoney import registry
from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_analyze.logic import analyze_entity

app = make_app(__loader__.name)
ORIGIN = "analyze"


def should_geocode(e: EntityProxy) -> bool:
    if e.schema.is_a("Address") or e.schema.is_a("RealEstate"):
        return True
    return bool(e.get_type_values(registry.address))


@task(app=app)
def analyze(job: DatasetJob) -> None:
    entities: list[EntityProxy] = list(job.load_entities())
    to_geocode: list[EntityProxy] = []
    to_index: list[EntityProxy] = []
    with job.get_writer() as bulk:
        for entity in entities:
            for result in analyze_entity(entity):
                bulk.put(result, origin=ORIGIN, fragment=entity.id)
                to_index.append(result)
                if should_geocode(result):
                    to_geocode.append(result)
    if to_index:
        defer.index(app, job.dataset, to_index, batch=job.batch, **job.context)
    if to_geocode:
        defer.geocode(app, job.dataset, entities, batch=job.batch, **job.context)
