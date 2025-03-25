(function($){
    $(document).ready(function() {
        function toggleFields(role) {
            // Hide all fields initially
            $('#id_district, #id_assigned_circuit, #id_school').closest('.form-row').hide();

            // Show the appropriate field based on the selected role
            if (role == 'cis') {
                $('#id_district').closest('.form-row').show();  // Show district for cis
            } else if (role == 'siso') {
                $('#id_assigned_circuit').closest('.form-row').show();  // Show circuit for siso
            } else if (role == 'headteacher' || role == 'teacher') {
                $('#id_school').closest('.form-row').show();  // Show school for headteacher/teacher
            }
        }

        // Trigger the function when the role field changes
        $('#id_role').change(function() {
            toggleFields($(this).val());
        });

        // Initial call to set the correct field visibility on page load
        toggleFields($('#id_role').val());
    });
})(django.jQuery);
