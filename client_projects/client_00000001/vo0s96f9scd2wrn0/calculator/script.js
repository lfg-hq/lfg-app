// Get the result input element
const result = document.getElementById('result');

// Function to append values to the display
function appendToDisplay(value) {
    result.value += value;
}

// Function to clear the display
function clearDisplay() {
    result.value = '';
}

// Function to calculate the result
function calculate() {
    try {
        // Use eval to calculate the expression (with proper error handling)
        result.value = eval(result.value);
        
        // Handle cases where result is not a number or is infinity
        if (isNaN(result.value) || !isFinite(result.value)) {
            result.value = 'Error';
        }
    } catch (error) {
        // If there's an error in the calculation
        result.value = 'Error';
    }
}

// Add keyboard support
document.addEventListener('keydown', function(event) {
    const key = event.key;
    
    // Numbers and operators
    if (/[0-9+\-*/.=]/.test(key)) {
        // Prevent default action for these keys
        event.preventDefault();
        
        // If equals key is pressed
        if (key === '=') {
            calculate();
        } else {
            appendToDisplay(key);
        }
    }
    
    // Enter key for calculate
    if (key === 'Enter') {
        event.preventDefault();
        calculate();
    }
    
    // Backspace for delete
    if (key === 'Backspace') {
        event.preventDefault();
        result.value = result.value.slice(0, -1);
    }
    
    // Escape or Delete for clear
    if (key === 'Escape' || key === 'Delete') {
        event.preventDefault();
        clearDisplay();
    }
});
