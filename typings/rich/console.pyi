from typing import Any


class Console:
    def __init__(self, *, stderr: bool = ..., **kwargs: Any) -> None: ...

    def print(self, *objects: Any, **kwargs: Any) -> None: ...
