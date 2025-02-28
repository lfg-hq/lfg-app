document.addEventListener('DOMContentLoaded', () => {
    // Header scroll effect
    const header = document.querySelector('header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });

    // Testimonial slider
    const testimonials = document.querySelectorAll('.testimonial');
    const dots = document.querySelectorAll('.dot');
    const prevButton = document.querySelector('.prev-button');
    const nextButton = document.querySelector('.next-button');
    let currentTestimonial = 0;
    
    // Hide all testimonials except the first one
    testimonials.forEach((testimonial, index) => {
        if (index !== 0) {
            testimonial.style.display = 'none';
        }
    });
    
    // Show a specific testimonial
    function showTestimonial(index) {
        testimonials.forEach(testimonial => {
            testimonial.style.display = 'none';
        });
        testimonials[index].style.display = 'block';
        
        // Update active dot
        dots.forEach(dot => {
            dot.classList.remove('active');
        });
        dots[index].classList.add('active');
        
        currentTestimonial = index;
    }
    
    // Event listeners for dots
    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            showTestimonial(index);
        });
    });
    
    // Event listeners for prev/next buttons
    prevButton.addEventListener('click', () => {
        let index = currentTestimonial - 1;
        if (index < 0) index = testimonials.length - 1;
        showTestimonial(index);
    });
    
    nextButton.addEventListener('click', () => {
        let index = currentTestimonial + 1;
        if (index >= testimonials.length) index = 0;
        showTestimonial(index);
    });
    
    // Auto-rotate testimonials
    setInterval(() => {
        let index = currentTestimonial + 1;
        if (index >= testimonials.length) index = 0;
        showTestimonial(index);
    }, 8000);
    
    // Animate the airplane path
    const airplane = document.querySelector('.airplane');
    
    function updateAirplanePath() {
        const time = Date.now() * 0.001;
        const x = Math.sin(time * 0.5) * 60;
        const y = Math.cos(time * 0.3) * 30 - 20;
        
        if (airplane) {
            airplane.style.transform = `translate(${x}px, ${y}px) rotate(${x * 0.5}deg)`;
        }
        
        requestAnimationFrame(updateAirplanePath);
    }
    
    updateAirplanePath();
    
    // Add reveal animations for sections
    const revealElements = document.querySelectorAll('.feature-card, .step, .showcase-item, .pricing-card');
    
    function checkReveal() {
        const windowHeight = window.innerHeight;
        const revealPoint = 150;
        
        revealElements.forEach(element => {
            const revealTop = element.getBoundingClientRect().top;
            
            if (revealTop < windowHeight - revealPoint) {
                element.classList.add('revealed');
            }
        });
    }
    
    // Initial check
    checkReveal();
    
    // Check on scroll
    window.addEventListener('scroll', checkReveal);
    
    // Particle animation
    const particles = document.querySelectorAll('.particle');
    
    particles.forEach(particle => {
        // Random initial position
        const x = Math.random() * 100 - 50;
        const y = Math.random() * 100 - 50;
        particle.style.transform = `translate(${x}px, ${y}px)`;
    });
}); 