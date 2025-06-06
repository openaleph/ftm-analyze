FROM ghcr.io/dataresearchcenter/ftmq:latest

RUN apt update && apt full-upgrade -y && apt autoremove -y && apt clean
RUN apt install -y wget

COPY ftm_analyze /app/ftm_analyze
COPY models /app/models
COPY setup.py /app/setup.py
COPY pyproject.toml /app/pyproject.toml
COPY VERSION /app/VERSION
COPY README.md /app/README.md

WORKDIR /app
RUN pip install ".[openaleph]"
RUN pip install psycopg-binary

# download ftm type prediction model
RUN wget -O /app/models/model_type_prediction.ftz \
    https://cdn.investigativedata.org/ftm-analyze/model_type_prediction.ftz

# download spacy models
RUN ftm-analyze download-spacy

ENV PROCRASTINATE_APP="ftm_analyze.tasks.app"

ENTRYPOINT [ "ftm-analyze" ]
