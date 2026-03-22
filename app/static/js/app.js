/**
 * JananiSuraksha — Shared JavaScript Utilities
 * AI-Powered Maternal Health Risk Intelligence
 * Powered by dmj.one
 */

/**
 * Returns a Tailwind color class string for a given risk level.
 * @param {string} level - One of: LOW, MEDIUM, HIGH, CRITICAL
 * @returns {string} Tailwind CSS class string
 */
function formatRiskLevel(level) {
    const map = {
        'LOW':      'bg-green-100 text-green-800 border-green-300',
        'MEDIUM':   'bg-yellow-100 text-yellow-800 border-yellow-300',
        'HIGH':     'bg-orange-100 text-orange-800 border-orange-300',
        'CRITICAL': 'bg-red-100 text-red-800 border-red-300'
    };
    return map[(level || '').toUpperCase()] || 'bg-gray-100 text-gray-800 border-gray-300';
}

/**
 * Returns display text and a Tailwind color class for a blood bank status.
 * @param {string} status - One of: available, limited, unavailable, unknown
 * @returns {string} Human-readable status text
 */
function formatBloodBank(status) {
    const map = {
        'available':   'Available',
        'limited':     'Limited Stock',
        'unavailable': 'Not Available',
        'unknown':     'Unknown'
    };
    return map[(status || '').toLowerCase()] || status || 'Unknown';
}

/**
 * Returns a Tailwind color class for blood bank status badges.
 * @param {string} status
 * @returns {string} Tailwind CSS class string
 */
function formatBloodBankColor(status) {
    const map = {
        'available':   'bg-green-100 text-green-700',
        'limited':     'bg-yellow-100 text-yellow-700',
        'unavailable': 'bg-red-100 text-red-700',
        'unknown':     'bg-gray-100 text-gray-700'
    };
    return map[(status || '').toLowerCase()] || 'bg-gray-100 text-gray-700';
}

/**
 * Smoothly animates a number counter from 0 to target.
 * @param {HTMLElement} element - The DOM element whose textContent will be updated
 * @param {number} target - The target number to count up to
 * @param {number} [duration=1500] - Animation duration in milliseconds
 * @param {string} [suffix=''] - Optional suffix to append (e.g., '%')
 */
function animateCounter(element, target, duration, suffix) {
    if (!element) return;
    duration = duration || 1500;
    suffix = suffix || '';
    const startTime = performance.now();
    const startValue = parseInt(element.textContent, 10) || 0;
    const delta = target - startValue;

    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    function tick(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(progress);
        const current = Math.floor(startValue + delta * eased);
        element.textContent = current.toLocaleString('en-IN') + suffix;
        if (progress < 1) {
            requestAnimationFrame(tick);
        } else {
            element.textContent = target.toLocaleString('en-IN') + suffix;
        }
    }

    requestAnimationFrame(tick);
}

/**
 * Escapes HTML special characters to prevent XSS.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.textContent;
}

/**
 * Shows a toast notification.
 * @param {string} message - The notification message
 * @param {string} [type='info'] - One of: success, error, warning, info
 * @param {number} [durationMs=4000] - How long to show (ms)
 */
function showNotification(message, type, durationMs) {
    type = type || 'info';
    durationMs = durationMs || 4000;

    var container = document.getElementById('toast-container');
    if (!container) {
        console.warn('[JananiSuraksha] Toast container not found. Message:', message);
        return;
    }

    var iconPaths = {
        success: 'M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z',
        error: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z',
        warning: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z',
        info: 'M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z'
    };

    var bgColors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-500',
        info: 'bg-blue-600'
    };

    var bgClass = bgColors[type] || bgColors.info;
    var iconPath = iconPaths[type] || iconPaths.info;

    // Build toast using safe DOM methods
    var toast = document.createElement('div');
    toast.className = bgClass + ' text-white px-4 py-3 rounded-lg shadow-lg flex items-center space-x-3 max-w-sm transform translate-x-full transition-transform duration-300 ease-out';
    toast.setAttribute('role', 'alert');

    // Icon SVG
    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'w-5 h-5 flex-shrink-0');
    svg.setAttribute('fill', 'currentColor');
    svg.setAttribute('viewBox', '0 0 20 20');
    var path = document.createElementNS(svgNS, 'path');
    path.setAttribute('fill-rule', 'evenodd');
    path.setAttribute('d', iconPath);
    path.setAttribute('clip-rule', 'evenodd');
    svg.appendChild(path);
    toast.appendChild(svg);

    // Message text
    var msgEl = document.createElement('p');
    msgEl.className = 'text-sm font-medium flex-1';
    msgEl.textContent = message;
    toast.appendChild(msgEl);

    // Dismiss button
    var closeBtn = document.createElement('button');
    closeBtn.className = 'ml-2 text-white text-opacity-70 hover:text-opacity-100 focus:outline-none';
    closeBtn.setAttribute('aria-label', 'Dismiss');
    closeBtn.addEventListener('click', function() {
        toast.remove();
    });
    var closeSvg = document.createElementNS(svgNS, 'svg');
    closeSvg.setAttribute('class', 'w-4 h-4');
    closeSvg.setAttribute('fill', 'currentColor');
    closeSvg.setAttribute('viewBox', '0 0 20 20');
    var closePath = document.createElementNS(svgNS, 'path');
    closePath.setAttribute('fill-rule', 'evenodd');
    closePath.setAttribute('d', 'M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z');
    closePath.setAttribute('clip-rule', 'evenodd');
    closeSvg.appendChild(closePath);
    closeBtn.appendChild(closeSvg);
    toast.appendChild(closeBtn);

    container.appendChild(toast);

    // Trigger slide-in animation
    requestAnimationFrame(function() {
        toast.classList.remove('translate-x-full');
        toast.classList.add('translate-x-0');
    });

    // Auto-remove after duration
    setTimeout(function() {
        toast.classList.remove('translate-x-0');
        toast.classList.add('translate-x-full');
        setTimeout(function() {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }, durationMs);
}
