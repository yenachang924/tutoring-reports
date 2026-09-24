// Progressive enhancement: the server and database still validate every save.
const reportForm = document.querySelector('.report-form');
const saveButton = reportForm?.querySelector('button[type="submit"]');

if (reportForm && saveButton) {
  const originalLabel = saveButton.innerHTML;
  reportForm.addEventListener('submit', (event) => {
    if (saveButton.disabled) {
      event.preventDefault();
      return;
    }
    saveButton.disabled = true;
    saveButton.textContent = '저장 중…';
    reportForm.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    saveButton.disabled = false;
    saveButton.innerHTML = originalLabel;
    reportForm.removeAttribute('aria-busy');
  });
}
