import json
import time
from dataclasses import dataclass
from enum import Enum

from google import genai
from supabase import create_client

from app.config import get_settings


class LegalRulesRetrievalException(Exception):
    pass


@dataclass
class LegalRule:
    rule_number: str
    title: str
    category: str
    content: str

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            rule_number=str(
                data.get("rule_number", "unknown")
            ),
            title=str(
                data.get("title", "Untitled rule")
            ),
            category=str(
                data.get("category", "uncategorized")
            ),
            content=str(
                data.get("content", "")
            ),
        )

    def format(self, status: str) -> str:
        return f"""Rule number: {self.rule_number}
Title: {self.title}
Category: {self.category}
Applicability: {status}
Content:
{self.content}"""


class RuleApplicability(Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    CANNOT_DETERMINE = "cannot_determine"

    @classmethod
    def from_value(cls, value):
        if value == "applicable":
            return cls.APPLICABLE

        if value == "not_applicable":
            return cls.NOT_APPLICABLE

        return cls.CANNOT_DETERMINE


@dataclass
class ApplicabilityDecision:
    rule: LegalRule
    status: RuleApplicability


@dataclass
class LegalRulesContext:
    applicable: list
    cannot_determine: list

    @classmethod
    def empty(cls):
        return cls(
            applicable=[],
            cannot_determine=[],
        )

    @property
    def formatted(self) -> str:
        sections = []

        for rule in self.applicable:
            sections.append(
                rule.format("APPLICABLE")
            )

        for rule in self.cannot_determine:
            sections.append(
                rule.format(
                    "APPLICABILITY UNCERTAIN"
                )
            )

        return "\n\n".join(sections)


class LegalRulesRetrievalService:

    # Gemini embedding model
    MODEL = "gemini-embedding-001"

    # Embedding vector dimension
    VECTOR_DIMENSION = 3072

    # Gemini model used for rule applicability classification
    APPLICABILITY_MODEL = "gemini-3.6-flash"

    # Number of retries for temporary Gemini failures
    MAX_APPLICABILITY_ATTEMPTS = 3

    def __init__(self):

        settings = get_settings()

        self.api_key = (
            settings.gemini_api_key.strip()
        )

        if not self.api_key:
            raise LegalRulesRetrievalException(
                "GEMINI_API_KEY is not configured."
            )

        if (
            not settings.supabase_url
            or not settings.supabase_anon_key
        ):
            raise LegalRulesRetrievalException(
                "Supabase configuration is missing."
            )

        self.gemini_client = genai.Client(
            api_key=self.api_key
        )

        self.supabase = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )

    def retrieve_legal_context(
        self,
        ocr_text: str,
    ) -> LegalRulesContext:

        query = self._build_query(
            ocr_text
        )

        print(
            f"RAG: retrieval query generated "
            f"({len(query)} characters)"
        )

        # ==========================================
        # STEP 1: Generate embedding for OCR query
        # ==========================================

        embedding = (
            self._generate_query_embedding(
                query
            )
        )

        # ==========================================
        # STEP 2: Count available embedded rules
        # ==========================================

        try:

            total_response = (
                self.supabase
                .table("legal_rules")
                .select(
                    "rule_number",
                    count="exact",
                )
                .not_.is_(
                    "embedding",
                    "null",
                )
                .execute()
            )

            print(
                "RAG: total embedded legal rules "
                f"available = {total_response.count}"
            )

        except Exception as error:

            print(
                "RAG: unable to count embedded "
                f"legal rules: {error}"
            )

        # ==========================================
        # STEP 3: Find similar legal rules
        # ==========================================

        response = (
            self.supabase
            .rpc(
                "match_legal_rules",
                {
                    "query_embedding": embedding,
                    "match_count": 51,
                },
            )
            .execute()
        )

        response_data = (
            response.data
            if response.data
            else []
        )

        rules = [
            LegalRule.from_json(rule)
            for rule in response_data
        ]

        print(
            f"RAG: rules retrieved = "
            f"{len(rules)}"
        )

        if not rules:
            return LegalRulesContext.empty()

        # ==========================================
        # STEP 4: Classify rule applicability
        #
        # IMPORTANT:
        # Gemini failure here must NOT stop the
        # entire inspection.
        # ==========================================

        decisions = (
            self._classify_applicability(
                ocr_text,
                rules,
            )
        )

        applicable = []
        cannot_determine = []

        for decision in decisions:

            if (
                decision.status
                == RuleApplicability.APPLICABLE
            ):
                applicable.append(
                    decision.rule
                )

            elif (
                decision.status
                == RuleApplicability.CANNOT_DETERMINE
            ):
                cannot_determine.append(
                    decision.rule
                )

        print(
            "RAG: rules classified as "
            f"applicable = {len(applicable)}"
        )

        print(
            "RAG: rules classified as "
            f"not applicable = "
            f"{len(rules) - len(applicable) - len(cannot_determine)}"
        )

        print(
            "RAG: rules classified as "
            f"cannot determine = "
            f"{len(cannot_determine)}"
        )

        return LegalRulesContext(
            applicable=applicable,
            cannot_determine=cannot_determine,
        )

    # ==================================================
    # RULE APPLICABILITY CLASSIFICATION
    #
    # This method is the important fix.
    #
    # If Gemini gives:
    # 429
    # 500
    # 502
    # 503
    # 504
    #
    # it retries and finally falls back safely instead
    # of causing Backend 500.
    # ==================================================

    def _classify_applicability(
        self,
        ocr_text: str,
        rules: list[LegalRule],
    ) -> list[ApplicabilityDecision]:

        prompt = (
            self._build_applicability_prompt(
                ocr_text,
                rules,
            )
        )

        last_error = None

        for attempt in range(
            1,
            self.MAX_APPLICABILITY_ATTEMPTS + 1,
        ):

            try:

                print(
                    "RAG: applicability "
                    f"classification attempt "
                    f"{attempt}/"
                    f"{self.MAX_APPLICABILITY_ATTEMPTS}"
                )

                response = (
                    self.gemini_client
                    .models
                    .generate_content(
                        model=self.APPLICABILITY_MODEL,
                        contents=prompt,
                        config={
                            "temperature": 0.0,
                            "response_mime_type": (
                                "application/json"
                            ),
                        },
                    )
                )

                text = response.text

                if (
                    not text
                    or not text.strip()
                ):
                    raise (
                        LegalRulesRetrievalException(
                            "Applicability response "
                            "was empty."
                        )
                    )

                parsed = json.loads(
                    text.strip()
                )

                decisions_data = (
                    parsed.get("decisions")
                )

                if not isinstance(
                    decisions_data,
                    list,
                ):
                    raise (
                        LegalRulesRetrievalException(
                            "Applicability response "
                            "had no decisions."
                        )
                    )

                # ==================================
                # Successfully received Gemini output
                # ==================================

                by_rule = {
                    rule.rule_number: rule
                    for rule in rules
                }

                classified = []

                for item in decisions_data:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    rule_number = str(
                        item.get(
                            "rule_number",
                            "",
                        )
                    )

                    rule = by_rule.get(
                        rule_number
                    )

                    if rule is None:
                        continue

                    status = (
                        RuleApplicability.from_value(
                            item.get("status")
                        )
                    )

                    classified.append(
                        ApplicabilityDecision(
                            rule=rule,
                            status=status,
                        )
                    )

                classified_numbers = {
                    decision.rule.rule_number
                    for decision in classified
                }

                # ==================================
                # Rules Gemini did not classify
                # become cannot_determine
                # ==================================

                for rule in rules:

                    if (
                        rule.rule_number
                        not in classified_numbers
                    ):
                        classified.append(
                            ApplicabilityDecision(
                                rule=rule,
                                status=(
                                    RuleApplicability
                                    .CANNOT_DETERMINE
                                ),
                            )
                        )

                print(
                    "RAG: applicability "
                    "classification completed."
                )

                return classified

            except Exception as error:

                last_error = error

                print(
                    "RAG WARNING: applicability "
                    f"classification failed on "
                    f"attempt {attempt}/"
                    f"{self.MAX_APPLICABILITY_ATTEMPTS}"
                )

                print(
                    f"RAG WARNING: {error}"
                )

                # ==================================
                # Retry if attempts remain
                # ==================================

                if (
                    attempt
                    < self.MAX_APPLICABILITY_ATTEMPTS
                ):

                    # Exponential backoff:
                    #
                    # Attempt 1 -> wait 3 seconds
                    # Attempt 2 -> wait 6 seconds

                    delay_seconds = (
                        3
                        * (
                            2
                            ** (
                                attempt - 1
                            )
                        )
                    )

                    print(
                        "RAG: Gemini temporarily "
                        "unavailable. "
                        f"Retrying in "
                        f"{delay_seconds} seconds..."
                    )

                    time.sleep(
                        delay_seconds
                    )

        # ==================================================
        # FINAL SAFE FALLBACK
        #
        # IMPORTANT:
        #
        # DO NOT RAISE THE ERROR HERE.
        #
        # The legal rules have already been successfully
        # retrieved from Supabase.
        #
        # Gemini applicability classification is only an
        # additional filtering step.
        #
        # Therefore the inspection should continue using
        # all retrieved rules as uncertain.
        # ==================================================

        print(
            "================================"
        )

        print(
            "RAG WARNING: Gemini applicability "
            "classification failed after "
            "all retries."
        )

        print(
            f"RAG WARNING: Last error: "
            f"{last_error}"
        )

        print(
            "RAG WARNING: Continuing "
            "inspection using retrieved "
            "legal rules."
        )

        print(
            "================================"
        )

        return [
            ApplicabilityDecision(
                rule=rule,
                status=(
                    RuleApplicability
                    .CANNOT_DETERMINE
                ),
            )
            for rule in rules
        ]

    def _build_applicability_prompt(
        self,
        ocr_text: str,
        rules: list[LegalRule],
    ) -> str:

        rule_text = "\n\n".join(
            [
                f"""Rule number: {rule.rule_number}
Title: {rule.title}
Category: {rule.category}
Content:
{rule.content}"""
                for rule in rules
            ]
        )

        return f"""Determine whether each legal rule is applicable to this inspected packaged product based only on the OCR/product information.

Use exactly one status for every rule:

- applicable: the rule clearly governs this package or a declaration that can be assessed for it.
- not_applicable: the rule clearly concerns a different commodity, package type, or circumstance.
- cannot_determine: available OCR/image information is insufficient to decide.

Never call a rule applicable merely because its topic is generally related.

Return JSON only in exactly this format:

{{"decisions":[{{"rule_number":"...","status":"applicable|not_applicable|cannot_determine"}}]}}

OCR/product information:

{ocr_text}

Retrieved legal rules:

{rule_text}"""

    def _build_query(
        self,
        ocr_text: str,
    ) -> str:

        return f"""Determine which Legal Metrology (Packaged Commodities) Rules, 2011 provisions are relevant to this packaged-product label and its declarations.

Pay particular attention to:

- manufacturer
- packer
- importer
- net quantity
- MRP
- dates
- consumer-care details
- unit sale price
- missing declarations

Product label OCR:

{ocr_text.strip()}"""

    def _generate_query_embedding(
        self,
        query: str,
    ) -> list[float]:

        try:

            response = (
                self.gemini_client
                .models
                .embed_content(
                    model=self.MODEL,
                    contents=query,
                    config={
                        "task_type": (
                            "RETRIEVAL_QUERY"
                        ),
                    },
                )
            )

            embeddings = (
                getattr(
                    response,
                    "embeddings",
                    None,
                )
            )

            if not embeddings:
                raise (
                    LegalRulesRetrievalException(
                        "Gemini embedding response "
                        "contained no embeddings."
                    )
                )

            values = list(
                embeddings[0].values
            )

            if (
                len(values)
                != self.VECTOR_DIMENSION
            ):
                raise (
                    LegalRulesRetrievalException(
                        f"Expected "
                        f"{self.VECTOR_DIMENSION} "
                        f"embedding values, "
                        f"received {len(values)}."
                    )
                )

            return [
                float(value)
                for value in values
            ]

        except LegalRulesRetrievalException:
            raise

        except Exception as error:

            raise (
                LegalRulesRetrievalException(
                    "Gemini embedding request "
                    f"failed: {error}"
                )
            ) from error