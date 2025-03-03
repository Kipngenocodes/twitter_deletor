// General functionality for the Twitter Manager

// Confirm deletions
function confirmDelete(event) {
    if (!confirm('Are you sure you want to delete this tweet?')) {
        event.preventDefault();
        return false;
    }
    return true;
}

// Initialize tooltips and popovers if using Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap 5 tooltip initialization
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Bootstrap 5 popover initialization
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});