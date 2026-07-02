from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "AI Study Assistant backend is working."

@app.route("/health")
def health_check():
    return {
        "status": "success",
        "message": "Backend is running"
    }

if __name__ == "__main__":
    app.run(debug=True)