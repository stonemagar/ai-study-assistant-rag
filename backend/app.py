import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pypdf import PdfReader
import chromadb

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "data", "processed_notes")
VECTOR_DB_FOLDER = os.path.join(BASE_DIR, "data", "vector_db")

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["VECTOR_DB_FOLDER"] = VECTOR_DB_FOLDER


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


def split_text_into_chunks(text, chunk_size=800, overlap=150):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap

    return chunks


def save_chunks(original_filename, chunks):
    chunks_folder = os.path.join(app.config["PROCESSED_FOLDER"], "chunks")
    os.makedirs(chunks_folder, exist_ok=True)

    filename_without_extension = os.path.splitext(original_filename)[0]
    saved_chunk_files = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_filename = f"{filename_without_extension}_chunk_{index:03}.txt"
        chunk_path = os.path.join(chunks_folder, chunk_filename)

        with open(chunk_path, "w", encoding="utf-8") as file:
            file.write(chunk)

        saved_chunk_files.append(chunk_path)

    return saved_chunk_files


def store_chunks_in_vector_db(original_filename, chunks):
    os.makedirs(app.config["VECTOR_DB_FOLDER"], exist_ok=True)

    client = chromadb.PersistentClient(path=app.config["VECTOR_DB_FOLDER"])

    collection = client.get_or_create_collection(
        name="study_notes"
    )

    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_id = f"{original_filename}_{index}_{uuid.uuid4()}"

        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "source_file": original_filename,
            "chunk_number": index
        })

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return len(ids)


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

        chunks = split_text_into_chunks(extracted_text)
        saved_chunk_files = save_chunks(safe_filename, chunks)

        total_vectors = store_chunks_in_vector_db(safe_filename, chunks)

        return jsonify({
            "status": "success",
            "message": "PDF uploaded, text extracted, chunks created, and stored in vector database",
            "filename": safe_filename,
            "text_file": saved_text_path,
            "total_chunks": len(saved_chunk_files),
            "total_vectors": total_vectors
        })

    return jsonify({
        "status": "success",
        "message": "File uploaded successfully. Text extraction for this file type will be added later.",
        "filename": safe_filename
    })


if __name__ == "__main__":
    app.run(debug=True)