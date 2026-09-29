import json

from supabase import Client, create_client

from app.config import get_settings


class SupabaseService:

    def __init__(self):

        settings = get_settings()

        supabase_url = settings.supabase_url
        supabase_key = settings.supabase_anon_key

        print(
            "DEBUG SUPABASE URL LOADED:",
            bool(supabase_url)
        )

        print(
            "DEBUG SUPABASE KEY LOADED:",
            bool(supabase_key)
        )

        if not supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is not configured."
            )

        if not supabase_key:
            raise RuntimeError(
                "SUPABASE_ANON_KEY is not configured."
            )

        self.client: Client = create_client(
            supabase_url,
            supabase_key,
        )


    def save_inspection(
        self,
        extracted_text: str,
        analysis,
    ):

        # Gemini may return JSON text
        if isinstance(analysis, str):

            try:

                analysis_data = json.loads(
                    analysis
                )

            except json.JSONDecodeError:

                analysis_data = {
                    "ai_report": analysis
                }

        else:

            analysis_data = analysis


        possible_issues = analysis_data.get(
            "possibleIssues",
            []
        )

        missing_information = analysis_data.get(
            "missingInformation",
            []
        )


        # Determine compliance
        is_compliant = (
            len(possible_issues) == 0
            and len(missing_information) == 0
        )


        compliance_status = (
            "compliant"
            if is_compliant
            else "non_compliant"
        )


        inspection_data = {

            "product_name": analysis_data.get(
                "productName"
            ),

            "mrp": analysis_data.get(
                "mrp"
            ),

            "quantity": analysis_data.get(
                "netQuantity"
            ),

            "net_quantity": analysis_data.get(
                "netQuantity"
            ),

            "manufacturer": analysis_data.get(
                "manufacturer"
            ),

            "manufacturer_address": analysis_data.get(
                "manufacturerAddress"
            ),

            "address": analysis_data.get(
                "address"
            ),

            "manufacturing_date": analysis_data.get(
                "manufacturingDate"
            ),

            "packing_date": analysis_data.get(
                "packingDate"
            ),

            "expiry_date": analysis_data.get(
                "expiryDate"
            ),

            "customer_care": analysis_data.get(
                "customerCare"
            ),

            "compliance_status": compliance_status,

            "is_compliant": is_compliant,

            "violations": possible_issues,

            "possible_issues": json.dumps(
                possible_issues
            ),

            "missing_information": json.dumps(
                missing_information
            ),

            "ocr_text": extracted_text,

            "ai_report": (
                analysis
                if isinstance(analysis, str)
                else json.dumps(analysis)
            ),

        }


        # Remove None values
        inspection_data = {

            key: value

            for key, value

            in inspection_data.items()

            if value is not None

        }


        response = (

            self.client

            .table("inspections")

            .insert(
                inspection_data
            )

            .execute()

        )


        return response.data