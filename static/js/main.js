// HeatShield Core Client-Side Utilities
// Double-submission protection, GPS location extraction, and UI interactions

document.addEventListener("DOMContentLoaded", function () {
  // 1. Prevent double submission on crucial forms (Check-in and SOS)
  const protectForms = document.querySelectorAll("form.prevent-double-submit");
  protectForms.forEach(function (form) {
    form.addEventListener("submit", function (e) {
      const submitBtn = form.querySelector("button[type='submit']");
      if (submitBtn) {
        if (submitBtn.dataset.submitted === "true") {
          e.preventDefault();
          return false;
        }
        submitBtn.dataset.submitted = "true";
        submitBtn.disabled = true;
        const originalText = submitBtn.innerText;
        submitBtn.innerText = "Transmitting...";
        
        // Safety timeout to re-enable in case of client cancel
        setTimeout(function () {
          submitBtn.disabled = false;
          submitBtn.innerText = originalText;
          submitBtn.dataset.submitted = "false";
        }, 8000);
      }
    });
  });

  // 2. Geolocation "Use My Location" helper
  const geoButtons = document.querySelectorAll(".btn-use-location");
  geoButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      const latInput = document.querySelector(btn.dataset.latTarget || "#latitude");
      const lonInput = document.querySelector(btn.dataset.lonTarget || "#longitude");
      const statusSpan = document.querySelector(btn.dataset.statusTarget || "#geo-status");

      if (!navigator.geolocation) {
        if (statusSpan) statusSpan.innerText = "Geolocation not supported by this browser.";
        alert("Geolocation is not supported by your browser.");
        return;
      }

      if (statusSpan) statusSpan.innerText = "Detecting GPS coordinates...";
      btn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        function (pos) {
          if (latInput) latInput.value = pos.coords.latitude.toFixed(6);
          if (lonInput) lonInput.value = pos.coords.longitude.toFixed(6);
          if (statusSpan) statusSpan.innerText = "Location locked from GPS.";
          btn.disabled = false;
        },
        function (err) {
          if (statusSpan) statusSpan.innerText = "GPS error. Using city center default.";
          btn.disabled = false;
          console.warn("Geolocation failure:", err.message);
        },
        { timeout: 8000, enableHighAccuracy: true }
      );
    });
  });
});
