from loguru import logger
from pydantic import BaseModel

from moshi import Message, Role
from moshi.utils import lang
from moshi.core.activities import BaseActivity

class Criterion(BaseModel):
    body: str
    points: int

class Goal(BaseModel):
    title: str
    criteria: list[Criterion]

class Translation(BaseModel):
    goals: list[Goal]
    title: str
    user_prompt: str
    character_prompt: str
    vocabulary: list[str]

class Lesson(BaseActivity):
    @property
    def goals(self, language: str=None) -> list[Goal]:
        language = language or self.user.language
        logger.debug(f"json goals={self._translations[language]['goals']}")
        return [Goal(**g) for g in self._translations[language]["goals"]]
    
    @property
    def title(self, language: str=None) -> str:
        language = language or self.user.language
        return self._translations[language]["title"]

    @property
    def user_prompt(self, language: str=None) -> str:
        language = language or self.user.language
        return self._translations[language]["user_prompt"]

    @property
    def character_prompt(self, language: str=None) -> str:
        language = language or self.user.language
        return self._translations[language]["character_prompt"]

    @property
    def vocab(self, language: str=None) -> list[str]:
        language = language or self.user.language
        return self._translations[language]["vocabulary"]

    def _translate_activity(self):
        """Translate the goals, title, and user_prompt. Does NOT write to Firestore."""
        # NOTE assumes the activity is initially written in us-EN
        logger.debug(f"_translations={self._translations}")
        enUS = Translation(**self._translations["en-US"])
        title = lang.translate_text(enUS.title, self.user.language)
        user_prompt = lang.translate_text(enUS.user_prompt, self.user.language)
        character_prompt = lang.translate_text(enUS.character_prompt, self.user.language)
        goals = []
        for goal in enUS.goals:
            title = lang.translate_text(goal.title, self.user.language)
            criteria = []
            if len(goal.criteria) > 0:
                for cri in goal.criteria:
                    translated_body = lang.translate_text(cri.body, self.user.language)
                    criteria.append(Criterion(body=translated_body, points=cri.points))
            goals.append(Goal(title=title, criteria=criteria))
        vocab = []
        if len(enUS.vocabulary) > 0:
            for word in enUS.vocabulary:
                vocab.append(lang.translate_text(word, self.user.language))
        self._translations[self.user.language] = Translation(
            goals=goals, title=title, user_prompt=user_prompt, character_prompt=character_prompt, vocabulary=vocab
        ).model_dump()
        self.doc.set({"translations": self._translations}, merge=True)

    @property
    def prompt(self) -> list[Message]:
        """Return the prompt for the lesson, to be used for LLM completions."""
        msgs = []
        for i, goal in enumerate(self.goals):
            msgs.append(Message(
                role=Role.SYS,
                body=f"goal {i}: {goal.model_dump_json()}",
            ))
        msgs.append(Message(
            role=Role.SYS,
            body=f"vocabulary: {self.vocab}",
        ))
        msgs.append(Message(
            role=Role.SYS,
            body=self.user_prompt,
        ))
        msgs.append(Message(
            role=Role.SYS,
            body=self.character_prompt,
        ))
        logger.debug(f"prompt={msgs}")
        return msgs