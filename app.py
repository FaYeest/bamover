import os
import io
import zipfile
from flask import Flask, render_template, request, send_file, after_this_request
from rembg import remove
from PIL import Image

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_images():
    temp_dir = 'temp_images'
    os.makedirs(temp_dir, exist_ok=True)

    files = request.files.getlist('images')

    for file in files:
        # Convert the uploaded file to an Image object
        img = Image.open(io.BytesIO(file.read()))
        # Remove background
        output_data = remove(img)

        # Convert image to RGB if it's in RGBA mode
        if output_data.mode == 'RGBA':
            output_data = output_data.convert('RGB')

        # Prepare filename and save the processed image
        filename = file.filename
        output_path = os.path.join(temp_dir, filename)
        output_data.save(output_path)  # Save the image to temp directory

    # Create a zip file for the processed images
    zip_path = "processed_images.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zip_file.write(file_path, file)

    # Ensure the ZIP file is closed before sending
    @after_this_request
    def cleanup(response):
        try:
            # Clean up temporary images
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    os.remove(os.path.join(root, file))
            os.rmdir(temp_dir)
            os.remove(zip_path)  # Delete zip file after sending
        except Exception as e:
            print(f"Error cleaning up: {e}")
        return response

    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=8080)