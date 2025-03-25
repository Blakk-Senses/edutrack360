document.addEventListener("DOMContentLoaded", function () {
    function getCSRFToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]").value;
    }

    document.querySelectorAll(".assign-subject").forEach(select => {
        select.addEventListener("change", function () {
            let teacherId = this.getAttribute("data-teacher");
            let subjectId = this.value;

            if (subjectId) {
                fetch(`/school/assign-subject/${teacherId}/${subjectId}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": getCSRFToken() }
                })
                .then(response => response.text())
                .then(html => {
                    document.getElementById(`assigned-subjects-${teacherId}`).innerHTML = html;
                });
            }
        });
    });

    document.querySelectorAll(".assign-class").forEach(select => {
        select.addEventListener("change", function () {
            let teacherId = this.getAttribute("data-teacher");
            let classId = this.value;

            if (classId) {
                fetch(`/school/assign-class/${teacherId}/${classId}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": getCSRFToken() }
                })
                .then(response => response.text())
                .then(html => {
                    document.getElementById(`assigned-classes-${teacherId}`).innerHTML = html;
                });
            }
        });
    });

    document.addEventListener("click", function(event) {
        if (event.target.classList.contains("remove-subject")) {
            let teacherId = event.target.getAttribute("data-teacher");
            let subjectId = event.target.getAttribute("data-subject");

            fetch(`/school/remove-subject/${teacherId}/${subjectId}/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCSRFToken() }
            })
            .then(response => response.text())
            .then(html => {
                document.getElementById(`assigned-subjects-${teacherId}`).innerHTML = html;
            });
        }
    });

    document.addEventListener("click", function(event) {
        if (event.target.classList.contains("remove-class")) {
            let teacherId = event.target.getAttribute("data-teacher");
            let classId = event.target.getAttribute("data-class");

            fetch(`/school/remove-class/${teacherId}/${classId}/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCSRFToken() }
            })
            .then(response => response.text())
            .then(html => {
                document.getElementById(`assigned-classes-${teacherId}`).innerHTML = html;
            });
        }
    });

    function loadSection(section) {
        let urls = {
            assign_teacher: "/school/assign-teacher/",
            assign_class: "/school/assign-class/",
            assign_subject: "/school/assign-subject/"
        };

        if (urls[section]) {
            fetch(urls[section], {
                method: "GET",
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.text())
            .then(html => {
                document.getElementById("dynamic-content").innerHTML = html;
            })
            .catch(error => console.error("Error loading section:", error));
        }
    }
});
