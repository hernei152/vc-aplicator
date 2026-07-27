from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from typing import Annotated

# 1. El "pegamento" para la generalización
class QuestionArchetype(str, Enum):
    PROBLEM = "problem"
    SOLUTION = "solution"
    WHY_NOW = "why_now"
    WHY_YOU = "why_you"
    TEAM = "team"
    TRACTION = "traction"
    BUSINESS_MODEL = "business_model"
    MARKET_SIZE = "market_size"
    COMPETITION = "competition"
    MOAT = "moat"
    GTM = "gtm"
    PRODUCT_DEMO = "product_demo"
    TECH = "tech"
    MILESTONES = "milestones"
    ASK = "ask"
    USE_OF_FUNDS = "use_of_funds"
    RISKS = "risks"
    FAILURE_STORY = "failure_story"
    WHY_THIS_PROGRAM = "why_this_program"   # nunca se reusa
    LEGAL_ADMIN = "legal_admin"             # nunca se reusa
    OTHER = "other"                         # nunca se reusa

NON_SHAREABLE = {QuestionArchetype.WHY_THIS_PROGRAM, QuestionArchetype.LEGAL_ADMIN, QuestionArchetype.OTHER}

class BaseQuestion(BaseModel):
    original_text: str
    is_required: bool = True

class TextQuestion(BaseQuestion):
    type: Literal["text"] = "text"
    category: QuestionArchetype
    max_chars: Optional[int] = None

class MultipleChoiceQuestion(BaseQuestion):
    type: Literal["multiple_choice"] = "multiple_choice"
    archetype: QuestionArchetype       # también texto, también va al bank
    options: List[str]
    allow_multiple: bool = False

class VideoFocus(str, Enum):
    FOUNDER_INTRO = "founder_intro"
    PITCH = "pitch"
    DEMO = "demo"

class VideoQuestion(BaseQuestion):
    type: Literal["video"] = "video"
    focus: VideoFocus               
    min_seconds: Optional[int] = None
    max_seconds: Optional[int] = None
    orientation: Literal["h", "v", "any"] = "any"
    language: Literal["es", "en", "any"] = "any"
    who: Literal["solo", "all_founders", "any"] = "any"

AnyQuestion = Annotated[
    Union[TextQuestion, MultipleChoiceQuestion, VideoQuestion],
    Field(discriminator="type"),
]

class AcceleratorForm(BaseModel):
    accelerator_name: str = ...
    questions: List[AnyQuestion]       
    url: Optional[str] = Field(default=None, description="URL de la aceleradora")
    deadline: Optional[str] = Field(default=None, description="Deadline de la aceleradora")