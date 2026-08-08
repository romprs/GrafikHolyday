from dataclasses import dataclass


@dataclass
class Violation:
    code: str
    message_ru: str
    params: dict
