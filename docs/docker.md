# Docker

`ftm-analyze` provides multi-stage Docker builds with separate images for each NER backend. This allows you to choose the right trade-off between image size and functionality.

## Available Images

All images are published to GitHub Container Registry:

```
ghcr.io/openaleph/ftm-analyze:<tag>
```

### Image Variants

| Variant | Tag | Description | Size (est.) |
|---------|-----|-------------|-------------|
| **spacy** | `latest`, `spacy` | Full spaCy with 15 language models | ~900MB |
| **spacy-slim** | `spacy-slim` | spaCy with EN, DE, FR, ES models only | ~650MB |
| **flair** | `flair` | Flair NER (downloads models at runtime) | ~1.3GB |
| **gliner** | `gliner` | GLiNER zero-shot NER | ~650MB |
| **transformers** | `transformers` | HuggingFace transformers (BERT) | ~750MB |
| **minimal** | `minimal` | No NER backend (for testing/custom setups) | ~550MB |

### Pulling Images

```bash
# Default (spacy with all language models)
docker pull ghcr.io/openaleph/ftm-analyze:latest

# Specific variant
docker pull ghcr.io/openaleph/ftm-analyze:spacy-slim

# Specific version
docker pull ghcr.io/openaleph/ftm-analyze:1.2.3-spacy-slim
```

## Building Locally

### Prerequisites

Docker with BuildKit support (Docker 23+ has it enabled by default):

```bash
export DOCKER_BUILDKIT=1
```

### Build Commands

```bash
# Build specific variant
docker build --target spacy -t ftm-analyze:spacy .
docker build --target spacy-slim -t ftm-analyze:spacy-slim .
docker build --target flair -t ftm-analyze:flair .
docker build --target gliner -t ftm-analyze:gliner .
docker build --target transformers -t ftm-analyze:transformers .
docker build --target minimal -t ftm-analyze:minimal .

# Or use make targets
make build-docker-spacy
make build-docker-spacy-slim
make build-docker          # builds all variants
```

### Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PYTHON_VERSION` | `3.13` | Python version for base image |

```bash
docker build --target spacy --build-arg PYTHON_VERSION=3.12 -t ftm-analyze:py312 .
```

## Choosing a Variant

### spacy (default)

Best for production deployments requiring multi-language support.

**Included language models:**

- Western European: English, German, French, Spanish, Portuguese, Italian, Dutch
- Eastern European: Russian, Polish, Romanian, Macedonian
- Nordic: Norwegian, Danish
- Other: Greek, Lithuanian

```bash
docker run ghcr.io/openaleph/ftm-analyze:spacy ftm-analyze --help
```

### spacy-slim

Recommended for deployments focused on Western European languages. ~250MB smaller than full spacy.

**Included language models:** English, German, French, Spanish

```bash
docker run ghcr.io/openaleph/ftm-analyze:spacy-slim ftm-analyze --help
```

### flair

Uses [Flair](https://github.com/flairNLP/flair) for NER. Models are downloaded at runtime on first use.

!!! warning
    Flair downloads models (~500MB+) on first run. Consider mounting a volume for `/root/.flair` to persist models.

```bash
docker run -v flair-cache:/root/.flair ghcr.io/openaleph/ftm-analyze:flair ftm-analyze --help
```

### gliner

Uses [GLiNER](https://github.com/urchade/GLiNER) for zero-shot NER. Good for custom entity types.

```bash
docker run ghcr.io/openaleph/ftm-analyze:gliner ftm-analyze --help
```

### transformers

Uses HuggingFace transformers with BERT-based models. Models downloaded at runtime.

```bash
docker run -v hf-cache:/root/.cache/huggingface ghcr.io/openaleph/ftm-analyze:transformers ftm-analyze --help
```

### minimal

No NER backend included. Useful for:

- Testing and development
- Custom NER configurations
- Running only pattern extraction (emails, phones, IBANs)

```bash
docker run ghcr.io/openaleph/ftm-analyze:minimal ftm-analyze --help
```

## Running with Docker

### Basic Usage

```bash
# Analyze entities from a file
docker run -v $(pwd)/data:/data ghcr.io/openaleph/ftm-analyze:spacy \
    ftm-analyze analyze -i /data/entities.ftm.json -o /data/output.ftm.json

# Analyze text directly
echo "Angela Merkel met with Emmanuel Macron in Berlin." | \
    docker run -i ghcr.io/openaleph/ftm-analyze:spacy-slim \
    ftm-analyze analyze-text
```

### With OpenAleph Queue

```bash
docker run \
    -e DATABASE_URL=postgresql://user:pass@host/db \
    -e PROCRASTINATE_APP=ftm_analyze.tasks.app \
    ghcr.io/openaleph/ftm-analyze:spacy \
    procrastinate worker -q analyze
```

### Environment Variables

Configure the NER engine and other settings via environment variables:

```bash
docker run \
    -e FTM_ANALYZE_NER_ENGINE=spacy \
    -e FTM_ANALYZE_RESOLVE_MENTIONS=true \
    -e FTM_ANALYZE_ANNOTATE=true \
    ghcr.io/openaleph/ftm-analyze:spacy \
    ftm-analyze analyze -i /data/input.json
```

See [Settings Reference](./reference/settings.md) for all available options.

## Model Volume Mounts

For production deployments, you can mount external volumes for model storage instead of baking models into the image. This enables:

- Sharing models across containers
- Updating models without rebuilding images
- Reducing image size (use `minimal` target)
- Persisting downloaded models across container restarts

### Volume Configuration by Engine

#### spaCy

spaCy models are Python packages installed in site-packages. For custom model locations, use a custom data directory:

```bash
docker run \
    -v /path/to/spacy-models:/models/spacy \
    -e SPACY_DATA=/models/spacy \
    ghcr.io/openaleph/ftm-analyze:minimal \
    ftm-analyze analyze -i /data/input.json
```

Or override specific language models:

```bash
docker run \
    -e FTM_ANALYZE_SPACY_MODELS_ENG=/models/en_core_web_lg \
    -e FTM_ANALYZE_SPACY_MODELS_DEU=/models/de_core_news_lg \
    ghcr.io/openaleph/ftm-analyze:minimal \
    ftm-analyze analyze -i /data/input.json
```

#### Flair

Flair downloads models to `~/.flair` by default. Mount a volume and set the cache directory:

```bash
docker run \
    -v flair-models:/models/flair \
    -e FLAIR_CACHE_ROOT=/models/flair \
    ghcr.io/openaleph/ftm-analyze:flair \
    ftm-analyze analyze -i /data/input.json
```

#### GLiNER / Transformers (HuggingFace)

Both GLiNER and transformers use the HuggingFace cache. Mount a volume and set `HF_HOME`:

```bash
docker run \
    -v huggingface-cache:/models/huggingface \
    -e HF_HOME=/models/huggingface \
    ghcr.io/openaleph/ftm-analyze:gliner \
    ftm-analyze analyze -i /data/input.json
```

### Pre-warming Model Cache

To pre-download models into a volume for offline use:

```bash
# Create volume
docker volume create ftm-models

# Download Flair models
docker run --rm \
    -v ftm-models:/models \
    -e FLAIR_CACHE_ROOT=/models/flair \
    ghcr.io/openaleph/ftm-analyze:flair \
    python -c "from flair.models import SequenceTagger; SequenceTagger.load('ner')"

# Download HuggingFace models (GLiNER)
docker run --rm \
    -v ftm-models:/models \
    -e HF_HOME=/models/huggingface \
    ghcr.io/openaleph/ftm-analyze:gliner \
    python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_small-v2.1')"
```

### Environment Variable Reference

| Variable | Engine | Description |
|----------|--------|-------------|
| `SPACY_DATA` | spaCy | Custom spaCy data directory |
| `FTM_ANALYZE_SPACY_MODELS_<LANG>` | spaCy | Override model for specific language |
| `FLAIR_CACHE_ROOT` | Flair | Flair model cache directory |
| `HF_HOME` | GLiNER, Transformers | HuggingFace cache directory |
| `TRANSFORMERS_CACHE` | Transformers | Alternative to HF_HOME |
| `FTM_ANALYZE_GLINER_MODEL` | GLiNER | Model name/path |
| `FTM_ANALYZE_BERT_MODEL` | Transformers | Model name/path |

## Build Architecture

The Dockerfile uses multi-stage builds for optimal caching and minimal image size:

```mermaid
flowchart TB
    subgraph parallel["Parallel Stages"]
        direction TB
        builder["builder\n(build tools + pyicu wheel)"]
        models-ftm["models-ftm\n(FTM prediction model)"]
        spacy-models["spacy-models\n(15 language models)"]
        spacy-models-slim["spacy-models-slim\n(4 language models)"]
    end

    python-base["python-base\n(python:3.13-slim + libicu)"]

    python-base --> builder
    python-base --> models-ftm
    python-base --> spacy-models
    python-base --> spacy-models-slim

    builder --> deps-builder["deps-builder\n(install + clean deps)"]
    deps-builder --> deps-base["deps-base\n(clean runtime)"]

    deps-base --> app-base["app-base\n(application code)"]
    models-ftm -.-> app-base

    subgraph variants["Final Variants"]
        direction LR
        spacy["spacy\n(default)"]
        spacy-slim["spacy-slim"]
        flair["flair"]
        gliner["gliner"]
        transformers["transformers"]
        minimal["minimal"]
    end

    app-base --> variants
    spacy-models -.-> spacy
    spacy-models-slim -.-> spacy-slim

    style python-base fill:#e1f5fe
    style app-base fill:#fff3e0
    style variants fill:#e8f5e9
    style parallel fill:#fce4ec
```

### Size Optimizations

The build applies several optimizations to reduce image size:

- **No build tools in runtime** - Compilation happens in builder stage
- **Stripped binaries** - Debug symbols removed from `.so` files
- **No bytecode** - `.pyc` files excluded via `--no-compile`
- **Cleaned site-packages** - Tests, docs, and metadata removed
- **No pip/setuptools** - Removed from final image (not needed at runtime)
