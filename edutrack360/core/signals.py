from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from core.models import Result, StudentMark, Student, Notification


@receiver(post_save, sender=Result)
def create_or_update_student_mark(sender, instance, created, **kwargs):
    """Automatically create a Student if not found & update StudentMark when a Result is uploaded"""

    with transaction.atomic():  # Ensure atomicity to prevent partial updates
        if not instance.student:  # If no student is linked, attempt to create one
            teacher = instance.teacher
            school = teacher.school if teacher else None
            circuit = teacher.circuit if teacher else None
            district = teacher.district if teacher else None

            # Ensure a class group is linked before proceeding
            if instance.class_group:
                # Generate a student name dynamically (Fallback Placeholder)
                default_first_name = "Unknown"
                default_last_name = f"Student {instance.id}"

                student, _ = Student.objects.get_or_create(
                    first_name=default_first_name,
                    last_name=default_last_name,
                    school=school,
                    class_group=instance.class_group,  # Student inherits class_group
                    defaults={"circuit": circuit, "district": district}
                )

                instance.student = student  # Link the student to the result
                instance.save()

        # Now update or create StudentMark
        student_mark, created = StudentMark.objects.update_or_create(
            student=instance.student,
            subject=instance.subject,
            academic_year=instance.academic_year,
            term=instance.term,
            class_group=instance.class_group,
            defaults={"mark": instance.final_mark}
        )

        print(f"{'Created' if created else 'Updated'} StudentMark for {instance.student} - {instance.subject}")


@receiver(post_save, sender=Result)
def create_notification_for_result_upload(sender, instance, created, **kwargs):
    """Creates a notification when a teacher uploads results."""
    if created:
        Notification.objects.create(
            recipient=instance.school.headteacher,
            sender=instance.teacher,
            message=f"{instance.teacher.first_name} {instance.teacher.last_name} uploaded {instance.subject.name} results for {instance.class_group.name}."
        )

