from loguru import logger
from pydantic import BaseModel

from moshi import Message, Role
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
    character_prompt: str

class Unstructured(BaseActivity):
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
            description = lang.translate_text(goal.description, self.user.language)
            examples = []
            if len(goal.examples) > 0:
                for ex in goal.examples:
                    ex_ = lang.translate_text(ex, self.user.language)
                    examples.append(ex_)
            goals.append(Goal(title=title, description=description, examples=examples))
        self._translations[self.user.language] = Translation(
            goals=goals, title=title, user_prompt=user_prompt, character_prompt=character_prompt
        ).model_dump()
        self.doc.set({"translations": self._translations}, merge=True)

    @property
    def prompt(self) -> list[Message]:
        msgs = []
        msg = Message(
            role=Role.SYS,
            body=self.character_prompt,
        )
        msgs.append(msg)
        msg = Message(
            role=Role.SYS,
            body=self.user_prompt,
        )
        msgs.append(msg)
        # TODO figure out a way to provide the "goal glue" in the target language.
        # e.g. saying "for example" here in en-US will not get translated.
        for goal in self.goals:
            payload = f"{goal.title}. {goal.description}. "
            for example in goal.examples:
                payload += f"'{example}', "
            payload = payload[:-2] + "."
            msg = Message(
                role=Role.SYS,
                body=payload,
            )
            msgs.append(msg)
        logger.debug(f"prompt={msgs}")
        return msgs