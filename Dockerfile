FROM python:3.13-slim

RUN apt-get -qq update && apt-get -qq -y upgrade
RUN apt-get install -qq -y pkg-config libicu-dev build-essential git wget
RUN apt-get -qq -y autoremove && apt-get clean

# download ftm type prediction model
RUN mkdir -p /app/models
RUN wget -O /app/models/model_type_prediction.ftz \
    https://cdn.investigativedata.org/ftm-analyze/model_type_prediction.ftz

# Install spaCy and models (these layers will be cached)
RUN pip3 install spacy
RUN python3 -m spacy download en_core_web_sm \
    && python3 -m spacy download de_core_news_sm \
    && python3 -m spacy download fr_core_news_sm \
    && python3 -m spacy download es_core_news_sm
RUN python3 -m spacy download ru_core_news_sm \
    && python3 -m spacy download pt_core_news_sm \
    && python3 -m spacy download ro_core_news_sm \
    && python3 -m spacy download mk_core_news_sm
RUN python3 -m spacy download el_core_news_sm \
    && python3 -m spacy download pl_core_news_sm \
    && python3 -m spacy download it_core_news_sm \
    && python3 -m spacy download lt_core_news_sm \
    && python3 -m spacy download nl_core_news_sm \
    && python3 -m spacy download nb_core_news_sm \
    && python3 -m spacy download da_core_news_sm

RUN pip install --no-cache-dir -U pip setuptools
RUN pip install --no-cache-dir -q --no-binary=:pyicu: pyicu

# Application code (changes frequently - keep at bottom for cache efficiency)
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -q --no-cache-dir --no-deps -r requirements.txt

COPY pyproject.toml /app/pyproject.toml
COPY setup.py /app/setup.py
COPY VERSION /app/VERSION
COPY README.md /app/README.md
COPY ftm_analyze /app/ftm_analyze
COPY models /app/models

RUN pip install -q --no-cache-dir ".[openaleph,ner-spacy]"
RUN pip install -q --no-cache-dir "psycopg[binary]"

ENV PROCRASTINATE_APP="ftm_analyze.tasks.app"

ENTRYPOINT [ "" ]
