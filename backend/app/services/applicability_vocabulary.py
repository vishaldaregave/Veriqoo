"""Controlled Phase 3A vocabularies derived from the Phase 3 audit."""

FACT_KEYS = frozenset(
    {
        "is_prepackaged",
        "commodity",
        "quantity",
        "quantity_unit",
        "actor_role",
        "sale_context",
        "consumer_type",
        "observed_declarations",
    }
)

ACTOR_ROLES = frozenset(
    {
        "manufacturer",
        "packer",
        "importer",
        "dealer",
        "retail_dealer",
        "wholesale_dealer",
    }
)

SALE_CONTEXTS = frozenset({"retail", "wholesale", "export", "domestic"})
CONSUMER_TYPES = frozenset({"institutional", "industrial"})
QUANTITY_DIMENSIONS = frozenset({"weight", "volume", "length", "area", "number"})

FACT_STATUSES = frozenset({"known", "unknown", "not_observed", "not_applicable"})
CONDITION_OPERATORS = frozenset(
    {
        "equals",
        "not_equals",
        "one_of",
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "range_inclusive",
        "exists",
    }
)
CONDITION_GROUP_OPERATORS = frozenset({"AND", "OR"})
APPLICABILITY_RESULTS = frozenset({"applicable", "not_applicable", "unknown"})
RULE_VERSION_STATUSES = frozenset({"draft", "in_review", "approved", "rejected", "retired"})
SOURCE_ROLES = frozenset({"supports", "condition", "exception", "schedule_scope", "amends"})

FACT_VALUE_TYPES = {
    "is_prepackaged": "boolean",
    "commodity": "source-grounded text or reviewed schedule-entry identifier",
    "quantity": "decimal number",
    "quantity_unit": "source-attested unit plus reviewed dimension",
    "actor_role": "controlled string in ACTOR_ROLES",
    "sale_context": "controlled string in SALE_CONTEXTS",
    "consumer_type": "controlled string in CONSUMER_TYPES",
    "observed_declarations": "array of source-supported declaration labels and observed values",
}