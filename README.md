[![Docs](https://img.shields.io/badge/docs-live-brightgreen)](https://docs.investigraph.dev/lib/ftm-analyze/)
[![ftm-analyze on pypi](https://img.shields.io/pypi/v/ftm-analyze)](https://pypi.org/project/ftm-analyze/)
[![PyPI Downloads](https://static.pepy.tech/badge/ftm-analyze/month)](https://pepy.tech/projects/ftm-analyze)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ftm-analyze)](https://pypi.org/project/ftm-analyze/)
[![Python test and package](https://github.com/dataresearchcenter/ftm-analyze/actions/workflows/python.yml/badge.svg)](https://github.com/dataresearchcenter/ftm-analyze/actions/workflows/python.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/dataresearchcenter/ftm-analyze/badge.svg?branch=main)](https://coveralls.io/github/dataresearchcenter/ftm-analyze?branch=main)
[![AGPLv3+ License](https://img.shields.io/pypi/l/ftm-analyze)](./LICENSE)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

# ftm-analyze

Analyze [FollowTheMoney](https://followthemoney.tech) entities. This is part of the ingestion process for [OpenAleph](https://openaleph.org) but can be used standalone or in other applications as well.

`ftm-analyze` outsources the "analyze" pipeline from [ingest-file](https://openaleph.org/docs/lib/ingest-file/).

## Features

- Detect language
- Detect country based on location names
- Named Entity Extraction (via [spacy](https://spacy.io/)) and schema prediction
- Convert `Mention` entities into their resolved counterparts if they are known (via [juditha](https://github.com/dataresearchcenter/juditha))
- Extract email, phonenumbers, ibans
- Annotate extracted patterns and names for full text search

## Installation

    pip install ftm-analyze

## Quickstart

    ftm-analyze analyze -i s3://data/entities.ftm.json

## Documentation

https://docs.investigraph.dev/lib/ftm-analyze
