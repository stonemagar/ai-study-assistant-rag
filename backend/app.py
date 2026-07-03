import os
from flask import Flask, request, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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

    if file and allowed_file(file.filename):
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)

        return jsonify({
            "status": "success",
            "message": "File uploaded successfully",
            "filename": file.filename
        })

    return jsonify({
        "status": "error",
        "message": "Only PDF, TXT, and DOCX files are allowed"
    }), 400


if __name__ == "__main__":
    app.run(debug=True)