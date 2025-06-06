[![ftm-analyze on pypi](https://img.shields.io/pypi/v/ftm-analyze)](https://pypi.org/project/ftm-analyze/)
[![Python test and package](https://github.com/investigativedata/ftm-analyze/actions/workflows/python.yml/badge.svg)](https://github.com/investigativedata/ftm-analyze/actions/workflows/python.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/investigativedata/ftm-analyze/badge.svg?branch=main)](https://coveralls.io/github/investigativedata/ftm-analyze?branch=main)
[![AGPLv3+ License](https://img.shields.io/pypi/l/ftm-analyze)](./LICENSE)

# ftm-analyze

Analyze [FollowTheMoney](https://followthemoney.tech) entities. This is part of the ingestion process for [OpenAleph](https://openaleph.org) but can be used standalone or in other applications as well.

`ftm-analyze` replaces the "analyze" pipeline within [ingest-file](https://github.com/openaleph/ingest-file/).

## Features

-

## Installation

    pip install ftm-analyze

## Quickstart

NER extraction:

    ftm-analyze ner -i s3://data/entities.ftm.json

Language detection:

    cat entities.ftm.json | ftm-analyze detect-language -o gcs://my_bucket/entities.ftm.json

## Documentation

https://docs.investigraph.dev/lib/ftm-analyze
