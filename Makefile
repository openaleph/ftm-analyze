all: clean install test

# All extras except gpu: --all-extras would select the gpu extra and flip torch
# to the CUDA build (see pyproject.toml), local installs stay CPU-only by default
install:
	poetry install --with dev --extras "openaleph ner-flair ner-gliner ner-spacy ner-transformers"

install-gpu:
	poetry install --with dev --extras "openaleph ner-flair ner-gliner ner-spacy ner-transformers gpu"

lint:
	poetry run flake8 ftm_analyze --count --select=E9,F63,F7,F82 --show-source --statistics
	poetry run flake8 ftm_analyze --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

pre-commit:
	poetry run pre-commit install
	poetry run pre-commit run -a

typecheck:
	poetry run mypy --strict ftm_analyze

test:
	poetry run pytest -v --capture=sys --cov=ftm_analyze --cov-report lcov

build:
	poetry build

# Docker build targets
DOCKER_REGISTRY ?= ghcr.io/openaleph
DOCKER_IMAGE ?= ftm-analyze
DOCKER_TAG ?= latest

# Build all NER variants
build-docker: build-docker-spacy build-docker-spacy-slim build-docker-flair build-docker-gliner build-docker-transformers build-docker-minimal

build-docker-spacy:
	docker build --target spacy -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG) -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):spacy .

build-docker-spacy-slim:
	docker build --target spacy-slim -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):spacy-slim .

build-docker-flair:
	docker build --target flair -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):flair .

build-docker-gliner:
	docker build --target gliner -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):gliner .

build-docker-transformers:
	docker build --target transformers -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):transformers .

build-docker-minimal:
	docker build --target minimal -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):minimal .

# GPU (nvidia/cuda) flavors, deliberately not part of build-docker: the default
# variants stay CPU-only, these pull the multi-GB CUDA torch build
build-docker-gpu: build-docker-flair-gpu build-docker-gliner-gpu build-docker-transformers-gpu

build-docker-flair-gpu:
	docker build --target flair-gpu -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):flair-gpu .

build-docker-gliner-gpu:
	docker build --target gliner-gpu -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):gliner-gpu .

build-docker-transformers-gpu:
	docker build --target transformers-gpu -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):transformers-gpu .

# Push all variants
push-docker: push-docker-spacy push-docker-spacy-slim push-docker-flair push-docker-gliner push-docker-transformers push-docker-minimal

push-docker-spacy:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG)
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):spacy

push-docker-spacy-slim:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):spacy-slim

push-docker-flair:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):flair

push-docker-gliner:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):gliner

push-docker-transformers:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):transformers

push-docker-minimal:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):minimal

# GPU flavors, see build-docker-gpu
push-docker-gpu: push-docker-flair-gpu push-docker-gliner-gpu push-docker-transformers-gpu

push-docker-flair-gpu:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):flair-gpu

push-docker-gliner-gpu:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):gliner-gpu

push-docker-transformers-gpu:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):transformers-gpu

clean:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

documentation:
	zensical build
	aws --endpoint-url https://s3.investigativedata.org s3 sync ./site s3://openaleph.org/docs/lib/ftm-analyze
