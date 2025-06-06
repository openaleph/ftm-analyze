from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

app = make_app(__loader__.name)
ORIGIN = "ftm-analyze"


@task(app=app)
def analyze(job: DatasetJob) -> DatasetJob:
    print("ANALYZE")
    return job
