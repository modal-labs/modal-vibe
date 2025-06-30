// Bouncing logo animation
function initBouncingLogo() {
    const logo = document.getElementById('bouncing-logo');
    if (!logo) return;

    const container = logo.parentElement;
    const logoWidth = 92; // 1/4 of original size
    const logoHeight = 48; // 1/4 of original size
    
    let x = Math.random() * (container.clientWidth - logoWidth);
    let y = Math.random() * (container.clientHeight - logoHeight);
    let dx = 1.5; // Slightly slower horizontal speed
    let dy = 1.5; // Slightly slower vertical speed

    function updatePosition() {
        // Update position
        x += dx;
        y += dy;

        // Bounce off walls
        if (x <= 0 || x >= container.clientWidth - logoWidth) {
            dx = -dx;
            changeLogo();
        }
        if (y <= 0 || y >= container.clientHeight - logoHeight) {
            dy = -dy;
            changeLogo();
        }

        // Apply position with hardware acceleration
        logo.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        requestAnimationFrame(updatePosition);
    }

    function changeLogo() {
        // Generate a random hue value
        const hue = Math.random() * 360;
        logo.style.filter = `hue-rotate(${hue}deg) brightness(1.2)`;
    }

    // Start the animation
    updatePosition();

    // Handle window resize
    window.addEventListener('resize', () => {
        // Keep logo within bounds after resize
        x = Math.min(x, container.clientWidth - logoWidth);
        y = Math.min(y, container.clientHeight - logoHeight);
    });
}

// Initialize when the DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBouncingLogo);
} else {
    initBouncingLogo();
} 