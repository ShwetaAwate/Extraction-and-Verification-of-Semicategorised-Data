import pytesseract
from PIL import Image

# Replace with the path to your Tesseract installation
pytesseract.pytesseract.tesseract_cmd = r''

try:
    # Test with a small sample image (replace with any simple image you have)
    img = Image.new('RGB', (100, 30), color='white')
    text = pytesseract.image_to_string(img)
    print("Tesseract is working!")
except Exception as e:
    print(f"Error: {e}")
