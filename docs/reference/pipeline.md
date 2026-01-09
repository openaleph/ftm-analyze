# Extraction Pipeline

This document describes the entity extraction pipeline in ftm-analyze.

## Overview

The pipeline processes FTM (FollowTheMoney) entities to extract structured information like named entities, patterns (emails, phones, IBANs), and resolves them against known datasets.

```mermaid
flowchart TD
    subgraph Input
        E[FTM Entity]
    end

    subgraph Analyzer
        E --> LD[Language Detection]
        LD --> EX

        subgraph EX[Extraction]
            NER[NER Extractor]
            PAT[Pattern Extractor]
        end

        EX --> AGG[Aggregator]

        subgraph AGG[Aggregation]
            DEDUP[Deduplication]
            CONF[Confidence Filter]
        end

        AGG --> RES

        subgraph RES[Resolution Pipeline]
            direction TB
            R1[RigourStage] -.-> R2[JudithaClassifierStage]
            R2 -.-> R3[JudithaValidatorStage]
            R3 -.-> R4[GeonamesStage]
            R4 -.-> R5[JudithaLookupStage]
        end

        RES --> EF[Entity Factory]
    end

    subgraph Output
        EF --> M[Mention Entities]
        EF --> RE[Resolved Entities]
        EF --> BA[BankAccount Entities]
        EF --> AE[Annotated Entity]
    end

    style R1 fill:#90EE90
    style R2 fill:#FFE4B5
    style R3 fill:#FFE4B5
    style R4 fill:#FFE4B5
    style R5 fill:#FFE4B5
```

> **Legend:** Green = enabled by default, Orange = optional (disabled by default), Dashed lines = optional stages

## Pipeline Stages

### 1. Language Detection

Detects the language of text content using fastText. The detected languages are stored on the entity and used to select appropriate NER models.

### 2. Extraction

Two types of extractors run in parallel:

#### NER Extractors

Extract named entities (persons, organizations, locations) using one of:

| Engine | Description |
|--------|-------------|
| `spacy` | Default. Uses spaCy models with language-specific variants |
| `flair` | Uses Flair NER models |
| `bert` | Uses HuggingFace transformers (dslim/bert-base-NER) |
| `gliner` | Uses GLiNER zero-shot NER |

#### Pattern Extractor

Extracts structured patterns using regex and validation:

- **Emails** - Validated email addresses
- **Phones** - Phone numbers (via phonenumbers library)
- **IBANs** - International Bank Account Numbers (via schwifty)

### 3. Aggregation

The `Aggregator` combines extraction results:

1. **Deduplication** - Groups results by normalized key (using rigour name normalization for NER, FTM type cleaning for patterns)
2. **Confidence Filtering** - Optional filtering using a fastText classifier to reject "trash" extractions

```mermaid
flowchart LR
    ER[ExtractionResult] --> KEY[Generate Key]
    KEY --> LOOKUP{Exists?}
    LOOKUP -->|No| CREATE[Create AggregatedResult]
    LOOKUP -->|Yes| UPDATE[Add Value]
    CREATE --> STORE[(Results Store)]
    UPDATE --> STORE

    STORE --> ITER[Iterate Results]
    ITER --> CONF{Confidence OK?}
    CONF -->|Yes| YIELD[Yield Result]
    CONF -->|No| SKIP[Skip]
```

### 4. Resolution Pipeline

A composable pipeline of stages that process mentions. Each stage can:

- Modify mention attributes (tag, values, schema)
- Reject mentions
- Pass through unchanged

> **Note:** By default, only `RigourStage` is enabled. All juditha and geonames stages require external services and must be explicitly enabled via configuration.

```mermaid
flowchart TD
    M[Mention] --> R1

    subgraph Classification
        R1[RigourStage]
        R2[JudithaClassifierStage]
    end

    subgraph Validation
        R3[JudithaValidatorStage]
        R4[GeonamesStage]
    end

    subgraph Resolution
        R5[JudithaLookupStage]
    end

    R1 -->|classify PER/ORG| R2
    R2 -.->|refine tag| R3
    R3 -.->|validate PER names| R4
    R4 -.->|canonize LOC| R5
    R5 -.->|lookup entity| OUT

    R1 -->|rejected| REJ[Rejected]
    R2 -.->|rejected| REJ
    R3 -.->|rejected| REJ
    R4 -.->|rejected| REJ
    R5 -.->|rejected| REJ

    OUT[Resolved Mention]

    style R1 fill:#90EE90
    style R2 fill:#FFE4B5
    style R3 fill:#FFE4B5
    style R4 fill:#FFE4B5
    style R5 fill:#FFE4B5
```

#### Stage Details

| Stage | Default | Purpose | Rejects When |
|-------|---------|---------|--------------|
| **Classification** | | | |
| `RigourStage` | **Enabled** | Fast heuristic classification using rigour name patterns. Detects person names (via name symbols) and org names (via org class symbols like Ltd, Inc). Cleans prefixes. | Never |
| `JudithaClassifierStage` | Disabled | ML-based refinement using juditha classifier. Can reclassify PER↔ORG. Requires juditha service. | Low confidence |
| **Validation** | | | |
| `JudithaValidatorStage` | Disabled | Validates entity names (PER) against known name token datasets. Requires juditha service. | Name validation fails |
| `GeonamesStage` | Disabled | Resolves location names (LOC) against geonames database. Sets canonical name and extracts country. Requires geonames data. | Location not found (optional) |
| **Resolution** | | | |
| `JudithaLookupStage` | Disabled | Looks up mentions in juditha entity store. Resolves to canonical forms and known entity IDs. Requires juditha service. | Never |

### 5. Entity Factory

Creates FTM entities from resolved mentions:

| Input | Output Entity Type |
|-------|-------------------|
| Resolved mention with schema | Person, Organization, etc. |
| Unresolved PER/ORG mention | Mention (with `detectedSchema`) |
| IBAN pattern | BankAccount |

### 6. Output

The pipeline yields:

1. **Mention entities** - Links between source document and detected names
2. **Resolved entities** - Person, Organization entities with canonical names
3. **BankAccount entities** - From IBAN extractions
4. **Annotated source entity** - Original entity with extracted properties and optional annotated text for Elasticsearch

## Data Flow

```mermaid
flowchart LR
    subgraph Types
        ER[ExtractionResult]
        AR[AggregatedResult]
        M[Mention]
        EP[EntityProxy]
    end

    ER -->|Aggregator.add| AR
    AR -->|Mention.from_aggregated| M
    M -->|ResolutionPipeline.resolve| M2[Resolved Mention]
    M2 -->|EntityFactory.create_from_mention| EP
```

## Configuration

Pipeline behavior is controlled via environment variables:

| Variable | Default | Description | Enables Stage |
|----------|---------|-------------|---------------|
| `FTM_ANALYZE_NER_ENGINE` | `spacy` | NER engine: spacy, flair, bert, gliner | - |
| `FTM_ANALYZE_REFINE_MENTIONS` | `false` | Enable juditha ML classifier | `JudithaClassifierStage` |
| `FTM_ANALYZE_REFINE_LOCATIONS` | `false` | Enable geonames resolution | `GeonamesStage` |
| `FTM_ANALYZE_VALIDATE_NAMES` | `false` | Enable name validation | `JudithaValidatorStage` |
| `FTM_ANALYZE_RESOLVE_MENTIONS` | `false` | Enable juditha entity lookup | `JudithaLookupStage` |
| `FTM_ANALYZE_ANNOTATE` | `false` | Generate annotated text for Elasticsearch | - |

### Default Pipeline

With default settings, the pipeline runs:

1. Language detection
2. NER extraction (spaCy)
3. Pattern extraction
4. Aggregation with confidence filtering
5. Resolution with `RigourStage` only
6. Entity creation (Mention entities, BankAccounts)

### Full Pipeline

To enable all resolution stages:

```bash
export FTM_ANALYZE_REFINE_MENTIONS=true
export FTM_ANALYZE_REFINE_LOCATIONS=true
export FTM_ANALYZE_VALIDATE_NAMES=true
export FTM_ANALYZE_RESOLVE_MENTIONS=true
```

This requires running [juditha](https://github.com/dataresearchcenter/juditha) and having geonames data available.

## Tracing

Enable pipeline tracing for debugging:

```python
analyzer = Analyzer(entity, enable_tracing=True)
analyzer.feed(entity)
for result in analyzer.flush():
    pass

# Get trace summary
summary = analyzer.get_trace_summary()
```

The tracer collects statistics on:

- Extractions (accepted/rejected by source and tag)
- Aggregations (by tag)
- Resolutions (accepted/rejected by stage)
- Entity creation (by schema)
