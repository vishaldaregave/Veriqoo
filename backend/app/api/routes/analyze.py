import os
import tempfile

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.services.ocr_service import OCRService

from app.services.gemini_service import GeminiService

from app.services.legal_retrieval_service import (
    LegalRulesRetrievalService,
)

from app.services.supabase_service import (
    SupabaseService,
)


router = APIRouter(
    prefix="/analyze",
    tags=["analysis"],
)


# --------------------------------------------------
# SERVICES
# --------------------------------------------------

ocr_service = OCRService()

gemini_service = GeminiService()

legal_rules_service = (
    LegalRulesRetrievalService()
)

supabase_service = (
    SupabaseService()
)


# --------------------------------------------------
# ANALYZE PRODUCT
# --------------------------------------------------

@router.post("")
async def analyze_product(

    file: UploadFile = File(...)

) -> dict:


    # --------------------------------------------------
    # VALIDATE IMAGE
    # --------------------------------------------------

    if (

        not file.content_type

        or not file.content_type.startswith(
            "image/"
        )

    ):

        raise HTTPException(

            status_code=400,

            detail=(
                "Please upload a valid image file."
            ),

        )


    temp_path = None


    try:


        # --------------------------------------------------
        # SAVE TEMPORARY IMAGE
        # --------------------------------------------------

        suffix = (

            os.path.splitext(

                file.filename or ""

            )[1]

            or ".jpg"

        )


        with tempfile.NamedTemporaryFile(

            delete=False,

            suffix=suffix,

        ) as temp_file:


            contents = await file.read()


            temp_file.write(

                contents

            )


            temp_path = temp_file.name


        # --------------------------------------------------
        # STEP 1: OCR
        # --------------------------------------------------

        print(
            "STEP 1: Extracting OCR text..."
        )


        extracted_text = (

            ocr_service.extract_text(

                temp_path

            )

        )


        print(
            "OCR extraction completed."
        )


        # --------------------------------------------------
        # STEP 2: LEGAL RAG
        # --------------------------------------------------

        print(
            "STEP 2: Retrieving legal rules..."
        )


        legal_rules_context = (

            legal_rules_service
            .retrieve_legal_context(

                extracted_text

            )

        )


        legal_context = (

            legal_rules_context.formatted

        )


        print(

            "RAG context length:",

            len(legal_context),

        )


        # --------------------------------------------------
        # STEP 3: GEMINI ANALYSIS
        # --------------------------------------------------

        print(
            "STEP 3: Running AI compliance analysis..."
        )


        analysis = (

            gemini_service
            .analyze_product_label(

                extracted_text=extracted_text,

                legal_context=legal_context,

            )

        )


        print(
            "AI analysis completed."
        )


        # --------------------------------------------------
        # STEP 4: SAVE INSPECTION TO SUPABASE
        # --------------------------------------------------

        print(
            "STEP 4: Saving inspection to Supabase..."
        )


        saved_inspection = (

            supabase_service
            .save_inspection(

                extracted_text=extracted_text,

                analysis=analysis,

            )

        )


        print(
            "Inspection saved successfully."
        )


        # --------------------------------------------------
        # STEP 5: RETURN RESULT
        # --------------------------------------------------

        return {

            "status": "success",

            "ocr_text": extracted_text,

            "legal_context": legal_context,

            "analysis": analysis,

            "inspection": (
                saved_inspection
            ),

        }


    except Exception as error:


        print(
            "PRODUCT ANALYSIS ERROR:",
            str(error),
        )


        raise HTTPException(

            status_code=500,

            detail=(

                "Product analysis failed: "

                f"{str(error)}"

            ),

        )


    finally:


        if (

            temp_path

            and os.path.exists(
                temp_path
            )

        ):

            os.remove(
                temp_path
            )