# Usage

Run the API locally (recommended Python 3.10+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

If you want to use the camera scan / OCR feature in production, the backend server must either have Tesseract installed or be configured to use a remote OCR provider.

- For local deployment: install `Tesseract-OCR` and make sure `pytesseract` can access it.
- For hosted deployment: set `OCR_PROVIDER=remote`, `OCR_SERVICE_URL`, and optionally `OCR_SERVICE_KEY` in `.env`.

Run tests:

```bash
pytest -q
```
