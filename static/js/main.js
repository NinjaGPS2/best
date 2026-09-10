document.addEventListener('DOMContentLoaded', function() {
    // 1. Live Clock in Top Navbar
    const clockEl = document.getElementById('liveClock');
    if (clockEl) {
        function updateClock() {
            const now = new Date();
            const options = { 
                weekday: 'short', 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            };
            clockEl.textContent = now.toLocaleDateString('km-KH', options);
        }
        setInterval(updateClock, 1000);
        updateClock();
    }

    // 2. Modal Controls
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
        }
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    };

    // Close modal when clicking outside of modal-content
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('show');
            }
        });
    });

    // 3. Dynamic Meter Reading auto-fetch and Live kWh Calculation
    const meterSelect = document.getElementById('meterSelect');
    const prevValueInput = document.getElementById('prevValueInput');
    const currValueInput = document.getElementById('currValueInput');
    const kwhDisplay = document.getElementById('kwhDisplay');

    if (meterSelect && prevValueInput && currValueInput) {
        meterSelect.addEventListener('change', function() {
            const meterId = this.value;
            if (!meterId) return;

            fetch(`/api/meter/${meterId}/latest-reading`)
                .then(res => res.json())
                .then(data => {
                    prevValueInput.value = data.previous_reading;
                    calculateKwh();
                })
                .catch(err => console.error('Error fetching meter reading:', err));
        });

        function calculateKwh() {
            const prev = parseFloat(prevValueInput.value) || 0;
            const curr = parseFloat(currValueInput.value) || 0;
            const diff = curr - prev;

            if (kwhDisplay) {
                if (curr < prev) {
                    kwhDisplay.innerHTML = `<span style="color: #ef4444; font-weight: 700;">⚠️ លេខថ្មីមិនអាចតូចជាងលេខចាស់ទេ!</span>`;
                } else {
                    kwhDisplay.innerHTML = `<span style="color: #10b981; font-weight: 700;">${diff.toFixed(1)} kWh</span> (ប្រើប្រាស់ខែនេះ)`;
                }
            }
        }

        currValueInput.addEventListener('input', calculateKwh);
        prevValueInput.addEventListener('input', calculateKwh);
    }

    // 4. Photo Preview for Meter Upload
    const photoInput = document.getElementById('meterPhotoInput');
    const photoPreview = document.getElementById('photoPreview');
    if (photoInput && photoPreview) {
        photoInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    photoPreview.src = e.target.result;
                    photoPreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 5. Auto dismiss flash alerts after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.flash-message').forEach(el => {
            el.style.transition = 'opacity 0.5s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 500);
        });
    }, 5000);
});
