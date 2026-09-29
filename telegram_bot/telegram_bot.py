import os
import asyncio
import json
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ==================================================
# PROJECT PATH
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ==================================================
# LOAD ENVIRONMENT VARIABLES
# ==================================================

ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if TOKEN:
    TOKEN = TOKEN.strip()


# FastAPI Backend URL
BACKEND_URL = "http://127.0.0.1:8010/analyze"


# ==================================================
# TELEGRAM ALBUM STORAGE
# ==================================================

media_groups = {}

media_group_tasks = {}


# ==================================================
# START COMMAND
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "👋 Welcome to VERIQO!\n\n"
        "Send me clear photos of a packaged product.\n\n"
        "📸 You can send multiple images together "
        "(front, back and side).\n\n"
        "I will combine the information from all images "
        "and perform one Legal Metrology compliance analysis."
    )


# ==================================================
# HANDLE SINGLE PHOTO
# ==================================================

async def handle_single_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message or not update.message.photo:
        return


    await update.message.reply_text(
        "📸 Image received!\n\n"
        "🔎 Extracting product information...\n"
        "⚖️ Checking Legal Metrology rules...\n"
        "🤖 Running AI compliance analysis..."
    )


    photo = update.message.photo[-1]


    print("\n================================")
    print("SINGLE IMAGE RECEIVED")
    print("================================")

    print(
        "File ID:",
        photo.file_id,
    )


    image_path = None


    try:


        # ------------------------------------------
        # GET TELEGRAM FILE
        # ------------------------------------------

        telegram_file = await context.bot.get_file(
            photo.file_id
        )


        # ------------------------------------------
        # CREATE IMAGE DIRECTORY
        # ------------------------------------------

        images_dir = BASE_DIR / "images"

        images_dir.mkdir(
            exist_ok=True
        )


        # ------------------------------------------
        # CREATE IMAGE PATH
        # ------------------------------------------

        image_path = (
            images_dir /
            f"{photo.file_unique_id}.jpg"
        )


        # ------------------------------------------
        # DOWNLOAD IMAGE
        # ------------------------------------------

        await telegram_file.download_to_drive(
            custom_path=str(
                image_path
            )
        )


        print(
            "Image downloaded:",
            image_path,
        )


        # ------------------------------------------
        # SEND IMAGE TO BACKEND
        # ------------------------------------------

        result = await send_images_to_backend(
            [image_path]
        )


        # ------------------------------------------
        # SEND RESULT TO TELEGRAM
        # ------------------------------------------

        await send_analysis_result(
            update,
            result,
        )


        print(
            "\nSingle image analysis completed successfully."
        )


    except Exception as error:


        import traceback


        print("\n================================")
        print("SINGLE IMAGE ERROR")
        print("================================")

        print(
            "ERROR TYPE:",
            type(error).__name__
        )

        print(
            "ERROR REPR:",
            repr(error)
        )

        traceback.print_exc()


        try:

            error_message = str(error).strip()

            if not error_message:
                error_message = repr(error)

            if not error_message:
                error_message = (
                    type(error).__name__
                )


            await update.message.reply_text(
                "❌ Product analysis failed.\n\n"
                f"Error: {error_message}"
            )


        except Exception as send_error:


            print(
                "Could not send Telegram error message:",
                repr(send_error),
            )


# ==================================================
# HANDLE PHOTO
# ==================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message or not update.message.photo:
        return


    # ----------------------------------------------
    # GET ALBUM ID
    # ----------------------------------------------

    media_group_id = (
        update.message.media_group_id
    )


    # ----------------------------------------------
    # SINGLE IMAGE
    # ----------------------------------------------

    if not media_group_id:


        await handle_single_photo(
            update,
            context,
        )


        return


    # ----------------------------------------------
    # MULTI IMAGE ALBUM
    # ----------------------------------------------

    print(
        "\nAlbum image received"
    )

    print(
        "Media group:",
        media_group_id,
    )


    # ----------------------------------------------
    # CREATE MEDIA GROUP
    # ----------------------------------------------

    if media_group_id not in media_groups:


        media_groups[
            media_group_id
        ] = {

            "photos": [],

            "chat_id": (
                update.effective_chat.id
            ),

            "context": context,

        }


    # ----------------------------------------------
    # GET HIGHEST RESOLUTION PHOTO
    # ----------------------------------------------

    photo = (
        update.message.photo[-1]
    )


    # ----------------------------------------------
    # STORE PHOTO
    # ----------------------------------------------

    media_groups[
        media_group_id
    ][
        "photos"
    ].append(

        {

            "file_id": (
                photo.file_id
            ),

            "file_unique_id": (
                photo.file_unique_id
            ),

        }

    )


    print(
        "Images currently collected:",
        len(
            media_groups[
                media_group_id
            ][
                "photos"
            ]
        ),
    )


    # ----------------------------------------------
    # RESET ALBUM TIMER
    # ----------------------------------------------

    if media_group_id in media_group_tasks:


        media_group_tasks[
            media_group_id
        ].cancel()


    media_group_tasks[
        media_group_id
    ] = asyncio.create_task(

        process_media_group_after_delay(
            media_group_id
        )

    )


# ==================================================
# PROCESS TELEGRAM ALBUM
# ==================================================

async def process_media_group_after_delay(
    media_group_id: str,
):

    try:


        # ------------------------------------------
        # WAIT FOR ALL ALBUM IMAGES
        # ------------------------------------------

        await asyncio.sleep(
            2
        )


        if (
            media_group_id
            not in media_groups
        ):

            return


        group = (
            media_groups[
                media_group_id
            ]
        )


        photos = (
            group[
                "photos"
            ]
        )


        context = (
            group[
                "context"
            ]
        )


        chat_id = (
            group[
                "chat_id"
            ]
        )


        print(
            "\n================================"
        )

        print(
            "PROCESSING COMPLETE ALBUM"
        )

        print(
            "Album ID:",
            media_group_id,
        )

        print(
            "Total images:",
            len(photos),
        )

        print(
            "================================\n"
        )


        # ------------------------------------------
        # NOTIFY USER
        # ------------------------------------------

        await context.bot.send_message(

            chat_id=chat_id,

            text=(

                f"📸 {len(photos)} product images received!\n\n"

                "🔎 Combining product information from all images...\n"

                "⚖️ Checking Legal Metrology rules...\n"

                "🤖 Running AI compliance analysis..."

            ),

        )


        # ------------------------------------------
        # IMAGE DIRECTORY
        # ------------------------------------------

        images_dir = (
            BASE_DIR / "images"
        )

        images_dir.mkdir(
            exist_ok=True
        )


        downloaded_images = []


        # ------------------------------------------
        # DOWNLOAD ALL IMAGES
        # ------------------------------------------

        for index, photo_data in enumerate(

            photos,

            start=1,

        ):


            print(
                f"Downloading image {index}..."
            )


            telegram_file = (
                await context.bot.get_file(

                    photo_data[
                        "file_id"
                    ]

                )
            )


            image_path = (

                images_dir /

                f"{media_group_id}_{index}.jpg"

            )


            await telegram_file.download_to_drive(

                custom_path=str(
                    image_path
                )

            )


            downloaded_images.append(
                image_path
            )


            print(

                f"Image {index} saved:",

                image_path,

            )


        # ------------------------------------------
        # SEND ALL IMAGES TO BACKEND
        # ------------------------------------------

        print(
            "\nSending all images to backend..."
        )


        result = (
            await send_images_to_backend(

                downloaded_images

            )
        )


        # ------------------------------------------
        # SEND RESULT
        # ------------------------------------------

        await send_analysis_result_by_chat_id(

            context,

            chat_id,

            result,

        )


        print(
            "\nAlbum analysis completed successfully."
        )


    except asyncio.CancelledError:


        print(
            "Album timer reset. Waiting for more images..."
        )


        return


    except Exception as error:


        import traceback


        print(
            "\n================================"
        )

        print(
            "ALBUM PROCESSING ERROR"
        )

        print(
            "================================"
        )

        print(
            "ERROR TYPE:",
            type(error).__name__,
        )

        print(
            "ERROR REPR:",
            repr(error),
        )

        traceback.print_exc()


        try:


            if (
                media_group_id
                in media_groups
            ):


                group = (
                    media_groups[
                        media_group_id
                    ]
                )


                error_message = str(
                    error
                ).strip()


                if not error_message:

                    error_message = repr(
                        error
                    )


                if not error_message:

                    error_message = (
                        type(error).__name__
                    )


                await group[
                    "context"
                ].bot.send_message(

                    chat_id=group[
                        "chat_id"
                    ],

                    text=(

                        "❌ Product analysis failed.\n\n"

                        f"Error: {error_message}"

                    ),

                )


        except Exception as send_error:


            print(
                "Could not send error message:",
                repr(send_error),
            )


    finally:


        # ------------------------------------------
        # CLEAN MEMORY
        # ------------------------------------------

        media_groups.pop(
            media_group_id,
            None,
        )


        media_group_tasks.pop(
            media_group_id,
            None,
        )


# ==================================================
# SEND IMAGES TO FASTAPI BACKEND
# ==================================================

async def send_images_to_backend(
    image_paths,
):

    files = []


    try:


        # ------------------------------------------
        # CREATE MULTIPART FILES
        # ------------------------------------------

        for image_path in image_paths:


            file_handle = open(

                image_path,

                "rb",

            )


            files.append(

                (

                    "file",

                    (

                        image_path.name,

                        file_handle,

                        "image/jpeg",

                    ),

                )

            )


        print(
            "Sending",
            len(files),
            "images to backend...",
        )


        # ------------------------------------------
        # EXTENDED TIMEOUT
        #
        # Multi-image analysis includes:
        # OCR + RAG + Gemini + Supabase
        # ------------------------------------------

        timeout = httpx.Timeout(

            connect=30.0,

            read=600.0,

            write=120.0,

            pool=30.0,

        )


        # ------------------------------------------
        # SEND REQUEST
        # ------------------------------------------

        async with httpx.AsyncClient(

            timeout=timeout,

        ) as client:


            response = await client.post(

                BACKEND_URL,

                files=files,

            )


        print(
            "Backend status:",
            response.status_code,
        )


        # ------------------------------------------
        # HANDLE BACKEND ERROR
        # ------------------------------------------

        if response.status_code != 200:


            raise RuntimeError(

                "Backend returned "

                f"{response.status_code}: "

                f"{response.text}"

            )


        # ------------------------------------------
        # PARSE JSON RESPONSE
        # ------------------------------------------

        try:


            result = response.json()


        except Exception as error:


            raise RuntimeError(

                "Backend returned invalid JSON: "

                f"{response.text}"

            ) from error


        # ------------------------------------------
        # DEBUG
        # ------------------------------------------

        print(
            "Backend response received successfully."
        )


        if isinstance(
            result,
            dict,
        ):


            print(
                "Response keys:",
                list(
                    result.keys()
                ),
            )


        return result


    # ==================================================
    # BACKEND READ TIMEOUT
    # ==================================================

    except httpx.ReadTimeout as error:


        print(
            "\n================================"
        )

        print(
            "BACKEND READ TIMEOUT"
        )

        print(
            "================================"
        )

        print(
            repr(error)
        )


        raise RuntimeError(

            "Backend analysis took longer than expected. "
            "Please try again."

        ) from error


    # ==================================================
    # BACKEND CONNECTION ERROR
    # ==================================================

    except httpx.ConnectError as error:


        print(
            "\n================================"
        )

        print(
            "BACKEND CONNECTION ERROR"
        )

        print(
            "================================"
        )

        print(
            repr(error)
        )


        raise RuntimeError(

            "Could not connect to the VERIQO backend. "
            "Make sure FastAPI is running."

        ) from error


    # ==================================================
    # CLOSE FILES
    # ==================================================

    finally:


        for _, file_data in files:


            file_handle = (
                file_data[1]
            )


            try:

                file_handle.close()


            except Exception:

                pass


# ==================================================
# SEND RESULT TO TELEGRAM
# ==================================================

async def send_analysis_result(
    update: Update,
    result: dict,
):


    formatted_result = (
        format_result(
            result
        )
    )


    chunks = split_message(
        formatted_result,
        4000,
    )


    for chunk in chunks:


        if chunk.strip():

            await update.message.reply_text(
                chunk
            )


# ==================================================
# SEND RESULT USING CHAT ID
# ==================================================

async def send_analysis_result_by_chat_id(
    context,
    chat_id,
    result: dict,
):


    formatted_result = (
        format_result(
            result
        )
    )


    chunks = split_message(
        formatted_result,
        4000,
    )


    for chunk in chunks:


        if chunk.strip():

            await context.bot.send_message(

                chat_id=chat_id,

                text=chunk,

            )


# ==================================================
# FORMAT BACKEND RESULT
# ==================================================

def format_result(
    result: dict,
):


    try:


        # ------------------------------------------
        # INVALID RESULT
        # ------------------------------------------

        if not isinstance(
            result,
            dict,
        ):


            return (

                "📋 PRODUCT COMPLIANCE ANALYSIS\n"

                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"{str(result)}"

            )


        # ------------------------------------------
        # GET ANALYSIS
        # ------------------------------------------

        analysis = result.get(

            "analysis",

            result,

        )


        # ------------------------------------------
        # ANALYSIS MAY BE JSON STRING
        # ------------------------------------------

        if isinstance(
            analysis,
            str,
        ):


            try:

                analysis = json.loads(
                    analysis
                )


            except Exception:


                return (

                    "📋 PRODUCT COMPLIANCE ANALYSIS\n"

                    "━━━━━━━━━━━━━━━━━━━━\n\n"

                    f"{analysis}"

                )


        # ------------------------------------------
        # INVALID ANALYSIS
        # ------------------------------------------

        if not isinstance(
            analysis,
            dict,
        ):


            return (

                "📋 PRODUCT COMPLIANCE ANALYSIS\n"

                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"{str(analysis)}"

            )


        lines = []


        # ------------------------------------------
        # HEADER
        # ------------------------------------------

        lines.append(
            "📋 PRODUCT COMPLIANCE ANALYSIS"
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )


        # ------------------------------------------
        # PRODUCT NAME
        # ------------------------------------------

        product_name = (

            analysis.get(
                "productName"
            )

            or analysis.get(
                "product_name"
            )

            or "Not identified"

        )


        lines.append(
            f"\n📦 Product: {product_name}"
        )


        # ------------------------------------------
        # NET QUANTITY
        # ------------------------------------------

        net_quantity = (

            analysis.get(
                "netQuantity"
            )

            or analysis.get(
                "net_quantity"
            )

            or ""

        )


        if net_quantity:


            lines.append(

                f"📏 Net Quantity: {net_quantity}"

            )


        # ------------------------------------------
        # MRP
        # ------------------------------------------

        mrp = (

            analysis.get(
                "mrp"
            )

            or analysis.get(
                "MRP"
            )

            or ""

        )


        if mrp:


            lines.append(
                f"💰 MRP: {mrp}"
            )


        # ------------------------------------------
        # COMPLIANCE STATUS
        # ------------------------------------------

        compliance_status = (

            analysis.get(
                "complianceStatus"
            )

            or analysis.get(
                "compliance_status"
            )

            or analysis.get(
                "status"
            )

            or ""

        )


        if compliance_status:


            lines.append(

                f"📊 Status: "

                f"{str(compliance_status).upper()}"

            )


        # ------------------------------------------
        # MISSING INFORMATION
        # ------------------------------------------

        missing = (

            analysis.get(
                "missingInformation"
            )

            or analysis.get(
                "missing_information"
            )

            or []

        )


        if missing is None:

            missing = []


        if isinstance(
            missing,
            dict,
        ):

            missing = [
                missing
            ]


        if isinstance(
            missing,
            str,
        ):

            missing = [
                missing
            ]


        if missing:


            lines.append(
                "\n⚠️ MISSING INFORMATION"
            )


            for item in missing:


                if isinstance(
                    item,
                    dict,
                ):


                    item_text = (

                        item.get(
                            "title"
                        )

                        or item.get(
                            "field"
                        )

                        or item.get(
                            "name"
                        )

                        or item.get(
                            "description"
                        )

                        or item.get(
                            "details"
                        )

                        or str(item)

                    )


                else:


                    item_text = str(
                        item
                    )


                lines.append(
                    f"• {item_text}"
                )


        # ------------------------------------------
        # COMPLIANCE ISSUES
        # ------------------------------------------

        issues = (

            analysis.get(
                "possibleIssues"
            )

            or analysis.get(
                "possible_issues"
            )

            or analysis.get(
                "issues"
            )

            or []

        )


        if issues is None:

            issues = []


        if isinstance(
            issues,
            dict,
        ):

            issues = [
                issues
            ]


        if isinstance(
            issues,
            str,
        ):

            issues = [
                issues
            ]


        if issues:


            lines.append(
                "\n🚨 COMPLIANCE ISSUES"
            )


            for index, issue in enumerate(

                issues,

                start=1,

            ):


                # ----------------------------------
                # ISSUE IS DICTIONARY
                # ----------------------------------

                if isinstance(
                    issue,
                    dict,
                ):


                    title = (

                        issue.get(
                            "title"
                        )

                        or issue.get(
                            "issue"
                        )

                        or issue.get(
                            "name"
                        )

                        or "Compliance Issue"

                    )


                    description = (

                        issue.get(
                            "description"
                        )

                        or issue.get(
                            "details"
                        )

                        or issue.get(
                            "message"
                        )

                        or ""

                    )


                    severity = (

                        issue.get(
                            "severity"
                        )

                        or issue.get(
                            "risk"
                        )

                        or ""

                    )


                    legal_basis = (

                        issue.get(
                            "legalBasis"
                        )

                        or issue.get(
                            "legal_basis"
                        )

                        or issue.get(
                            "legalRule"
                        )

                        or issue.get(
                            "legal_rule"
                        )

                        or issue.get(
                            "rule"
                        )

                        or ""

                    )


                # ----------------------------------
                # ISSUE IS STRING
                # ----------------------------------

                else:


                    title = (
                        "Compliance Issue"
                    )


                    description = str(
                        issue
                    )


                    severity = ""


                    legal_basis = ""


                # ----------------------------------
                # ADD ISSUE
                # ----------------------------------

                lines.append(

                    f"\n{index}. {title}"

                )


                if severity:


                    lines.append(

                        "Severity: "

                        f"{str(severity).upper()}"

                    )


                if description:


                    lines.append(
                        str(description)
                    )


                if legal_basis:


                    lines.append(
                        "\n⚖️ Legal Basis:"
                    )


                    if isinstance(
                        legal_basis,
                        list,
                    ):


                        for basis in legal_basis:


                            lines.append(
                                f"• {basis}"
                            )


                    else:


                        lines.append(

                            str(
                                legal_basis
                            )

                        )


        # ------------------------------------------
        # NO ISSUES
        # ------------------------------------------

        if not issues:


            lines.append(

                "\n✅ No major compliance issues "
                "were identified from the available "
                "product information."

            )


        # ------------------------------------------
        # SUMMARY
        # ------------------------------------------

        summary = (

            analysis.get(
                "summary"
            )

            or analysis.get(
                "overallSummary"
            )

            or analysis.get(
                "overall_summary"
            )

            or ""

        )


        if summary:


            lines.append(
                "\n📝 SUMMARY"
            )


            lines.append(
                str(summary)
            )


        # ------------------------------------------
        # RETURN
        # ------------------------------------------

        return "\n".join(
            lines
        )


    except Exception as error:


        print(
            "\n================================"
        )

        print(
            "FORMAT RESULT ERROR"
        )

        print(
            "================================"
        )

        print(
            "ERROR TYPE:",
            type(error).__name__,
        )

        print(
            "ERROR REPR:",
            repr(error),
        )


        print(
            "\nRAW BACKEND RESULT:"
        )


        try:


            print(

                json.dumps(

                    result,

                    indent=2,

                    ensure_ascii=False,

                )

            )


        except Exception:


            print(
                repr(result)
            )


        return (

            "📋 PRODUCT ANALYSIS COMPLETED\n"

            "━━━━━━━━━━━━━━━━━━━━\n\n"

            "The product was successfully analyzed "
            "and saved to the inspection system.\n\n"

            "⚠️ Some response fields could not be "
            "formatted for Telegram."

        )


# ==================================================
# SPLIT LONG TELEGRAM MESSAGES
# ==================================================

def split_message(
    text: str,
    max_length: int = 4000,
):


    # ------------------------------------------
    # EMPTY
    # ------------------------------------------

    if not text:


        return [
            "No analysis result available."
        ]


    text = str(
        text
    )


    # ------------------------------------------
    # SHORT
    # ------------------------------------------

    if len(
        text
    ) <= max_length:


        return [
            text
        ]


    chunks = []

    remaining = text


    # ------------------------------------------
    # SPLIT
    # ------------------------------------------

    while len(
        remaining
    ) > max_length:


        split_at = remaining.rfind(

            "\n",

            0,

            max_length,

        )


        # Try space
        if split_at <= 0:


            split_at = remaining.rfind(

                " ",

                0,

                max_length,

            )


        # Force split
        if split_at <= 0:


            split_at = max_length


        chunk = (

            remaining[
                :split_at
            ].strip()

        )


        if chunk:


            chunks.append(
                chunk
            )


        remaining = (

            remaining[
                split_at:
            ].strip()

        )


    # ------------------------------------------
    # FINAL CHUNK
    # ------------------------------------------

    if remaining:


        chunks.append(
            remaining
        )


    # ------------------------------------------
    # REMOVE EMPTY CHUNKS
    # ------------------------------------------

    return [

        chunk

        for chunk in chunks

        if chunk and chunk.strip()

    ]


# ==================================================
# MAIN
# ==================================================

def main():


    print(
        "\n================================"
    )

    print(
        "VERIQO Telegram Bot"
    )

    print(
        "================================"
    )

    print(
        "Telegram token loaded:",
        bool(TOKEN),
    )

    print(
        "Looking for .env at:",
        ENV_PATH,
    )

    print(
        "Backend URL:",
        BACKEND_URL,
    )


    # ------------------------------------------
    # CHECK TOKEN
    # ------------------------------------------

    if not TOKEN:


        raise RuntimeError(

            "TELEGRAM_BOT_TOKEN is not set. "

            f"Check your .env file at: "

            f"{ENV_PATH}"

        )


    # ------------------------------------------
    # CREATE APPLICATION
    # ------------------------------------------

    app = (

        Application

        .builder()

        .token(TOKEN)

        .build()

    )


    # ------------------------------------------
    # START COMMAND
    # ------------------------------------------

    app.add_handler(

        CommandHandler(

            "start",

            start,

        )

    )


    # ------------------------------------------
    # PHOTO HANDLER
    # ------------------------------------------

    app.add_handler(

        MessageHandler(

            filters.PHOTO,

            handle_photo,

        )

    )


    # ------------------------------------------
    # START BOT
    # ------------------------------------------

    print(
        "\nTelegram bot started..."
    )

    print(
        "Waiting for product images...\n"
    )


    app.run_polling()


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    main()