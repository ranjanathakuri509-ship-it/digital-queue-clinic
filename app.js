document.querySelectorAll('.flash').forEach((el, i) => setTimeout(() => { if (el) el.remove(); }, 5000 + i * 300));

// Set the appointment date to today when a patient opens the form.
const dateInput = document.querySelector('input[type="date"][name="appointment_date"]');
if (dateInput && !dateInput.value) {
  dateInput.value = new Date().toISOString().slice(0, 10);
  dateInput.min = dateInput.value;
}
