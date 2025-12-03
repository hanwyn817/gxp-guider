// Function to apply blur effect to a single image element
function applyBlurToImage(imgElement, blurRadius = 20) {
    // Find the parent container (thumbnail-wrapper)
    const container = imgElement.closest('.thumbnail-wrapper');
    if (!container) {
        console.warn('No parent .thumbnail-wrapper found for image', imgElement);
        return;
    }

    // Find the blur background element within the container
    const blurBgElement = container.querySelector('.thumbnail-blur-bg');
    if (!blurBgElement) {
        console.warn('No .thumbnail-blur-bg element found within container', container);
        return;
    }

    // Create an off-screen canvas to draw and blur the image
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Set canvas dimensions to match the image display dimensions
    // We need to wait for the image to load to get its natural dimensions
    // and calculate the display size within its container
    
    // For simplicity and performance in this example, we'll use a fixed size
    // A more robust solution would calculate the displayed size more precisely
    const displayWidth = imgElement.clientWidth || imgElement.width || 200;
    const displayHeight = imgElement.clientHeight || imgElement.height || 200;
    
    // Use a smaller size for the blur canvas to improve performance
    const scaleFactor = 0.1; 
    canvas.width = displayWidth * scaleFactor;
    canvas.height = displayHeight * scaleFactor;

    try {
        // Draw the image onto the canvas, scaled down
        ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);

        // Apply StackBlur to the canvas
        StackBlur.canvasRGB(canvas, 0, 0, canvas.width, canvas.height, blurRadius * scaleFactor);

        // Convert the blurred canvas to a data URL
        const blurredDataUrl = canvas.toDataURL('image/png');

        // Apply the blurred image as the background of the blur-bg element
        blurBgElement.style.backgroundImage = `url(${blurredDataUrl})`;
        blurBgElement.style.backgroundSize = 'cover';
        blurBgElement.style.backgroundPosition = 'center';
        // Reset any fallback styles
        blurBgElement.style.backgroundColor = '';
        blurBgElement.style.opacity = '0.8';
    } catch (e) {
        console.warn('Failed to blur image, applying fallback. Image URL:', imgElement.src, 'Error:', e);
        // Apply a fallback style (e.g., a subtle gray background)
        // You can customize this color or even use a subtle pattern
        blurBgElement.style.backgroundImage = 'none';
        blurBgElement.style.backgroundColor = '#f3f4f6'; // Tailwind's gray-100 or similar
        blurBgElement.style.opacity = '1'; // Make fallback fully opaque
    }
}

// Function to initialize blur effect for all images on the page
function initBlurThumbnails() {
    // Select all images inside .thumbnail-wrapper that have a src
    const images = document.querySelectorAll('.thumbnail-wrapper img[src]:not([src=""])');

    images.forEach(img => {
        if (img.complete) {
            // If the image is already loaded, apply the blur immediately
            applyBlurToImage(img);
        } else {
            // Otherwise, wait for it to load
            img.addEventListener('load', () => {
                applyBlurToImage(img);
            }, { once: true }); // Ensure the event listener is removed after firing once
            
            // Handle image load errors
            img.addEventListener('error', (e) => {
                console.warn('Image failed to load:', img.src, e);
                const container = img.closest('.thumbnail-wrapper');
                if (container) {
                    const blurBgElement = container.querySelector('.thumbnail-blur-bg');
                    if (blurBgElement) {
                        // Apply fallback on load error as well
                        blurBgElement.style.backgroundImage = 'none';
                        blurBgElement.style.backgroundColor = '#f3f4f6'; // Tailwind's gray-100 or similar
                        blurBgElement.style.opacity = '1';
                    }
                }
            }, { once: true });
        }
    });
}

// Run the initialization when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Small delay to ensure images start loading
    setTimeout(initBlurThumbnails, 100);
});

// Optional: Re-run if new content is dynamically added (e.g., via AJAX/pagination)
// You can call initBlurThumbnails() again after new elements are added to the DOM.