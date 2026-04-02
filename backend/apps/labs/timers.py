from django.utils import timezone

def end_session(session):
    session.status = "COMPLETED"
    session.ended_at = timezone.now()
    session.save()

