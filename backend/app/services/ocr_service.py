from paddleocr import PaddleOCR


class OCRService:
    def __init__(self):
        self.ocr = PaddleOCR(
            lang="en",
            enable_mkldnn=False,
        )

    def extract_text(self, image_path: str) -> str:
        result = self.ocr.predict(image_path)

        extracted_lines = []

        for page in result:
            data = page.json

            if not data:
                continue

            result_data = data.get("res", {})

            texts = result_data.get("rec_texts", [])

            for text in texts:
                text = str(text).strip()

                if text:
                    extracted_lines.append(text)

        return "\n".join(extracted_lines)