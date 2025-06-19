from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob, Defers
from openaleph_procrastinate.tasks import task

from ftm_analyze.logic import analyze_entities
from ftm_analyze.settings import Settings

app = make_app(__loader__.name)
ORIGIN = "ftm-analyze"


@task(app=app)
def analyze(job: DatasetJob) -> Defers:
    settings = Settings()
    entities: list[EntityProxy] = []
    with job.get_writer() as bulk:
        for entity in analyze_entities(job.load_entities()):
            bulk.put(entity, origin=ORIGIN)
            entities.append(entity)
    if settings.tasks.defer_index:
        yield defer.index(job.dataset, entities, **job.context)
