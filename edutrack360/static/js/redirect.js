// static/js/redirect.js

window.onload = function() {
    setTimeout(function() {
        const userRole = document.body.getAttribute('data-user-role');
        
        if (userRole === 'cis') {
            window.location.href = document.body.getAttribute('data-cis-url');
        } else if (userRole === 'siso') {
            window.location.href = document.body.getAttribute('data-siso-url');
        } else if (userRole === 'headteacher') {
            window.location.href = document.body.getAttribute('data-headteacher-url');
        } else if (userRole === 'teacher') {
            window.location.href = document.body.getAttribute('data-teacher-url');
        } else {
            window.location.href = document.body.getAttribute('data-homepage-url');
        }
    }, 3000);  // Redirect after 3 seconds
}
