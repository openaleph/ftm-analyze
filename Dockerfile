FROM ghcr.io/dataresearchcenter/ftm-analyze-base:latest

COPY ftm_analyze /app/ftm_analyze
COPY models /app/models
COPY setup.py /app/setup.py
COPY pyproject.toml /app/pyproject.toml
COPY VERSION /app/VERSION
COPY README.md /app/README.md

WORKDIR /app
RUN pip install ".[openaleph]"

# download configured spacy models
# they are in base image now, and could overwritten here via docker ARG
# RUN ftm-analyze download-spacy

ENV PROCRASTINATE_APP="ftm_analyze.tasks.app"

ENTRYPOINT [ "" ]
