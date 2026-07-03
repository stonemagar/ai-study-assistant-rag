import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfReader

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "data", "processed_notes")

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    extracted_text = ""

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if page_text:
            extracted_text += f"\n\n--- Page {page_number} ---\n"
            extracted_text += page_text

    return extracted_text


def save_extracted_text(original_filename, text):
    os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)

    filename_without_extension = os.path.splitext(original_filename)[0]
    output_filename = f"{filename_without_extension}.txt"

    output_path = os.path.join(app.config["PROCESSED_FOLDER"], output_filename)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)

    return output_path


@app.route("/")
def home():
    return "AI Study Assistant backend is working."


@app.route("/health")
def health_check():
    return {
        "status": "success",
        "message": "Backend is running"
    }


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part found"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "status": "error",
            "message": "Only PDF, TXT, and DOCX files are allowed"
        }), 400

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    safe_filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)

    file.save(file_path)

    file_extension = safe_filename.rsplit(".", 1)[1].lower()

    if file_extension == "pdf":
        extracted_text = extract_text_from_pdf(file_path)

        if not extracted_text.strip():
            return jsonify({
                "status": "warning",
                "message": "File uploaded, but no readable text was found in the PDF.",
                "filename": safe_filename
            })

        saved_text_path = save_extracted_text(safe_filename, extracted_text)

        return jsonify({
            "status": "success",
            "message": "PDF uploaded and text extracted successfully",
            "filename": safe_filename,
            "text_file": saved_text_path
        })

    return jsonify({
        "status": "success",
        "message": "File uploaded successfully. Text extraction for this file type will be added later.",
        "filename": safe_filename
    })


if __name__ == "__main__":
    app.run(debug=True)