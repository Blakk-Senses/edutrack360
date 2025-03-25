from django.core.mail import send_mail

def send_performance_alert(school, term, year, score):
    """Sends an alert if performance drops below the threshold."""
    if score < 45:
        subject = f"⚠️ Performance Drop Alert - {school.name}"
        message = f"The average performance for {school.name} in {term}, {year} has dropped to {score:.2f}%. Immediate attention is required!"
        send_mail(subject, message, "admin@school.com", ["headteacher@school.com"])
