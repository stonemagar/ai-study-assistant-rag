import shutil
import os
import re
import uuid
import fitz
import chromadb
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename






app = Flask(__name__)
CORS(app)


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv(os.path.join(BASE_DIR, ".env"))


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
    document = fitz.open(file_path)
    extracted_text = ""

    for page_number, page in enumerate(document, start=1):
        page_text = page.get_text("text")

        if page_text.strip():
            extracted_text += f"\n\n--- Page {page_number} ---\n"
            extracted_text += page_text

    document.close()
    return extracted_text


def fix_spaced_letters(text):
    """
    Fixes PDF text if it appears like:
    M a c h i n e   L e a r n i n g

    into:
    Machine Learning
    """

    sample_tokens = text[:3000].split()

    if not sample_tokens:
        return text

    single_character_tokens = sum(
        1 for token in sample_tokens
        if len(token) == 1 and token.isalnum()
    )

    ratio = single_character_tokens / len(sample_tokens)

    # Only apply this fix when many tokens are single letters
    if ratio < 0.4:
        return text

    word_space_marker = "###WORDSPACE###"

    # Keep bigger spaces as real word spaces
    text = re.sub(r"[ \t]{2,}", word_space_marker, text)

    # Remove spaces between letters/numbers
    text = re.sub(r"(?<=[A-Za-z0-9])\s+(?=[A-Za-z0-9])", "", text)

    # Restore word spaces
    text = text.replace(word_space_marker, " ")

    return text


def clean_extracted_text(text):
    text = fix_spaced_letters(text)

    # Remove too many blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Replace repeated spaces and tabs with one space
    text = re.sub(r"[ \t]+", " ", text)

    # Remove spaces before punctuation
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    # Join broken single lines
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    return text.strip()


def save_extracted_text(original_filename, text):
    os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)

    filename_without_extension = os.path.splitext(original_filename)[0]
    output_filename = f"{filename_without_extension}.txt"

    output_path = os.path.join(app.config["PROCESSED_FOLDER"], output_filename)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)

    return output_path


def split_text_into_chunks(text, chunk_size=120, overlap=25):
    """
    Splits text into word-based chunks.
    This avoids the problem of showing text like:
    M a c h i n e L e a r n i n g
    """

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])

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


def get_keyword_score(question, document):
    stop_words = {
        "what", "when", "where", "which", "who", "why", "how",
        "is", "are", "was", "were", "the", "a", "an", "and",
        "or", "to", "of", "in", "on", "for", "with", "about"
    }

    question_words = re.findall(r"\b[a-zA-Z]{3,}\b", question.lower())

    important_words = [
        word for word in question_words
        if word not in stop_words
    ]

    document_lower = document.lower()

    score = 0

    for word in important_words:
        if word in document_lower:
            score += 10

    # Extra boost if the main keyword appears clearly
    if important_words:
        main_keyword = important_words[-1]
        if main_keyword in document_lower:
            score += 20

    return score


def search_vector_db(question, number_of_results=3):
    client = chromadb.PersistentClient(path=app.config["VECTOR_DB_FOLDER"])

    collection = client.get_or_create_collection(
        name="study_notes"
    )

    # Get more results first, then re-rank them
    results = collection.query(
        query_texts=[question],
        n_results=8,
        include=["documents", "metadatas", "distances"]
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    combined_results = []

    for index, document in enumerate(documents):
        combined_results.append({
            "document": document,
            "metadata": metadatas[index],
            "distance": distances[index],
            "keyword_score": get_keyword_score(question, document)
        })

    # Higher keyword score is better.
    # Lower distance is better.
    combined_results.sort(
        key=lambda item: (-item["keyword_score"], item["distance"])
    )

    top_results = combined_results[:number_of_results]

    return {
        "documents": [[item["document"] for item in top_results]],
        "metadatas": [[item["metadata"] for item in top_results]],
        "distances": [[item["distance"] for item in top_results]]
    }

def generate_ai_answer(question, documents):
    context = "\n\n".join(documents)

    prompt = f"""
You are an AI Study Assistant.

Use the study notes below to answer the student's question.

Rules:
- Answer only from the study notes.
- If the question asks about one topic, answer only that topic.
- Do not include related topics unless the question asks for them.
- Do not add examples, causes, results, names, methods, or bracket examples unless they are written exactly in the notes.
- For definition questions, give only the definition written in the notes.
- Keep the answer short and clear.
- Use British English.
- Do not start with "Here's an answer" or "To answer your question".
- Never write both an answer and "I could not find this in the uploaded notes."
- Say "I could not find this in the uploaded notes." only if there is no relevant information at all.

Student question:
{question}

Study notes:
{context}

Final answer only:
"""

    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0
            }
        },
        timeout=120
    )

    response.raise_for_status()

    result = response.json()
    answer = result.get("response", "").strip()

    not_found_message = "I could not find this in the uploaded notes."

    if not_found_message in answer and answer.replace(not_found_message, "").strip():
        answer = answer.replace(not_found_message, "").strip()

    return answer

def empty_folder(folder_path):
    os.makedirs(folder_path, exist_ok=True)

    for item_name in os.listdir(folder_path):
        if item_name == ".gitkeep":
            continue

        item_path = os.path.join(folder_path, item_name)

        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)

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
        return jsonify({
            "status": "error",
            "message": "No file part found"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "No file selected"
        }), 400

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
        extracted_text = clean_extracted_text(extracted_text)

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


@app.route("/search", methods=["POST"])
def search_notes():
    data = request.get_json()

    if not data or "question" not in data:
        return jsonify({
            "status": "error",
            "message": "No question provided"
        }), 400

    question = data["question"]

    results = search_vector_db(question)

    return jsonify({
        "status": "success",
        "question": question,
        "results": results
    })

@app.route("/ask", methods=["POST"])
def ask_ai():
    data = request.get_json()

    if not data or "question" not in data:
        return jsonify({
            "status": "error",
            "message": "No question provided"
        }), 400

    question = data["question"]

    results = search_vector_db(question)
    documents = results["documents"][0][:3]

    if not documents:
        return jsonify({
            "status": "success",
            "question": question,
            "answer": "I could not find this in the uploaded notes.",
            "sources": []
        })

    answer = generate_ai_answer(question, documents)

    return jsonify({
        "status": "success",
        "question": question,
        "answer": answer,
        "sources": documents
    })

@app.route("/clear-notes", methods=["POST"])
def clear_notes():
    try:
        empty_folder(app.config["UPLOAD_FOLDER"])
        empty_folder(app.config["PROCESSED_FOLDER"])

        os.makedirs(app.config["VECTOR_DB_FOLDER"], exist_ok=True)

        client = chromadb.PersistentClient(path=app.config["VECTOR_DB_FOLDER"])

        try:
            collection = client.get_collection(name="study_notes")
            existing_items = collection.get()

            if existing_items["ids"]:
                collection.delete(ids=existing_items["ids"])

        except Exception:
            pass

        return jsonify({
            "status": "success",
            "message": "Uploaded notes and vector data cleared successfully."
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": f"Could not clear notes: {str(error)}"
        }), 500
    
if __name__ == "__main__":
    app.run(debug=True)