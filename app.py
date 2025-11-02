import io
import zipfile
import uuid
import logging
from flask import Flask, render_template, request, send_file, abort, jsonify
from rembg import remove
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB per request
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_filename(filename: str) -> bool:
    if not filename:
        return False
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    return ('.' + ext.lower()) in ALLOWED_EXT


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    """Return JSON for AJAX requests (so the client can show clean error messages).

    For normal browser navigations, let Flask render the default HTML error page.
    """
    # Detect XHR/fetch via a custom header or prefer JSON when Accept prefers it
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if wants_json:
        response = jsonify({"error": e.description if hasattr(e, 'description') else str(e)})
        response.status_code = e.code or 500
        return response
    return e


@app.errorhandler(Exception)
def handle_unexpected_error(e: Exception):
    # Log full traceback server-side
    logger.exception("Unhandled exception: %s", e)
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if wants_json:
        response = jsonify({"error": "Internal server error"})
        response.status_code = 500
        return response
    # Re-raise to allow default Flask handler to produce HTML error page
    raise e


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process_images():
    files = request.files.getlist('images')
    if not files:
        abort(400, "No files uploaded")

    # Use an in-memory ZIP to avoid race conditions or leftover temp files
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        processed_any = False

        for file_storage in files:
            original_name = file_storage.filename or ''
            filename = secure_filename(original_name) or f"image-{uuid.uuid4().hex}.png"

            # extension check
            if not allowed_filename(filename):
                logger.info("Skipping disallowed extension: %s", original_name)
                continue

            # Read bytes (will be limited by MAX_CONTENT_LENGTH globally)
            try:
                data = file_storage.read()
            except Exception as e:
                logger.exception("Failed to read uploaded file %s: %s", original_name, e)
                continue

            if not data:
                logger.info("Skipping empty file: %s", original_name)
                continue

            if len(data) > MAX_FILE_SIZE:
                logger.info("Skipping file (too large): %s (%d bytes)", original_name, len(data))
                continue

            # Validate and open image using Pillow
            try:
                img = Image.open(io.BytesIO(data))
                # convert to RGBA to be safe for rembg
                img = img.convert('RGBA')
            except UnidentifiedImageError:
                logger.info("Skipping invalid image file: %s", original_name)
                continue
            except Exception as e:
                logger.exception("Error opening image %s: %s", original_name, e)
                continue

            # Remove background using rembg (guard with try/except)
            try:
                result = remove(img)
            except Exception as e:
                logger.exception("rembg failed for %s: %s", original_name, e)
                continue

            # Ensure result preserves alpha and save as PNG
            try:
                if result.mode != 'RGBA':
                    result = result.convert('RGBA')

                out_bytes = io.BytesIO()
                result.save(out_bytes, format='PNG')
                out_bytes.seek(0)

                arcname = f"{uuid.uuid4().hex}_{filename.rsplit('.', 1)[0]}.png"
                zip_file.writestr(arcname, out_bytes.read())
                processed_any = True
            except Exception as e:
                logger.exception("Failed to save processed image for %s: %s", original_name, e)
                continue

    if not processed_any:
        abort(400, "No valid images processed")

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_images.zip'
    )


if __name__ == "__main__":
    # NOTE: Do not run with debug=True in production. Use a WSGI server (gunicorn/uvicorn) behind a reverse proxy.
    app.run(host="127.0.0.1", port=8080, debug=False)