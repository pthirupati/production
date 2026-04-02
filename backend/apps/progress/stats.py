from .models import UserScenarioProgress

def get_user_stats(user):
    total = UserScenarioProgress.objects.filter(user=user).count()
    completed = UserScenarioProgress.objects.filter(
        user=user,
        completed=True
    ).count()

    return {
        "total_attempted": total,
        "completed": completed,
        "completion_rate": (completed / total * 100) if total else 0,
    }

