document.addEventListener("DOMContentLoaded", function () {
    var roleField = document.getElementById("id_role");
    var districtField = document.getElementById("id_district").closest(".form-row");
    var circuitField = document.getElementById("id_assigned_circuit").closest(".form-row");
    var schoolField = document.getElementById("id_school").closest(".form-row");

    function toggleFields() {
        var selectedRole = roleField.value;
        
        districtField.style.display = "none";
        circuitField.style.display = "none";
        schoolField.style.display = "none";

        if (selectedRole === "cis") {
            districtField.style.display = "block";
        } else if (selectedRole === "siso") {
            circuitField.style.display = "block";
        } else if (selectedRole === "headteacher" || selectedRole === "teacher") {
            schoolField.style.display = "block";
        }
    }

    toggleFields();
    roleField.addEventListener("change", toggleFields);
});
