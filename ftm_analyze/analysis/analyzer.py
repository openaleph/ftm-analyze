"""Main analyzer for extracting entities from FTM documents."""

from typing import Generator, Literal

from anystore.logging import get_logger
from followthemoney import model
from followthemoney.types import registry
from ftmq.util import EntityProxy
from rigour.names import normalize_name

from ftm_analyze.analysis.aggregate import Aggregator
from ftm_analyze.analysis.emit import EntityFactory
from ftm_analyze.analysis.extract import (
    TAG_IBAN,
    TAG_LOC,
    TAG_ORG,
    TAG_PER,
    BertExtractor,
    ExtractionContext,
    FlairExtractor,
    GlinerExtractor,
    PatternExtractor,
    SpacyExtractor,
)
from ftm_analyze.analysis.extract.patterns import get_iban_country
from ftm_analyze.analysis.language import detect_languages
from ftm_analyze.analysis.resolve import (
    GeonamesStage,
    JudithaClassifierStage,
    JudithaLookupStage,
    JudithaValidatorStage,
    Mention,
    ResolutionContext,
    ResolutionPipeline,
    ResolutionStage,
    RigourStage,
)
from ftm_analyze.analysis.tracer import ExtractionTracer
from ftm_analyze.analysis.util import ANALYZABLE, text_chunks
from ftm_analyze.annotate.annotator import ANNOTATED, Annotator
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()

NerEngine = Literal["spacy", "flair", "bert", "gliner"]

# Map tags to properties for entity output
TAG_TO_PROP_NAME = {
    TAG_PER: "namesMentioned",
    TAG_ORG: "companiesMentioned",
    TAG_LOC: "locationMentioned",
}


class Analyzer:
    """Main analyzer for extracting structured data from FTM entities.

    Orchestrates the extraction pipeline:
    1. Language detection
    2. NER extraction (spacy/flair/bert/gliner)
    3. Pattern extraction (emails, phones, IBANs)
    4. Aggregation and deduplication
    5. Resolution (rigour heuristics, juditha ML, geonames)
    6. Entity creation
    """

    def __init__(
        self,
        entity: EntityProxy,
        ner_engine: NerEngine | None = None,
        use_confidence: bool = True,
        use_rigour: bool = True,
        use_juditha_classifier: bool | None = None,
        use_juditha_validator: bool | None = None,
        use_juditha_lookup: bool | None = None,
        use_geonames: bool | None = None,
        annotate: bool | None = None,
        enable_tracing: bool = False,
    ):
        """Initialize the analyzer.

        Args:
            entity: The source FTM entity to analyze
            ner_engine: NER engine to use (spacy, flair, bert, gliner)
            use_confidence: Enable confidence-based filtering
            use_rigour: Use rigour heuristics for classification
            use_juditha_classifier: Use juditha ML classifier
            use_juditha_validator: Validate names against juditha
            use_juditha_lookup: Lookup entities in juditha (default: settings.resolve_mentions)
            use_geonames: Refine locations with geonames (default: settings.refine_locations)
            annotate: Generate annotated text for search (default: settings.annotate)
            enable_tracing: Enable detailed pipeline tracing
        """
        # Store the source entity
        self.source_entity = entity
        self.entity = model.make_entity(entity.schema)
        self.entity.id = entity.id

        # Initialize extractors
        ner_engine = ner_engine or settings.ner_engine
        self.ner_extractor = self._create_ner_extractor(ner_engine)
        self.pattern_extractor = PatternExtractor()

        # Initialize aggregator
        self.aggregator = Aggregator(
            use_confidence=use_confidence,
            confidence_threshold=settings.ner_type_model_confidence,
        )

        # Initialize resolution pipeline
        self.pipeline = self._create_pipeline(
            use_rigour=use_rigour,
            use_juditha_classifier=(
                use_juditha_classifier
                if use_juditha_classifier is not None
                else settings.refine_mentions
            ),
            use_juditha_validator=(
                use_juditha_validator
                if use_juditha_validator is not None
                else settings.validate_names
            ),
            use_juditha_lookup=(
                use_juditha_lookup
                if use_juditha_lookup is not None
                else settings.resolve_mentions
            ),
            use_geonames=(
                use_geonames if use_geonames is not None else settings.refine_locations
            ),
        )

        # Initialize entity factory
        self.factory = EntityFactory()

        # Initialize annotator
        self.annotate = annotate if annotate is not None else settings.annotate
        self.annotator = Annotator(entity) if self.annotate else None

        # Initialize tracer
        self.tracer = ExtractionTracer(enabled=enable_tracing)

        # Track countries found during analysis
        self.countries: set[str] = set()

    def _create_ner_extractor(
        self, engine: NerEngine
    ) -> SpacyExtractor | FlairExtractor | BertExtractor | GlinerExtractor:
        """Create the appropriate NER extractor."""
        if engine == "bert":
            return BertExtractor()
        elif engine == "flair":
            return FlairExtractor()
        elif engine == "gliner":
            return GlinerExtractor()
        else:
            return SpacyExtractor()

    def _create_pipeline(
        self,
        use_rigour: bool,
        use_juditha_classifier: bool,
        use_juditha_validator: bool,
        use_juditha_lookup: bool,
        use_geonames: bool,
    ) -> ResolutionPipeline:
        """Create the resolution pipeline with configured stages."""
        stages: list[ResolutionStage] = []

        # 1. Classification stages
        if use_rigour:
            stages.append(RigourStage())
        if use_juditha_classifier:
            stages.append(JudithaClassifierStage())

        # 2. Validation/canonicalization stages (by entity type)
        if use_juditha_validator:
            stages.append(JudithaValidatorStage())  # PER
        if use_geonames:
            stages.append(GeonamesStage())  # LOC

        # 3. Entity resolution (last, benefits from all refinements)
        if use_juditha_lookup:
            stages.append(JudithaLookupStage())

        return ResolutionPipeline(stages)

    def feed(self, entity: EntityProxy) -> None:
        """Extract from an entity and aggregate results.

        Args:
            entity: FTM entity to extract from
        """
        if not entity.schema.is_a(ANALYZABLE):
            return

        texts = entity.get_type_values(registry.text)
        for text in text_chunks(texts):
            # Detect languages
            detect_languages(self.entity, text)

            # Create extraction context
            context = ExtractionContext(
                entity=self.entity,
                text=text,
                languages=self.entity.get_type_values(registry.language),
            )

            # NER extraction
            for result in self.ner_extractor.extract(context):
                accepted = self.aggregator.add(result)
                self.tracer.trace_extraction(
                    result.value, result.tag, result.source, accepted
                )

            # Pattern extraction
            for result in self.pattern_extractor.extract(context):
                accepted = self.aggregator.add(result)
                self.tracer.trace_extraction(
                    result.value, result.tag, result.source, accepted
                )

    def flush(self) -> Generator[EntityProxy, None, None]:
        """Resolve and emit entities.

        Yields:
            FTM EntityProxy objects (resolved entities, mentions, bank accounts)
        """
        if self.entity.id is None:
            raise ValueError("Entity has no ID!")

        mention_ids: set[str] = set()
        entity_ids: set[str] = set()
        results_count = 0

        # Create resolution context
        resolution_context = ResolutionContext(
            entity=self.entity,
            languages=self.entity.get_type_values(registry.language),
            countries=self.countries,
        )

        # Process aggregated results
        for agg_result in self.aggregator.iter_results():
            self.tracer.trace_aggregation(
                agg_result.key, agg_result.tag, len(agg_result.values)
            )

            # Handle patterns (non-NER)
            if agg_result.tag in (TAG_IBAN, "EMAIL", "PHONE", "COUNTRY"):
                yield from self._handle_pattern_result(agg_result, entity_ids)
                results_count += 1
                continue

            # Create mention from aggregated NER result
            mention = Mention.from_aggregated(
                key=agg_result.key,
                tag=agg_result.tag,
                values=agg_result.values,
                entity_id=self.entity.id,
                sources=agg_result.sources,
            )

            # Resolve through pipeline
            mention = self.pipeline.resolve(mention, resolution_context)

            self.tracer.trace_resolution(
                mention.key,
                mention.rejection_stage or "complete",
                not mention.is_rejected,
                mention.rejection_reason,
            )

            if mention.is_rejected:
                continue

            # Create entities from mention
            created_entity = None
            for entity in self.factory.create_from_mention(
                mention, countries=self.countries
            ):
                created_entity = entity
                if entity.schema.is_a("Mention"):
                    mention_ids.add(entity.id)
                else:
                    entity_ids.add(entity.id)
                    self.tracer.trace_entity_created(entity.schema.name, entity.id)

                yield entity

            # Handle annotation
            if self.annotator:
                self._annotate_mention(mention, created_entity)

            # Add to output entity properties (normalized)
            prop_name = TAG_TO_PROP_NAME.get(mention.ner_tag)
            if prop_name:
                values = mention.resolved_values or mention.values
                normalized_values = {normalize_name(v) for v in values if v}
                self.entity.add(prop_name, normalized_values, cleaned=True, quiet=True)

            results_count += 1

        # Add countries to output entity
        self.entity.add("country", self.countries)

        # Add annotated text
        if self.annotator:
            for text in self.annotator.get_texts():
                self.entity.add("indexText", f"{ANNOTATED} {text}")

        # Log summary
        if results_count:
            log.debug(
                "Extraction complete",
                results=results_count,
                mentions=len(mention_ids),
                entities=len(entity_ids),
                schema=self.entity.schema.name,
                entity_id=self.entity.id,
            )
            yield self.entity

        # Log tracer summary
        self.tracer.log_summary()

    def _handle_pattern_result(
        self,
        agg_result,
        entity_ids: set[str],
    ) -> Generator[EntityProxy, None, None]:
        """Handle pattern extraction results (emails, phones, IBANs, countries)."""
        if agg_result.tag == "COUNTRY":
            self.countries.update(agg_result.values)
            return

        if agg_result.tag == TAG_IBAN:
            for value in agg_result.values:
                country = get_iban_country(value)
                if country:
                    iban_entity = self.factory.create_bank_account(
                        iban=value,
                        country=country,
                        proof_entity_id=self.entity.id,
                    )
                    entity_ids.add(iban_entity.id)
                    self.tracer.trace_entity_created("BankAccount", iban_entity.id)
                    yield iban_entity

        # Add to output entity (emails, phones, etc.)
        # Map pattern tags to property names
        pattern_prop_map = {
            "EMAIL": "emailMentioned",
            "PHONE": "phoneMentioned",
            TAG_IBAN: "ibanMentioned",
        }
        prop_name = pattern_prop_map.get(agg_result.tag)
        if prop_name:
            self.entity.add(prop_name, agg_result.values, cleaned=True, quiet=True)

        # Annotate patterns
        if self.annotator:
            for value in agg_result.values:
                # Get property from tag for annotation
                from ftm_analyze.analysis.util import TAG_EMAIL
                from ftm_analyze.analysis.util import TAG_IBAN as PROP_IBAN
                from ftm_analyze.analysis.util import TAG_PHONE

                prop_map = {
                    "EMAIL": TAG_EMAIL,
                    "PHONE": TAG_PHONE,
                    TAG_IBAN: PROP_IBAN,
                }
                prop = prop_map.get(agg_result.tag)
                if prop:
                    self.annotator.add_tag(prop, value)

    def _annotate_mention(self, mention: Mention, entity: EntityProxy | None) -> None:
        """Add mention annotation for search."""
        if not self.annotator:
            return

        if entity and entity.schema.is_a("LegalEntity"):
            for value in mention.annotate_values:
                self.annotator.add_mention(value, entity)
        else:
            # Fall back to tag annotation
            from ftm_analyze.analysis.util import TAG_COMPANY, TAG_LOCATION, TAG_PERSON

            prop_map = {
                "PER": TAG_PERSON,
                "ORG": TAG_COMPANY,
                "LOC": TAG_LOCATION,
            }
            prop = prop_map.get(mention.ner_tag)
            if prop:
                for value in mention.values:
                    self.annotator.add_tag(prop, value)

    def get_trace_summary(self) -> dict:
        """Get the extraction trace summary for debugging."""
        return self.tracer.get_summary().to_dict()
