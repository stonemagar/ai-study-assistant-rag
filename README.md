# AI Study Assistant with RAG

AI Study Assistant with RAG is a web application that helps students learn from their own uploaded study notes. The app allows users to upload PDF notes, ask questions, generate summaries, and create quiz questions based on the uploaded content.

This project was built as a first full web app for learning practical AI, Python backend development, and Retrieval-Augmented Generation.

## Aim of the Project

The aim of this project is to build a simple AI-powered study assistant that answers questions using uploaded notes instead of general internet knowledge. The system uses a RAG workflow to retrieve relevant note chunks before generating an answer with a local AI model.

## Main Features

- Upload PDF study notes
- Extract text from uploaded PDF files
- Clean extracted text
- Split notes into smaller chunks
- Store note chunks in ChromaDB
- Search relevant note chunks using vector search
- Generate AI answers using a local Ollama model
- Answer only from uploaded notes
- Show and hide retrieved sources
- Display source file name and chunk number
- Summarise uploaded notes
- Generate quiz questions from notes
- Clear uploaded notes and stored data
- Loading message while the AI is thinking
- View uploaded notes
- Auto-refresh uploaded notes list
- Delete individual uploaded notes
- Answer history for recent questions and answers
- Clear answer history

## Technologies Used

| Area | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python Flask |
| Vector Database | ChromaDB |
| PDF Processing | PyMuPDF |
| Local AI Model | Ollama |
| AI Model Used | llama3.2:1b |
| API Cost | Free, local model |

## Project Structure

```text
ai-study-assistant-rag/
│
├── backend/
│   └── app.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── uploads/
│   └── .gitkeep
│
├── data/
│   ├── processed_notes/
│   └── vector_db/
│
├── requirements.txt
├── .gitignore
└── README.md

## How the RAG Workflow Works

1. The user uploads a PDF study note.
2. The backend extracts text from the PDF.
3. The extracted text is cleaned to remove unnecessary spacing and formatting issues.
4. The cleaned text is split into smaller chunks.
5. The chunks are stored in ChromaDB.
6. When the user asks a question, the app searches for the most relevant note chunks.
7. The selected chunks are sent to the local Ollama model.
8. The AI generates an answer using only the uploaded notes.
9. The app displays the answer and optional source details.

## How to Run the Project Locally

### 1. Clone the Repository

```cmd
git clone https://github.com/stonemagar/ai-study-assistant-rag.git
cd ai-study-assistant-rag
```

### 2. Create a Virtual Environment

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Required Packages

```cmd
pip install -r requirements.txt
```

### 4. Create a `.env` File

Create a `.env` file in the main project folder.

Add this line inside the `.env` file:

```text
OLLAMA_MODEL=llama3.2:1b
```

Do not push the `.env` file to GitHub.

### 5. Install and Set Up Ollama

Check that Ollama is installed:

```cmd
ollama --version
```

Download the local model:

```cmd
ollama pull llama3.2:1b
```

Test the model:

```cmd
ollama run llama3.2:1b
```

Exit Ollama:

```text
/bye
```

### 6. Run the Flask Backend

Make sure the virtual environment is activated, then run:

```cmd
python backend/app.py
```

### 7. Open the Frontend

Open the project in VS Code.

Then open:

```text
frontend/index.html
```

Right-click the file and select:

```text
Open with Live Server
```

The app should open in your browser.

## Example Questions

After uploading machine learning notes, users can ask questions such as:

```text
What is overfitting?
How can overfitting be fixed?
What is underfitting?
What is data leakage?
```

If the answer is not available in the uploaded notes, the app should respond with:

```text
I could not find this in the uploaded notes.
```

## Limitations

* The app depends on the quality of text extracted from uploaded PDF files.
* The local Ollama model may respond more slowly than paid cloud AI models.
* Very large documents may need improved chunking and search optimisation.
* The current version is designed mainly for local use.
* The quiz output may vary slightly because quiz generation uses a more flexible AI temperature setting.
* The app currently does not include user login or saved chat history.

## Future Improvements

* Add user login and authentication.
* Add support for multiple subjects.
* Add saved chat history.
* Improve document management.
* Add export options for summaries and quizzes.
* Improve quiz formatting.
* Add stronger support for DOCX notes.
* Improve the user interface for mobile screens.
* Deploy the app online.

## Author

Stone Magar

MSc Computer Science
York St John University
