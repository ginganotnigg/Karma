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

    // Speed slider functionality
    const speedSlider = document.getElementById("speed-slider");
    const speedValueDisplay = document.getElementById("speed-value");

    speedSlider.addEventListener("input", function () {
        speedValueDisplay.textContent = this.value;
    });

    document.getElementById("tts-button").addEventListener("click", () => {
        const text = document.getElementById("tts-text").value.trim();
        const lang = document.getElementById("tts-lang").value;
        const readerIndex = document.getElementById("tts-reader-id").value;
        const speed = speedSlider.value;

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
                "gender": (readerIndex == 0) ? "female" : "male",
                "speed": speed
            })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.Error || "An error occurred.");
                    });
                }
                return response.json(); // Get JSON response
            })
            .then(data => {
                if (data && data.audio) {
                    // Decode base64 and play audio
                    playMp3FromBase64(data.audio);
                } else {
                    document.getElementById("result").innerText = "Error: Audio data not found in response.";
                }
            })
            .catch(error => {
                document.getElementById("result").innerText = "Error: " + error.message;
            })
            .finally(() => {
                document.getElementById("loading").style.display = "none";
            });
    });

    document.getElementById("lip-sync-button").addEventListener("click", () => {
        const text = document.getElementById("tts-text").value.trim();
        const lang = document.getElementById("tts-lang").value;
        const readerIndex = document.getElementById("tts-reader-id").value;
        const speed = document.getElementById("speed-slider").value;

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
                "gender": (readerIndex == 0) ? "female" : "male",
                "speed": speed
            })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || "An error occurred.");
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data) {
                    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
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

    function playMp3FromBase64(base64) {
      try {
        const decodedBytes = base64ToUint8Array(base64);
        const blob = new Blob([decodedBytes], { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);

        const audio = new Audio(url);
        audio.addEventListener('error', (error) => {
          console.error('Audio playback error:', error);
          document.getElementById("result").innerText = "Error playing audio.";
        });
        audio.play();

        audio.onended = () => URL.revokeObjectURL(url);
        document.getElementById("result").innerText = "Audio played successfully!";
      } catch (error) {
          console.error("Error playing MP3:", error);
          document.getElementById("result").innerText = "Error playing audio.";
      }
    }

    function base64ToUint8Array(base64) {
      try {
        const binaryString = atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes;
      } catch (error) {
        console.error("Base64 decoding error:", error);
        document.getElementById("result").innerText = "Error decoding audio.";
        return null;
      }
    }
});