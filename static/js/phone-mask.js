/**
 * Phone number mask formatter
 * Formato objetivo: 300 123 4567 (10 dígitos)
 */

function formatPhoneNumber(value) {
    const digits = value.replace(/\D/g, '').slice(0, 10);

    if (digits.length <= 3) {
        return digits;
    }
    if (digits.length <= 6) {
        return `${digits.slice(0, 3)} ${digits.slice(3)}`;
    }
    return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6, 10)}`;
}

/**
 * Only get numeric part (without +) for submission
 */
function getPhoneDigitsOnly(value) {
    return value.replace(/[^\d]/g, '');
}

/**
 * Apply phone mask to input field
 */
function applyPhoneMask(inputElement) {
    const input = inputElement;
    
    // Handler for input event
    const handleInput = (e) => {
        let cursorPos = input.selectionStart;
        const oldValue = input.value;
        const formatted = formatPhoneNumber(oldValue);
        
        if (formatted !== oldValue) {
            input.value = formatted;
            
            // Adjust cursor position based on length difference
            const diff = formatted.length - oldValue.length;
            input.selectionStart = cursorPos + diff;
            input.selectionEnd = cursorPos + diff;
        }
    };
    
    // Handler for paste event
    const handlePaste = (e) => {
        e.preventDefault();
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        const cleaned = pastedText.replace(/[^\d+]/g, '');
        const formatted = formatPhoneNumber(cleaned);
        input.value = formatted;
        input.selectionStart = formatted.length;
        input.selectionEnd = formatted.length;
    };
    
    input.addEventListener('input', handleInput);
    input.addEventListener('paste', handlePaste);
    
    // Initial formatting if there's already a value
    if (input.value) {
        input.value = formatPhoneNumber(input.value);
    }
    
    // Store the cleanup function for potential removal
    input._phoneMaskCleanup = () => {
        input.removeEventListener('input', handleInput);
        input.removeEventListener('paste', handlePaste);
        delete input._phoneMaskCleanup;
    };
}

/**
 * Remove phone mask listeners from an input
 */
function removePhoneMask(inputElement) {
    if (inputElement._phoneMaskCleanup) {
        inputElement._phoneMaskCleanup();
    }
}

// Auto-apply to all elements with data-phone-mask attribute on page load
document.addEventListener('DOMContentLoaded', () => {
    const phoneInputs = document.querySelectorAll('[data-phone-mask]');
    phoneInputs.forEach(applyPhoneMask);
});
