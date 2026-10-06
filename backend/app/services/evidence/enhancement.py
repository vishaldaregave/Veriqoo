"\""Image enhancement service for blur and low contrast extraction."\""

from PIL import Image, ImageEnhance, ImageFilter

def enhance_for_ocr(img: Image.Image) -> Image.Image:
    "\""Apply enhancement pipeline to improve OCR on blurry or translucent text."\""
    # 1. Convert to grayscale if it is not already
    img_gray = img.convert('L')
    
    # 2. Increase contrast (helps with translucent text)
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(2.0)
    
    # 3. Apply sharpening (helps with blurry text)
    img_sharp = img_contrast.filter(ImageFilter.SHARPEN)
    
    # 4. Convert back to RGB for standard pipeline consistency
    return img_sharp.convert('RGB')
