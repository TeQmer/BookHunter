// Main JavaScript for BookHunter

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Add loading state to forms
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            var submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Загрузка...';
                submitBtn.disabled = true;
            }
        });
    });

    // Search functionality
    var searchInput = document.getElementById('search-input');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(function() {
                performSearch(searchInput.value);
            }, 300);
        });
    }

    // Price formatting
    var priceElements = document.querySelectorAll('.price');
    priceElements.forEach(function(element) {
        var price = parseFloat(element.textContent);
        if (!isNaN(price)) {
            element.textContent = new Intl.NumberFormat('ru-RU', {
                style: 'currency',
                currency: 'RUB'
            }).format(price);
        }
    });

    // Discount color coding
    var discountElements = document.querySelectorAll('.discount');
    discountElements.forEach(function(element) {
        var discount = parseInt(element.textContent);
        if (!isNaN(discount)) {
            if (discount >= 30) {
                element.classList.add('text-danger');
            } else if (discount >= 20) {
                element.classList.add('text-warning');
            } else {
                element.classList.add('text-success');
            }
        }
    });
});

// Search function
function performSearch(query) {
    if (query.length < 2) return;
    
    var resultsContainer = document.getElementById('search-results');
    if (!resultsContainer) return;
    
    // Очищаем запрос от знаков пунктуации
    var cleanedQuery = query.replace(/[,\.\!\?\:\;\-\—\(\)\[\]\{\}<>]/g, ' ').trim().replace(/\s+/g, ' ');

    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div></div>';
    
    fetch(`/web/books/api/search?q=${encodeURIComponent(cleanedQuery)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data, resultsContainer);
        })
        .catch(error => {
            console.error('Search error:', error);
            resultsContainer.innerHTML = '<div class="text-danger">Ошибка поиска</div>';
        });
}

// Display search results
function displaySearchResults(data, container) {
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="text-muted">Ничего не найдено</div>';
        return;
    }
    
    var html = '';
    data.forEach(function(book) {
        html += `
            <div class="card mb-2">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="card-title mb-1">${book.title}</h6>
                            <p class="card-text text-muted mb-1">${book.author || 'Автор неизвестен'}</p>
                            <small class="text-muted">${book.source}</small>
                        </div>
                        <div class="text-end">
                            <div class="fw-bold text-success">${formatPrice(book.current_price)}</div>
                            ${book.discount_percent ? `<div class="badge bg-danger">-${book.discount_percent}%</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Format price
function formatPrice(price) {
    if (!price) return 'Цена не указана';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB'
    }).format(price);
}

// Confirm delete actions
function confirmDelete(message) {
    return confirm(message || 'Вы уверены, что хотите удалить этот элемент?');
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Скопировано в буфер обмена', 'success');
    }).catch(function() {
        showToast('Ошибка копирования', 'error');
    });
}

// Show toast notification
function showToast(message, type = 'info') {
    var toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    var toastContainer = document.getElementById('toast-container') || createToastContainer();
    toastContainer.appendChild(toast);
    
    var bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Create toast container if it doesn't exist
function createToastContainer() {
    var container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

// AJAX helpers
function makeRequest(url, options = {}) {
    return fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    });
}

// Form validation
function validateForm(form) {
    var isValid = true;
    var requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Real-time price update (for admin panel)
function updatePrice(bookId, newPrice) {
    makeRequest(`/api/books/${bookId}/price`, {
        method: 'PUT',
        body: JSON.stringify({ price: newPrice })
    })
    .then(data => {
        showToast('Цена обновлена', 'success');
        location.reload();
    })
    .catch(error => {
        showToast('Ошибка обновления цены', 'error');
    });
}

// Toggle alert status
function toggleAlert(alertId) {
    makeRequest(`/api/alerts/${alertId}/toggle`, {
        method: 'POST'
    })
    .then(data => {
        showToast('Статус подписки изменен', 'success');
        location.reload();
    })
    .catch(error => {
        showToast('Ошибка изменения статуса', 'error');
    });
}
