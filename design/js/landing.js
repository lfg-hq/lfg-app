document.addEventListener('DOMContentLoaded', function() {
  // Mobile menu toggle
  const menuToggle = document.getElementById('menu-toggle');
  const mobileMenu = document.getElementById('mobile-menu');
  
  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener('click', function() {
      mobileMenu.classList.toggle('hidden');
    });
  }
  
  // Testimonial carousel
  const slides = document.getElementById('testimonial-slides');
  const slide1Btn = document.getElementById('slide-1');
  const slide2Btn = document.getElementById('slide-2');
  const slide3Btn = document.getElementById('slide-3');
  
  if (slides && slide1Btn && slide2Btn && slide3Btn) {
    slide1Btn.addEventListener('click', function() {
      slides.style.transform = 'translateX(0)';
      slide1Btn.classList.add('bg-purple-600');
      slide1Btn.classList.remove('bg-gray-600');
      slide2Btn.classList.add('bg-gray-600');
      slide2Btn.classList.remove('bg-purple-600');
      slide3Btn.classList.add('bg-gray-600');
      slide3Btn.classList.remove('bg-purple-600');
    });
    
    slide2Btn.addEventListener('click', function() {
      slides.style.transform = 'translateX(-100%)';
      slide1Btn.classList.add('bg-gray-600');
      slide1Btn.classList.remove('bg-purple-600');
      slide2Btn.classList.add('bg-purple-600');
      slide2Btn.classList.remove('bg-gray-600');
      slide3Btn.classList.add('bg-gray-600');
      slide3Btn.classList.remove('bg-purple-600');
    });
    
    slide3Btn.addEventListener('click', function() {
      slides.style.transform = 'translateX(-200%)';
      slide1Btn.classList.add('bg-gray-600');
      slide1Btn.classList.remove('bg-purple-600');
      slide2Btn.classList.add('bg-gray-600');
      slide2Btn.classList.remove('bg-purple-600');
      slide3Btn.classList.add('bg-purple-600');
      slide3Btn.classList.remove('bg-gray-600');
    });
  }
});
