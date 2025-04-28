// Helper functions for Django AJAX requests

// Get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Standard headers for Django AJAX requests
function getAjaxHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
    };
}

// Django-friendly fetch function
function djangoFetch(url, options = {}) {
    // Merge default headers with any provided headers
    const headers = {
        ...getAjaxHeaders(),
        ...(options.headers || {})
    };
    
    // Return fetch with merged options
    return fetch(url, {
        ...options,
        headers
    });
}
