from enum import Enum
from loguru import logger

from moshi import User
from .core import BaseActivity, sample_activity_id
from .lesson import Lesson
from .unstructured import Unstructured

class ActivityType(str, Enum):
    UNSTRUCTURED = "unstructured"  # talk about anything, user-driven, random topic.
    # TOPICAL = "topical"  # talk about a specific topic e.g. sports, politics, etc.
    LESSON = "lesson"  # e.g. (beginner, introductions), (intermediate, small talk), (advanced, debate), play out a scenario e.g. a job interview, ordering coffee, etc.

def new(activity_type: str, usr: User, level: int=1, name: str | None = None, latest: bool=True, start=True) -> BaseActivity:
    """Create a new activity for the user."""
    aid = sample_activity_id(
        activity_type=activity_type,
        name=name,
        level=level,
        latest=latest,
    )
    if activity_type == ActivityType.UNSTRUCTURED.value:
        act = Unstructured(user=usr)
    elif activity_type == ActivityType.LESSON.value:
        act = Lesson(user=usr)
    else:
        raise ValueError(f"Invalid activity type: '{activity_type}', must be one of {[m.value for m in ActivityType.__members__.values()]}")
    if start:
        act.start(aid)
    return act

logger.success("Activities module loaded.")