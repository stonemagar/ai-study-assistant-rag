import shutil
import random
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

def analyse_question_relevance(question, documents):
    stop_words = {
        "what", "when", "where", "which", "who", "why", "how",
        "is", "are", "was", "were", "the", "a", "an", "and",
        "or", "to", "of", "in", "on", "for", "with", "about",
        "can", "could", "should", "would", "tell", "explain",
        "define", "describe", "fix", "fixed", "reduce", "reduced",
        "improve", "improved"
    }

    # Use 3+ letters so small noisy words like "go" are ignored
    question_words = re.findall(r"\b[a-zA-Z]{3,}\b", question.lower())

    important_words = []

    for word in question_words:
        if word not in stop_words and word not in important_words:
            important_words.append(word)

    if not important_words:
        return {
            "is_relevant": False,
            "matched_words": [],
            "unmatched_words": []
        }

    combined_text = " ".join(documents).lower()

    matched_words = [
        word for word in important_words
        if word in combined_text
    ]

    unmatched_words = [
        word for word in important_words
        if word not in combined_text
    ]

    return {
        "is_relevant": len(matched_words) > 0,
        "matched_words": matched_words,
        "unmatched_words": unmatched_words
    }


def clean_question(question, unmatched_words):
    cleaned_question = question

    for word in unmatched_words:
        cleaned_question = re.sub(
            rf"\b{re.escape(word)}\b",
            "",
            cleaned_question,
            flags=re.IGNORECASE
        )

    cleaned_question = re.sub(r"\s+", " ", cleaned_question).strip()

    return cleaned_question

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

def get_all_notes_text():
    if not os.path.exists(app.config["PROCESSED_FOLDER"]):
        return ""

    all_text = ""

    for filename in os.listdir(app.config["PROCESSED_FOLDER"]):
        if filename.endswith(".txt"):
            file_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)

            with open(file_path, "r", encoding="utf-8") as file:
                all_text += file.read() + "\n\n"

    return all_text.strip()


def generate_notes_summary(notes_text):
    words = notes_text.split()
    limited_text = " ".join(words[:2500])

    prompt = f"""
You are an AI Study Assistant.

Your task is to summarise the uploaded study notes.

Very important rules:
- Return ONLY the final summary.
- Do not write "Here's a summary".
- Do not repeat the rules.
- Do not repeat the full study notes.
- Do not create a section called "Rules".
- Do not create a section called "Study Notes".
- Use only information from the uploaded notes.
- Use British English.
- Keep the answer clear and beginner-friendly.

Use exactly this format:

Short summary:
- one or two short bullet points

Key points:
- key point 1
- key point 2
- key point 3
- key point 4
- key point 5

Important terms:
- Term: simple meaning
- Term: simple meaning
- Term: simple meaning
- Term: simple meaning

Uploaded notes:
--- START OF NOTES ---
{limited_text}
--- END OF NOTES ---

Final summary only:
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
        timeout=180
    )

    response.raise_for_status()

    result = response.json()
    summary = result.get("response", "").strip()

    # Clean unwanted prompt-copying from small local models
    unwanted_markers = [
        "Rules:",
        "**Rules:**",
        "Study Notes:",
        "**Study Notes:**",
        "Uploaded notes:",
        "**Uploaded notes:**"
    ]

    for marker in unwanted_markers:
        if marker in summary:
            summary = summary.split(marker)[0].strip()

    summary = summary.replace("Here's a summary of the uploaded study notes in the requested format:", "").strip()
    summary = summary.replace("Here is a summary of the uploaded study notes in the requested format:", "").strip()

    return summary

def generate_notes_quiz(notes_text):
    words = notes_text.split()
    limited_text = " ".join(words[:2500])

    quiz_focus_options = [
        "definitions and basic concepts",
        "machine learning types and examples",
        "model training and evaluation",
        "overfitting, underfitting and data leakage",
        "algorithms, regression and classification"
    ]

    quiz_focus = random.choice(quiz_focus_options)
    
    prompt = f"""
You are an AI Study Assistant.

Create a short quiz using only the uploaded study notes.
Focus this quiz mainly on: {quiz_focus}

Very important rules:

- Return ONLY the quiz.
- Do not repeat the uploaded notes.
- Create between 8 and 12 useful quiz questions.
- Do not create a section called "Rules".
- Do not create a section called "Study Notes".
- Use only information from the uploaded notes.
- Use British English.
- Keep the quiz beginner-friendly.

Use exactly this format:

Question 1:
Question: ...
Answer: ...
Explanation: ...

Question 2:
Question: ...
Answer: ...
Explanation: ...

Question 3:
Question: ...
Answer: ...
Explanation: ...

Question 4:
Question: ...
Answer: ...
Explanation: ...

Question 5:
Question: ...
Answer: ...
Explanation: ...

Uploaded notes:
--- START OF NOTES ---
{limited_text}
--- END OF NOTES ---

Final quiz only:
"""

    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.4
            }
        },
        timeout=180
    )

    response.raise_for_status()

    result = response.json()
    quiz = result.get("response", "").strip()

    unwanted_markers = [
        "Rules:",
        "**Rules:**",
        "Study Notes:",
        "**Study Notes:**",
        "Uploaded notes:",
        "**Uploaded notes:**"
    ]

    for marker in unwanted_markers:
        if marker in quiz:
            quiz = quiz.split(marker)[0].strip()

    quiz = quiz.replace("Here is a short quiz using the uploaded study notes:", "").strip()
    quiz = quiz.replace("Here's a short quiz using the uploaded study notes:", "").strip()

    return quiz

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

def get_uploaded_notes():
    notes = []
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    for file_name in os.listdir(UPLOAD_FOLDER):
        if file_name == ".gitkeep":
            continue

        file_path = os.path.join(UPLOAD_FOLDER, file_name)

        if os.path.isfile(file_path):
            file_size_kb = round(os.path.getsize(file_path) / 1024, 2)

            notes.append({
                "file_name": file_name,
                "file_size_kb": file_size_kb
            })

    return notes

def delete_single_note(file_name):
    safe_file_name = secure_filename(file_name)

    if not safe_file_name:
        return False, "Invalid file name."

    upload_path = os.path.join(UPLOAD_FOLDER, safe_file_name)

    if not os.path.exists(upload_path):
        return False, "File not found."

    # Delete uploaded file
    os.remove(upload_path)

    # Delete related processed text/chunk files
    original_name_without_extension = os.path.splitext(safe_file_name)[0]

    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    for item_name in os.listdir(PROCESSED_FOLDER):
        if item_name == ".gitkeep":
            continue

        item_path = os.path.join(PROCESSED_FOLDER, item_name)

        if item_name.startswith(original_name_without_extension):
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    # Delete related chunks from ChromaDB
    try:
        client = chromadb.PersistentClient(path=VECTOR_DB_FOLDER)

        # Use the same collection name that your upload/search functions use
        collection = client.get_or_create_collection(name="study_notes")

        collection.delete(
            where={
                "source_file": safe_file_name
            }
        )

    except Exception as error:
        print("Vector delete warning:", error)

    return True, f"{safe_file_name} deleted successfully."

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
    metadatas = results["metadatas"][0][:3]

    relevance = analyse_question_relevance(question, documents)

    if not documents or not relevance["is_relevant"]:
        return jsonify({
            "status": "success",
            "question": question,
            "answer": "I could not find this in the uploaded notes.",
            "sources": [],
            "source_details": []
        })

    focused_question = clean_question(question, relevance["unmatched_words"])

    answer = generate_ai_answer(focused_question, documents)

    if relevance["unmatched_words"]:
        missing_terms = ", ".join(
            f'"{word}"' for word in relevance["unmatched_words"]
        )

        answer = (
            f"I could not find information about {missing_terms} "
            f"in the uploaded notes. {answer}"
        )

    source_details = []

    for index, document in enumerate(documents):
        metadata = metadatas[index]

        source_details.append({
            "source_number": index + 1,
            "source_file": metadata.get("source_file", "Unknown file"),
            "chunk_number": metadata.get("chunk_number", "Unknown chunk"),
            "text": document
        })

    return jsonify({
        "status": "success",
        "question": question,
        "answer": answer,
        "sources": documents,
        "source_details": source_details
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
    

@app.route("/summarise-notes", methods=["POST"])
def summarise_notes():
    notes_text = get_all_notes_text()

    if not notes_text:
        return jsonify({
            "status": "success",
            "summary": "No uploaded notes found. Please upload a PDF first."
        })

    summary = generate_notes_summary(notes_text)

    return jsonify({
        "status": "success",
        "summary": summary
    })

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    notes_text = get_all_notes_text()

    if not notes_text:
        return jsonify({
            "status": "success",
            "quiz": "No uploaded notes found. Please upload a PDF first."
        })

    quiz = generate_notes_quiz(notes_text)

    return jsonify({
        "status": "success",
        "quiz": quiz
    })

@app.route("/notes", methods=["GET"])
def view_uploaded_notes():
    try:
        notes = get_uploaded_notes()

        return jsonify({
            "success": True,
            "count": len(notes),
            "notes": notes
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500
    
@app.route("/delete-note", methods=["POST"])
def delete_note():
    try:
        data = request.get_json()
        file_name = data.get("file_name", "")

        success, message = delete_single_note(file_name)

        return jsonify({
            "success": success,
            "message": message
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500
        
if __name__ == "__main__":
    app.run(debug=True)