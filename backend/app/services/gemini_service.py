import json

from google import genai

from app.config import get_settings


class AIAnalysisException(Exception):
    pass


class GeminiService:

    MODEL = "gemini-3.6-flash"

    def __init__(self):
        settings = get_settings()

        print(
            "DEBUG GEMINI KEY LOADED:",
            bool(settings.gemini_api_key)
        )

        print(
            "DEBUG SUPABASE URL LOADED:",
            bool(settings.supabase_url)
        )

        self.api_key = settings.gemini_api_key.strip()

        if not self.api_key:
            raise AIAnalysisException(
                "GEMINI_API_KEY is not configured."
            )

        self.gemini_client = genai.Client(
            api_key=self.api_key
        )
    def analyze_product_label(
        self,
        extracted_text: str,
        legal_context: str = "",
    ) -> dict:

        trimmed_text = extracted_text.strip()

        if (
            not trimmed_text
            or "no text detected" in trimmed_text.lower()
        ):
            raise AIAnalysisException(
                "No OCR text is available to analyze. "
                "Please capture a product image first."
            )

        prompt = self._build_prompt(
            trimmed_text,
            legal_context,
        )

        # IMPORTANT:
        # This confirms which model is actually being used.
        print(
            f"Gemini model being used: {self.MODEL}"
        )

        try:

            response = (
                self.gemini_client.models.generate_content(
                    model=self.MODEL,
                    contents=prompt,
                    config={
                        "temperature": 0.2,
                        "response_mime_type": "application/json",
                    },
                )
            )

            content = response.text

            if (
                not content
                or not content.strip()
            ):
                raise AIAnalysisException(
                    "Gemini API returned no JSON content."
                )

            parsed_json = json.loads(
                content.strip()
            )

            if not isinstance(
                parsed_json,
                dict,
            ):
                raise AIAnalysisException(
                    "Gemini API returned unexpected JSON structure."
                )

            # Restrict Gemini citations so that it can only
            # cite rules actually retrieved through RAG.
            self._restrict_rule_citations(
                parsed_json,
                legal_context,
            )

            return parsed_json

        except AIAnalysisException:
            raise

        except Exception as error:

            raise AIAnalysisException(
                "Failed to analyze Gemini response: "
                f"{error}"
            ) from error


    def _restrict_rule_citations(
        self,
        parsed_json: dict,
        legal_context: str,
    ) -> None:

        possible_issues = (
            parsed_json.get("possibleIssues")
            if isinstance(
                parsed_json.get(
                    "possibleIssues"
                ),
                list,
            )
            else []
        )

        if not legal_context.strip():
            return

        # Dictionary containing only rules actually
        # retrieved from the RAG system.
        #
        # Example:
        # {
        #     "6": "Declaration of quantity",
        #     "18": "Mandatory declarations"
        # }
        valid_rule_map = {}

        current_rule_number = None

        # Extract exact rule numbers and titles
        # from the formatted LEGAL CONTEXT.
        for line in legal_context.splitlines():

            line = line.strip()

            if line.startswith(
                "Rule number:"
            ):

                current_rule_number = (
                    line.replace(
                        "Rule number:",
                        "",
                        1,
                    ).strip()
                )

            elif (
                line.startswith("Title:")
                and current_rule_number
            ):

                rule_title = (
                    line.replace(
                        "Title:",
                        "",
                        1,
                    ).strip()
                )

                valid_rule_map[
                    current_rule_number
                ] = rule_title

        print(
            "RAG: Retrieved valid rules -> "
            f"{list(valid_rule_map.keys())}"
        )

        for issue in possible_issues:

            if not isinstance(
                issue,
                dict,
            ):
                continue

            issue_title = str(
                issue.get("title")
                or "Untitled"
            )

            # Read rule numbers returned by Gemini.
            cited_rules = (
                [
                    str(rule).strip()
                    for rule in issue.get(
                        "ruleNumbers",
                        [],
                    )
                    if str(rule).strip()
                ]
                if isinstance(
                    issue.get("ruleNumbers"),
                    list,
                )
                else []
            )

            # Keep ONLY rules that were actually
            # retrieved by the RAG system.
            valid_rules = [
                rule
                for rule in cited_rules
                if rule in valid_rule_map
            ]

            print(
                f'RAG: Gemini cited rules for issue '
                f'"{issue_title}" -> {cited_rules}'
            )

            if (
                len(valid_rules)
                != len(cited_rules)
            ):

                print(
                    f'RAG: Invalid rule citations removed '
                    f'for "{issue_title}"'
                )

            # Replace Gemini's rules with verified rules.
            issue[
                "ruleNumbers"
            ] = valid_rules

            # Generate titles directly from the retrieved
            # legal context instead of trusting Gemini.
            issue[
                "ruleTitles"
            ] = [
                valid_rule_map[rule]
                for rule in valid_rules
            ]

            # Safety rule:
            # A legally verified violation MUST have at least
            # one valid rule retrieved through RAG.
            if (
                issue.get(
                    "verificationStatus"
                )
                == "legally_verified"
                and not valid_rules
            ):

                print(
                    f'RAG: "{issue_title}" changed from '
                    f'legally_verified to possible_concern '
                    f'because no valid retrieved rule exists.'
                )

                issue[
                    "verificationStatus"
                ] = "possible_concern"


    def _build_prompt(
        self,
        extracted_text: str,
        legal_context: str,
    ) -> str:

        has_legal_context = bool(
            legal_context.strip()
        )

        print(
            f"RAG: Gemini legal context passed = "
            f"{has_legal_context}"
        )

        context_block = (
            legal_context.strip()
            if has_legal_context
            else (
                "No legal context was retrieved. "
                "Do not claim any legally verified "
                "violation without support from a "
                "retrieved legal rule."
            )
        )

        return f"""
You are an expert legal metrology compliance assistant.

Analyze the product label OCR text and return valid JSON only.
Do not use markdown fences.

Rules for evidence and legal verification:

1. Extract only facts present in the OCR text.
   Use an empty string when a value is missing or unclear.

2. Add missing or unclear declarations to
   missingInformation.

3. For possibleIssues, distinguish clearly between:
   - legally verified violations
   - possible concerns
   - cannot determine
   - general observations

4. A legally verified violation must be supported by:
   - a specific retrieved rule in LEGAL CONTEXT, AND
   - clear OCR evidence.

5. Never invent rule numbers or rule titles.

6. Never cite a rule that is not present in
   LEGAL CONTEXT.

7. Use OCR evidence directly from the product
   information.

8. Include a concise legalBasis explaining how
   the retrieved rule applies to the OCR evidence.

9. Use severity values:
   - low
   - medium
   - high

10. Every possible issue MUST contain
    verificationStatus.

Use exactly one of these verificationStatus values:

- "legally_verified"
  Use ONLY when:
  - a retrieved rule supports the issue, AND
  - OCR evidence clearly supports the finding.

- "possible_concern"
  Use when:
  - a retrieved rule may be relevant, but
  - OCR evidence is incomplete or unclear.

- "cannot_determine"
  Use when OCR/product information is
  insufficient to determine compliance.

- "general_observation"
  Use when the finding is only an observation
  and no retrieved legal rule clearly supports it.

Important:

- If verificationStatus is "legally_verified",
  ruleNumbers MUST NOT be empty.

- If verificationStatus is "legally_verified",
  ruleTitles MUST NOT be empty.

- Never mark an issue as legally_verified unless
  BOTH a retrieved rule AND OCR evidence support it.

- If no retrieved rule supports the issue, use:
  "general_observation"
  or
  "possible_concern".

- Never use "legally_verified" when there is no
  supporting retrieved rule.

Return exactly this JSON structure:

{{
  "productName": "",
  "mrp": "",
  "netQuantity": "",
  "manufacturer": "",
  "address": "",
  "packingDate": "",
  "customerCare": "",
  "missingInformation": [],
  "possibleIssues": [
    {{
      "title": "",
      "description": "",
      "severity": "low",
      "verificationStatus": "general_observation",
      "ruleNumbers": [],
      "ruleTitles": [],
      "legalBasis": "",
      "ocrEvidence": ""
    }}
  ]
}}

Output requirements:

- ruleNumbers must contain only rule numbers
  present in LEGAL CONTEXT.

- ruleTitles must correspond exactly to the cited
  rule numbers.

- If multiple rules support an issue, include all
  relevant rules.

- If no retrieved rule supports an issue:
  set ruleNumbers to []
  and ruleTitles to [].

- The legalBasis must explain how the retrieved
  rule applies to the OCR evidence.

- The ocrEvidence field must quote or accurately
  paraphrase information present in the OCR text.

- The title should be short.

- The description should clearly distinguish
  between a legally verified violation and an
  observation or possible concern.

- Every possible issue must include
  verificationStatus.

OCR text:

{extracted_text}

LEGAL CONTEXT:

{context_block}
"""