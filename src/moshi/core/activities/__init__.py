from enum import Enum
from loguru import logger
from .core import BaseActivity, sample_activity_id
from .lesson import Lesson
from .unstructured import Unstructured

class ActivityType(str, Enum):
    UNSTRUCTURED = "unstructured"  # talk about anything, user-driven, random topic.
    # TOPICAL = "topical"  # talk about a specific topic e.g. sports, politics, etc.
    LESSON = "lesson"  # e.g. (beginner, introductions), (intermediate, small talk), (advanced, debate), play out a scenario e.g. a job interview, ordering coffee, etc.

def new(activity_type, usr) -> BaseActivity:
    """Create a new activity for the user."""
    if activity_type == ActivityType.UNSTRUCTURED:
        return Unstructured(user=usr)
    elif activity_type == ActivityType.LESSON:
        return Lesson(user=usr)
    else:
        raise ValueError(f"Invalid activity type: {activity_type}")

logger.success("Activities module loaded.")