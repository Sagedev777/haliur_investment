// =========================
// Document Ready
// =========================
document.addEventListener("DOMContentLoaded", function() {

    // =========================
    // Filter Tables by Search Input
    // =========================
    const filterInputs = document.querySelectorAll('.table-filter');
    filterInputs.forEach(input => {
        input.addEventListener('keyup', function() {
            const tableId = this.dataset.table;
            const filter = this.value.toLowerCase();
            const table = document.getElementById(tableId);
            if (!table) return;
            const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            for (let row of rows) {
                row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none';
            }
        });
    });

    // =========================
    // Bootstrap tooltips
    // =========================
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // =========================
    // Toggle filter forms (optional)
    // =========================
    const filterToggles = document.querySelectorAll('.filter-toggle');
    filterToggles.forEach(btn => {
        btn.addEventListener('click', function() {
            const target = document.querySelector(this.dataset.target);
            if (target) target.classList.toggle('d-none');
        });
    });

    // =========================
    // Smooth scroll for anchor links
    // =========================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

});
