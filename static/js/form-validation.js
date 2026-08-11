/**
 * Inline form validation helpers.
 * Activated by data-validate attributes on inputs:
 *   data-validate="email"      -> RFC-ish email format
 *   data-validate="phone-ke"   -> Kenyan phone: fixed +254 prefix + 9 digits
 *   data-validate="password"   -> length >= 8, at least 1 special character
 *   data-validate="confirm"    -> must match input[name="password"]
 */
(function () {
  "use strict";

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const SPECIAL_RE = /[^A-Za-z0-9]/; // any non-alphanumeric counts as special

  function setValidity(input, ok, message) {
    input.classList.toggle("is-invalid", !ok);
    input.classList.toggle("is-valid", ok && input.value.length > 0);
    let fb = input.parentElement.querySelector(".invalid-feedback.js-fb");
    if (!fb) {
      fb = document.createElement("div");
      fb.className = "invalid-feedback js-fb";
      input.parentElement.appendChild(fb);
    }
    fb.textContent = ok ? "" : message;
  }

  // ---------- Email ----------
  function wireEmail(input) {
    const check = () => {
      const v = input.value.trim();
      if (!v && !input.required) {
        input.classList.remove("is-invalid", "is-valid");
        return true;
      }
      const ok = EMAIL_RE.test(v);
      setValidity(input, ok, "Enter a valid email address (e.g. name@example.com).");
      return ok;
    };
    input.addEventListener("input", check);
    input.addEventListener("blur", check);
    input.form && input.form.addEventListener("submit", (e) => {
      if (!check()) { e.preventDefault(); input.focus(); }
    });
  }

  // ---------- Phone (+254) ----------
  function wirePhone(input) {
    // Hide the real input and render an input-group with fixed +254 prefix.
    input.type = "hidden";
    const wrap = document.createElement("div");
    wrap.className = "input-group";
    const prefix = document.createElement("span");
    prefix.className = "input-group-text";
    prefix.textContent = "+254";
    const visible = document.createElement("input");
    visible.type = "tel";
    visible.inputMode = "numeric";
    visible.autocomplete = "tel-national";
    visible.className = "form-control";
    visible.placeholder = "7XXXXXXXX";
    visible.maxLength = 9;
    // Pre-populate from any existing +254XXXXXXXXX value.
    const existing = (input.value || "").replace(/^\+?254/, "").replace(/\D/g, "");
    visible.value = existing.slice(0, 9);

    wrap.appendChild(prefix);
    wrap.appendChild(visible);
    input.parentElement.insertBefore(wrap, input);
    const fb = document.createElement("div");
    fb.className = "invalid-feedback js-fb d-block";
    input.parentElement.appendChild(fb);

    function sync() {
      let digits = visible.value.replace(/\D/g, "");
      // Ignore a leading 0 the user might type out of habit.
      if (digits.startsWith("0")) digits = digits.slice(1);
      digits = digits.slice(0, 9);
      visible.value = digits;
      const ok = digits.length === 9;
      visible.classList.toggle("is-invalid", !ok);
      visible.classList.toggle("is-valid", ok);
      fb.textContent = ok ? "" : "Enter the 9 digits after +254 (e.g. 769964274).";
      input.value = ok ? "+254" + digits : "";
    }
    visible.addEventListener("input", sync);
    visible.addEventListener("blur", sync);
    sync();
    input.form && input.form.addEventListener("submit", (e) => {
      sync();
      if (!input.value) { e.preventDefault(); visible.focus(); }
    });
  }

  // ---------- Password checklist ----------
  const LETTER_RE = /[A-Za-z]/;
  const DIGIT_RE = /\d/;

  function wirePassword(input) {
    const list = document.createElement("ul");
    list.className = "list-unstyled small mt-2 mb-0 password-checklist";
    list.innerHTML =
      '<li data-rule="len"><i class="bi bi-x-circle text-danger"></i> At least 8 characters</li>' +
      '<li data-rule="letter"><i class="bi bi-x-circle text-danger"></i> At least 1 letter</li>' +
      '<li data-rule="digit"><i class="bi bi-x-circle text-danger"></i> At least 1 number</li>' +
      '<li data-rule="special"><i class="bi bi-x-circle text-danger"></i> At least 1 special character (e.g. , : .)</li>';
    input.parentElement.appendChild(list);

    function evaluate() {
      const v = input.value || "";
      const rules = {
        len: v.length >= 8,
        letter: LETTER_RE.test(v),
        digit: DIGIT_RE.test(v),
        special: SPECIAL_RE.test(v),
      };
      list.querySelectorAll("li").forEach((li) => {
        const ok = rules[li.dataset.rule];
        const icon = li.querySelector("i");
        icon.className = ok
          ? "bi bi-check-circle-fill text-success"
          : "bi bi-x-circle text-danger";
        li.classList.toggle("text-success", ok);
        li.classList.toggle("text-muted", !ok);
      });
      const allOk = Object.values(rules).every(Boolean);
      input.classList.toggle("is-invalid", !allOk && v.length > 0);
      input.classList.toggle("is-valid", allOk);
      return allOk;
    }
    input.addEventListener("input", evaluate);
    input.addEventListener("blur", evaluate);
    input.form && input.form.addEventListener("submit", (e) => {
      if (!evaluate()) { e.preventDefault(); input.focus(); }
    });
  }

  // ---------- Confirm password ----------
  function wireConfirm(input) {
    const pwd = input.form && input.form.querySelector('input[name="password"]');
    const check = () => {
      const ok = pwd && input.value === pwd.value && input.value.length > 0;
      setValidity(input, ok, "Passwords do not match.");
      return ok;
    };
    input.addEventListener("input", check);
    input.addEventListener("blur", check);
    pwd && pwd.addEventListener("input", check);
    input.form && input.form.addEventListener("submit", (e) => {
      if (!check()) { e.preventDefault(); input.focus(); }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('[data-validate="email"]').forEach(wireEmail);
    document.querySelectorAll('[data-validate="phone-ke"]').forEach(wirePhone);
    document.querySelectorAll('[data-validate="password"]').forEach(wirePassword);
    document.querySelectorAll('[data-validate="confirm"]').forEach(wireConfirm);
  });
})();
