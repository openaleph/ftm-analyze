from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_analyze.logic import analyze_entities

app = make_app(__loader__.name)
ORIGIN = "analyze"


def should_geocode(e: EntityProxy) -> bool:
    return all((e.first("longitude", quiet=True), e.first("latitude", quiet=True)))


@task(app=app)
def analyze(job: DatasetJob) -> None:
    entities: list[EntityProxy] = list(job.load_entities())
    to_geocode: list[EntityProxy] = []
    to_index: list[EntityProxy] = []
    with job.get_writer() as bulk:
        for entity in analyze_entities(entities):
            bulk.put(entity, origin=ORIGIN)
            to_index.append(entity)
            if should_geocode(entity):
                to_geocode.append(entity)
    if to_index:
        defer.index(app, job.dataset, to_index, batch=job.batch, **job.context)
    if to_geocode:
        defer.geocode(app, job.dataset, entities, batch=job.batch, **job.context)
