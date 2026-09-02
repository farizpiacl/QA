// QA Portal PIA — Module 5: reusable dynamic Activity form engine.
//
// This file is intentionally generic. Modules 6-8 add new activity-type
// fields purely on the server (via app.utils.activity_registry) and this
// script picks them up automatically through the `.activity-type-fieldset
// [data-type-code]` markup the template already renders — no JS changes
// needed per activity type.
//
// Responsibilities:
//   1. Activity Type card selection -> sets the hidden `activity_type`
//      input and reveals the common + type-specific fields.
//   2. Conditional fields: only the fieldset matching the selected type is
//      shown; every other type's fields are hidden AND disabled so they
//      are never submitted (avoids leaking irrelevant/stale data).
//   3. Client-side required-field validation with clear inline messages,
//      purely for responsiveness — the server re-validates everything
//      regardless (see app/utils/activity_forms.py).
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("addActivityForm");
    if (!form) return;

    var typeCards = document.querySelectorAll(".activity-type-select");
    var typeInput = document.getElementById("activityTypeInput");
    var detailsSection = document.getElementById("activityDetailsSection");
    var heading = document.getElementById("selectedTypeHeading");
    var fieldsets = document.querySelectorAll(".activity-type-fieldset");

    function labelFor(code) {
      var card = document.querySelector('.activity-type-select[data-type-code="' + code + '"]');
      return card ? card.querySelector(".fw-semibold").textContent.trim() : "";
    }

    function setFieldsetEnabled(fieldset, enabled) {
      var controls = fieldset.querySelectorAll("input, select, textarea");
      controls.forEach(function (el) {
        el.disabled = !enabled;
      });
      fieldset.classList.toggle("d-none", !enabled);
    }

    function selectType(code) {
      typeInput.value = code;

      typeCards.forEach(function (card) {
        card.classList.toggle("border-primary", card.getAttribute("data-type-code") === code);
      });

      fieldsets.forEach(function (fieldset) {
        setFieldsetEnabled(fieldset, fieldset.getAttribute("data-type-code") === code);
      });

      if (heading) heading.textContent = labelFor(code);
      if (detailsSection) detailsSection.classList.toggle("d-none", !code);

      clearFieldError(typeInput.closest("form"));
    }

    typeCards.forEach(function (card) {
      card.addEventListener("click", function () {
        selectType(card.getAttribute("data-type-code"));
      });
      // Keyboard accessibility — cards are role="button".
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectType(card.getAttribute("data-type-code"));
        }
      });
    });

    // Restore state on a re-render after a failed server-side submission.
    if (typeInput.value) {
      selectType(typeInput.value);
    }

    function clearFieldError(el) {
      if (!el) return;
      el.classList.remove("is-invalid");
    }

    // --- Lightweight client-side required-field validation ----------------
    // Mirrors the server's checks for immediate feedback; never a
    // replacement for them.
    form.addEventListener("submit", function (e) {
      var firstInvalid = null;
      var missing = [];

      if (!typeInput.value) {
        missing.push("Activity Type");
        firstInvalid = firstInvalid || document.getElementById("activityTypeCards");
      }

      var visibleRequired = form.querySelectorAll(
        "#activityDetailsSection [required]:not(:disabled)"
      );
      visibleRequired.forEach(function (el) {
        var value = el.type === "checkbox" ? el.checked : (el.value || "").trim();
        if (!value) {
          el.classList.add("is-invalid");
          if (!firstInvalid) firstInvalid = el;
          var labelEl = form.querySelector('label[for="' + el.id + '"]');
          missing.push(labelEl ? labelEl.textContent.replace("*", "").trim() : el.name);
        } else {
          el.classList.remove("is-invalid");
        }
      });

      if (missing.length) {
        e.preventDefault();
        showFormError(
          "Please fill in the required field(s): " + missing.join(", ") + "."
        );
        if (firstInvalid && firstInvalid.scrollIntoView) {
          firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    });

    function showFormError(message) {
      var existing = document.getElementById("clientValidationAlert");
      if (existing) existing.remove();

      var alertEl = document.createElement("div");
      alertEl.id = "clientValidationAlert";
      alertEl.className = "alert alert-danger";
      alertEl.setAttribute("role", "alert");
      alertEl.textContent = message;
      form.parentNode.insertBefore(alertEl, form);
    }
  });
})();
