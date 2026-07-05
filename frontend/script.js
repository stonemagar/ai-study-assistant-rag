console.log("JavaScript file loaded");

document.addEventListener("DOMContentLoaded", function () {
    console.log("HTML page fully loaded");

    const uploadForm = document.getElementById("uploadForm");
    const fileInput = document.getElementById("fileInput");
    const uploadResult = document.getElementById("uploadResult");

    console.log("Upload form:", uploadForm);
    console.log("File input:", fileInput);
    console.log("Upload result:", uploadResult);

    uploadForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        console.log("Upload button clicked");

        if (!fileInput.files[0]) {
            uploadResult.innerHTML = "Please choose a file first.";
            return;
        }

        uploadResult.innerHTML = "Uploading file...";

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        try {
            const response = await fetch("http://127.0.0.1:5000/upload", {
                method: "POST",
                body: formData
            });

            console.log("Response received:", response);

            const result = await response.json();
            console.log("Result:", result);

            uploadResult.innerHTML = `
                <p><strong>Status:</strong> ${result.status}</p>
                <p><strong>Message:</strong> ${result.message}</p>
                <p><strong>Filename:</strong> ${result.filename}</p>
                <p><strong>Total chunks:</strong> ${result.total_chunks || "N/A"}</p>
                <p><strong>Total vectors:</strong> ${result.total_vectors || "N/A"}</p>
            `;
        } catch (error) {
            console.log("Error:", error);
            uploadResult.innerHTML = "Error: Backend is not responding or request is blocked.";
        }
    });
});

const questionForm = document.getElementById("questionForm");
const questionInput = document.getElementById("questionInput");
const searchResult = document.getElementById("searchResult");

questionForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const question = questionInput.value;

    searchResult.innerHTML = "Searching your notes...";

    try {
        const response = await fetch("http://127.0.0.1:5000/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question
            })
        });

        const result = await response.json();

        console.log("Search result:", result);

        const documents = result.results.documents[0];

        let output = `<p><strong>Question:</strong> ${result.question}</p>`;
        output += `<h3>Most relevant notes:</h3>`;

        documents.forEach(function (doc, index) {
            output += `
                <div class="result-box">
                    <h4>Result ${index + 1}</h4>
                    <p>${doc}</p>
                </div>
            `;
        });

        searchResult.innerHTML = output;

    } catch (error) {
        console.log("Search error:", error);
        searchResult.innerHTML = "Error: Could not search notes.";
    }
});