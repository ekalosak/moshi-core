from loguru import logger
from pydantic import BaseModel

from moshi import Message
from moshi.utils import lang
from moshi.core.activities import BaseActivity

class Goal(BaseModel):
    title: str
    description: str
    examples: list[str]

class Translation(BaseModel):
    goals: list[Goal]
    title: str
    user_prompt: str


class Unstructured(BaseActivity):
    @property
    def goals(self, language: str=None) -> list[Goal]:
        language = language or self.user.language
        return [Goal(g) for g in self._translations[language]["goals"]]
    
    @property
    def title(self, language: str=None) -> str:
        language = language or self.user.language
        return self._translations[language]["title"]

    @property
    def user_prompt(self, language: str=None) -> str:
        language = language or self.user.language
        return self._translations[language]["user_prompt"]

    def _translate_activity(self):
        """Translate the goals, title, and user_prompt. Does NOT write to Firestore."""
        # NOTE assumes the activity is initially written in us-EN
        logger.debug(f"_translations={self._translations}")
        enUS = Translation(**self._translations["en-US"])
        title = lang.translate_text(enUS.title, self.user.language)
        user_prompt = lang.translate_text(enUS.user_prompt, self.user.language)
        goals = []
        for goal in enUS.goals:
            title = lang.translate_text(goal.title, self.user.language)
            description = lang.translate_text(goal.description, self.user.language)
            examples = []
            if len(goal.examples) > 0:
                for ex in goal.examples:
                    ex_ = lang.translate_text(ex, self.user.language)
                    examples.append(ex_)
            goals.append(Goal(title=title, description=description, examples=examples))
        self._translations[self.user.language] = Translation(
            goals=goals, title=title, user_prompt=user_prompt
        ).model_dump()
        self.doc.set({"translations": self._translations}, merge=True)

    def prompt(self) -> list[Message]:
        raise NotImplementedError