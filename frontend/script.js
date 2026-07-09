console.log("JavaScript file loaded");

document.addEventListener("DOMContentLoaded", function () {
    const uploadForm = document.getElementById("uploadForm");
    const fileInput = document.getElementById("fileInput");
    const uploadResult = document.getElementById("uploadResult");

    const questionForm = document.getElementById("questionForm");
    const questionInput = document.getElementById("questionInput");
    const searchResult = document.getElementById("searchResult");

    const clearNotesBtn = document.getElementById("clearNotesBtn");
    const clearResult = document.getElementById("clearResult");
    
    const summaryBtn = document.getElementById("summaryBtn");
    const summaryResult = document.getElementById("summaryResult");

    function formatText(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>");
    }

    uploadForm.addEventListener("submit", async function (event) {
        event.preventDefault();

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
            
            const result = await response.json();

            uploadResult.innerHTML = `
                <p><strong>Status:</strong> ${formatText(result.status)}</p>
                <p><strong>Message:</strong> ${formatText(result.message)}</p>
                <p><strong>Filename:</strong> ${formatText(result.filename)}</p>
                <p><strong>Total chunks:</strong> ${result.total_chunks || "N/A"}</p>
                <p><strong>Total vectors:</strong> ${result.total_vectors || "N/A"}</p>
            `;
        } catch (error) {
            console.log("Upload error:", error);
            uploadResult.innerHTML = "Error: Backend is not responding or request is blocked.";
        }
    });

    questionForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const question = questionInput.value.trim();

        if (!question) {
            searchResult.innerHTML = "Please type a question first.";
            return;
        }

        const askButton = questionForm.querySelector("button");

        askButton.disabled = true;
        askButton.textContent = "Thinking...";

        searchResult.innerHTML = "Thinking with your uploaded notes...";

        try {
            const response = await fetch("http://127.0.0.1:5000/ask", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    question: question
                })
            });

            const result = await response.json();
            const sources = result.source_details || [];

            let output = `
                <p><strong>Question:</strong> ${formatText(result.question)}</p>

                <div class="result-box answer-box">
                    <h4>AI Answer</h4>
                    <p>${formatText(result.answer)}</p>
                </div>
            `;

            if (sources.length > 0) {
                output += `
                    <button id="toggleSourcesBtn" class="secondary-button" type="button">
                        Show Sources
                    </button>

                    <div id="sourcesContainer" class="sources-panel hidden">
                        <h3>Retrieved Sources</h3>
                `;

                sources.forEach(function (source) {
                    output += `
                        <div class="result-box source-box">
                            <h4>Source ${source.source_number}</h4>
                            <p><strong>File:</strong> ${formatText(source.source_file)}</p>
                            <p><strong>Chunk:</strong> ${formatText(String(source.chunk_number))}</p>
                            <p><strong>Text:</strong></p>
                            <p>${formatText(source.text)}</p>
                        </div>
                    `;
                });

                output += `</div>`;
            }

            searchResult.innerHTML = output;

            askButton.disabled = false;
            askButton.textContent = "Ask";

            const toggleSourcesBtn = document.getElementById("toggleSourcesBtn");
            const sourcesContainer = document.getElementById("sourcesContainer");

            if (toggleSourcesBtn && sourcesContainer) {
                toggleSourcesBtn.addEventListener("click", function () {
                    sourcesContainer.classList.toggle("hidden");

                    if (sourcesContainer.classList.contains("hidden")) {
                        toggleSourcesBtn.textContent = "Show Sources";
                    } else {
                        toggleSourcesBtn.textContent = "Hide Sources";
                    }
                });
            }
        } catch (error) {
            console.log("Search error:", error);
            searchResult.innerHTML = "Error: Could not search notes.";

            askButton.disabled = false;
            askButton.textContent = "Ask";
        }
    });

    if (clearNotesBtn) {
        clearNotesBtn.addEventListener("click", async function () {
            const confirmClear = confirm("Are you sure you want to clear all uploaded notes?");

            if (!confirmClear) {
                return;
            }

            clearNotesBtn.disabled = true;
            clearNotesBtn.textContent = "Clearing...";
            clearResult.innerHTML = "Clearing uploaded notes...";

            try {
                const response = await fetch("http://127.0.0.1:5000/clear-notes", {
                    method: "POST"
                });

                const result = await response.json();

                clearResult.innerHTML = result.message;
                searchResult.innerHTML = "";
                uploadResult.innerHTML = "";

            } catch (error) {
                console.log("Clear notes error:", error);
                clearResult.innerHTML = "Error: Could not clear notes.";
            }

            clearNotesBtn.disabled = false;
            clearNotesBtn.textContent = "Clear Notes";
        });
    }

    if (summaryBtn) {
    summaryBtn.addEventListener("click", async function () {
        summaryBtn.disabled = true;
        summaryBtn.textContent = "Summarising...";
        summaryResult.innerHTML = "Summarising your uploaded notes...";

        try {
            const response = await fetch("http://127.0.0.1:5000/summarise-notes", {
                method: "POST"
            });

            const result = await response.json();

            summaryResult.innerHTML = `
                <div class="result-box answer-box">
                    <h4>Notes Summary</h4>
                    <p>${formatText(result.summary)}</p>
                </div>
            `;

        } catch (error) {
            console.log("Summary error:", error);
            summaryResult.innerHTML = "Error: Could not summarise notes.";
        }

        summaryBtn.disabled = false;
        summaryBtn.textContent = "Summarise Notes";
    });
    }
});