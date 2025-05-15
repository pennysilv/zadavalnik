from enum import Enum, auto

class UserState(Enum):
    START = auto()
    AWAITING_TOPIC = auto()
    IN_TEST = auto()
    TEST_COMPLETED = auto()