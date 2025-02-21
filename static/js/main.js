// Handle dark/light mode toggle
document.addEventListener('DOMContentLoaded', function() {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    function setTheme(e) {
        if (e.matches) {
            document.documentElement.setAttribute('data-bs-theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-bs-theme', 'light');
        }
    }

    prefersDark.addListener(setTheme);
    setTheme(prefersDark);

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle file upload preview
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name;
            const fileLabel = document.querySelector('.custom-file-label');
            if (fileLabel) {
                fileLabel.textContent = fileName || 'Choose file';
            }
        });
    }
});

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Handle AJAX form submissions
document.querySelectorAll('form[data-remote]').forEach(form => {
    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(form);
        const url = form.action;

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showAlert('success', data.message);
            } else {
                showAlert('danger', data.message);
            }
        })
        .catch(error => {
            showAlert('danger', 'An error occurred. Please try again.');
        });
    });
});

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);

    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Enhanced suggestion handling
document.querySelectorAll('.suggest-account-btn').forEach(button => {
    button.addEventListener('click', async function() {
        const transactionId = this.dataset.transactionId;
        const description = this.dataset.description;
        const explanation = this.dataset.explanation;
        const suggestionsDiv = document.getElementById(`suggestions-${transactionId}`);

        if (!suggestionsDiv) {
            console.error('Suggestions container not found');
            return;
        }

        try {
            const response = await fetch('/predict_account', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    description,
                    explanation
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const suggestions = await response.json();
            updateSuggestionsDisplay(suggestionsDiv, suggestions);

        } catch (error) {
            console.error('Error:', error);
            showErrorMessage(suggestionsDiv, error.message);
        }
    });
});

function updateSuggestionsDisplay(suggestionsDiv, suggestions) {
    suggestionsDiv.innerHTML = ''; // Clear previous suggestions
    suggestions.forEach(suggestion => {
        const suggestionElement = document.createElement('div');
        suggestionElement.textContent = suggestion;
        suggestionsDiv.appendChild(suggestionElement);
    });
}

function showErrorMessage(suggestionsDiv, message) {
    const errorElement = document.createElement('div');
    errorElement.textContent = message;
    errorElement.style.color = 'red';
    suggestionsDiv.appendChild(errorElement);
}