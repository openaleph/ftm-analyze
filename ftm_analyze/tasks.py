from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_analyze.logic import analyze_entities

app = make_app(__loader__.name)
ORIGIN = "ftm-analyze"


@task(app=app)
def analyze(job: DatasetJob) -> None:
    entities: list[EntityProxy] = list(job.load_entities())
    with job.get_writer() as bulk:
        for entity in analyze_entities(entities):
            bulk.put(entity, origin=ORIGIN)
            entities.append(entity)
    defer.index(app, job.dataset, entities, **job.context)
