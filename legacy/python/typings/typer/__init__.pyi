from typing import Any, Callable, TypeVar

_T = TypeVar("_T")


class Exit(Exception):
    exit_code: int

    def __init__(self, code: int = ...) -> None: ...


def run(function: Callable[..., Any]) -> None: ...


def Argument(*args: Any, **kwargs: Any) -> Any: ...


def Option(*args: Any, **kwargs: Any) -> Any: ...
