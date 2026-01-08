// ROB2 Report Interactive Features

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Highlight citation when clicked from evidence reference
    document.querySelectorAll('.evidence-refs a').forEach(link => {
        link.addEventListener('click', function() {
            // Remove previous highlights
            document.querySelectorAll('.citation').forEach(c => {
                c.classList.remove('highlighted');
            });
            
            // Add highlight to target
            const targetId = this.getAttribute('href');
            const target = document.querySelector(targetId);
            if (target) {
                target.classList.add('highlighted');
                setTimeout(() => {
                    target.classList.remove('highlighted');
                }, 3000);
            }
        });
    });
});

// Add CSS for highlighting dynamically
const style = document.createElement('style');
style.textContent = `
    .citation.highlighted {
        background-color: #fff3cd !important;
        border-left-color: #ffc107 !important;
        transition: background-color 0.3s ease;
    }
`;
document.head.appendChild(style);
