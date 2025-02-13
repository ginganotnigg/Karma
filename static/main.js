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

        let images = [];
        if (lang === "vi_VN") {
            images = [
                { index: 0, src: "/static/assets/id-0.png", alt: "Reader 0" }
            ];
        } else {
            images = [
                { index: 0, src: "/static/assets/id-0.png", alt: "Reader 0" },
                { index: 1, src: "/static/assets/id-1.png", alt: "Reader 1" },
                { index: 2, src: "/static/assets/id-2.png", alt: "Reader 2" },
                { index: 3, src: "/static/assets/id-3.png", alt: "Reader 3" }
            ];
        }

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

        document.getElementById("tts-loading").style.display = "block";
        document.getElementById("tts-result").innerText = "";

        if (!text) {
            alert("Please enter text to speak.");
            document.getElementById("tts-loading").style.display = "none";
            return;
        }

        fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                "content": text,
                "lang": lang,
                "reader": readerIndex
            })
        })
            .then(response => response.json())
            .then(data => {
                document.getElementById("tts-loading").style.display = "none";
                document.getElementById("tts-result").innerText = data.Message || "TTS triggered successfully!";
            })
            .catch(error => {
                document.getElementById("tts-loading").style.display = "none";
                document.getElementById("tts-result").innerText = "Error: " + error;
            });
    });
});