from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_analyze.logic import analyze_entities

app = make_app(__loader__.name)
ORIGIN = "ftm-analyze"


@task(app=app)
def analyze(job: DatasetJob) -> DatasetJob:
    with job.get_writer() as bulk:
        for entity in analyze_entities(job.get_entities()):
            bulk.put(entity, origin=ORIGIN)
    return job
