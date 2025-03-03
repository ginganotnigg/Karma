document.addEventListener("DOMContentLoaded", function () {

    const attachReaderListeners = () => {
        document.querySelectorAll('.reader-img').forEach(image => {
            image.addEventListener('click', function () {
                document.querySelectorAll('.reader-img').forEach(img => img.classList.remove('selected'));
                this.classList.add('selected');
                const readerIndex = this.getAttribute('data-reader-index');
                document.getElementById('tts-reader-id').value = readerIndex;
            });
        });
    }

    const updateReaderSelection = () => {
        const lang = document.getElementById("tts-lang").value;
        const container = document.getElementById("reader-selection");
        container.innerHTML = "";

        let images = [
            { index: 0, src: "/static/assets/id-0.png", alt: "Female" },
            { index: 1, src: "/static/assets/id-3.png", alt: "Male" }
        ];

        images.forEach(imgData => {
            const img = document.createElement("img");
            img.src = imgData.src;
            img.alt = imgData.alt;
            img.width = 80;
            img.classList.add("reader-img");
            img.setAttribute("data-reader-index", imgData.index);
            container.appendChild(img);
        });
        attachReaderListeners();
        container.firstChild.classList.add("selected");
        document.getElementById('tts-reader-id').value = images[0].index;
    }
    updateReaderSelection();
    document.getElementById("tts-lang").addEventListener("change", () => {
        updateReaderSelection();
    });

    document.getElementById("tts-button").addEventListener("click", () => {
        const text = document.getElementById("tts-text").value.trim();
        const lang = document.getElementById("tts-lang").value;
        const readerIndex = document.getElementById("tts-reader-id").value;

        document.getElementById("loading").style.display = "block";
        document.getElementById("result").innerText = "";

        if (!text) {
            alert("Please enter text to speak.");
            document.getElementById("loading").style.display = "none";
            return;
        }

        fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                "content": text,
                "language": lang,
                "gender": (readerIndex == 0) ? "female" : "male"
            })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.Error || "An error occurred.");
                    });
                }
                return response.blob(); // Get the response as a blob (binary data)
            })
            .then(blob => {
                // Create a temporary URL for the blob
                const url = window.URL.createObjectURL(blob);

                // Create a temporary link to download the file
                const link = document.createElement('a');
                link.href = url;
                const filename = `tts_audio_${Date.now()}.mp3`;
                link.download = filename;
                link.click();

                // Release the object URL
                window.URL.revokeObjectURL(url);

                document.getElementById("result").innerText = "Audio downloaded successfully!";

            })
            .catch(error => {
                document.getElementById("result").innerText = "Error: " + error.message;
            })
            .finally(() => {
                document.getElementById("loading").style.display = "none";
            });
    });

    // Lip Sync functionality
    document.getElementById("lip-sync-button").addEventListener("click", () => {
        const text = document.getElementById("tts-text").value.trim();
        const lang = document.getElementById("tts-lang").value;
        const readerIndex = document.getElementById("tts-reader-id").value;

        document.getElementById("loading").style.display = "block";
        document.getElementById("result").innerText = "";

        if (!text) {
            alert("Please enter text to speak.");
            document.getElementById("loading").style.display = "none";
            return;
        }

        fetch("/api/lip-sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                "content": text,
                "language": lang,
                "gender": (readerIndex == 0) ? "female" : "male"
            })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || "An error occurred.");
                    });
                }
                return response.json(); // Get the response as JSON
            })
            .then(data => {
                if (data.json_result) {
                    document.getElementById("result").innerText = JSON.stringify(data.json_result, null, 2);
                } else {
                    document.getElementById("result").innerText = "Failed to generate lip sync.";
                }
            })
            .catch(error => {
                document.getElementById("result").innerText = "Error: " + error.message;
            })
            .finally(() => {
                document.getElementById("loading").style.display = "none";
            });
    });
});