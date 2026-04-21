"""Shared JSON serialization/deserialization helpers for dataclass IR nodes."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from dataclasses import MISSING, dataclass, field, fields
from enum import StrEnum
from functools import cache
from typing import Any, ClassVar, Self, Union, cast, get_args, get_origin, get_type_hints

_SERDE_DEFAULT_KIND = object()


def _encode_json_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, StrEnum):
        return v.value
    to_json_dict = getattr(v, "to_json_dict", None)
    if callable(to_json_dict):
        return to_json_dict()
    if isinstance(v, list):
        return [_encode_json_value(x) for x in v]
    return v


def _decode_list(raw: Any, elem_type: Any, owner_cls: type) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise TypeError(f"expected list, got {type(raw).__name__}")
    out: list[Any] = []
    for x in raw:
        out.append(_decode_json_value(x, elem_type, owner_cls))
    return out


def _is_union_type(annotated_type: Any) -> bool:
    origin = get_origin(annotated_type)
    return origin in (Union, types.UnionType)


def _decode_json_value(raw: Any, annotated_type: Any, owner_cls: type) -> Any:
    if raw is None:
        return None

    if (
        dispatch := SerDeMixin._serde_union_dispatch_for(owner_cls, annotated_type)
    ) is not None and isinstance(raw, dict):
        return dispatch(raw)

    origin = get_origin(annotated_type)
    if origin is list:
        (elem_type,) = get_args(annotated_type) or (Any,)
        return _decode_list(raw, elem_type, owner_cls)

    if _is_union_type(annotated_type):
        args = tuple(arg for arg in get_args(annotated_type) if arg is not type(None))
        if len(args) == 1:
            return _decode_json_value(raw, args[0], owner_cls)
        if isinstance(raw, dict) and "kind" in raw:
            for arg in args:
                if (dispatch := SerDeMixin._serde_union_dispatch_for(owner_cls, arg)) is not None:
                    try:
                        return dispatch(raw)
                    except (TypeError, ValueError, KeyError):
                        continue
                from_json_dict = getattr(arg, "from_json_dict", None)
                if callable(from_json_dict):
                    try:
                        return from_json_dict(raw)
                    except (TypeError, ValueError, KeyError):
                        continue
        return raw

    if isinstance(annotated_type, type) and issubclass(annotated_type, StrEnum):
        return annotated_type(raw)

    from_json_dict = getattr(annotated_type, "from_json_dict", None)
    if callable(from_json_dict) and isinstance(raw, dict):
        return from_json_dict(raw)

    if isinstance(raw, dict) and "kind" in raw:
        raise TypeError(f"missing decoder for discriminated object kind={raw.get('kind')!r}")

    return raw


@dataclass(frozen=True)
class SerdeFieldSpec:
    """Small schema override for one dataclass field."""

    json_key: str | None = None
    missing_from: Callable[[dict[str, Any]], Any] | None = None
    encoder: Callable[[Any], Any] | None = None
    decoder: Callable[[Any], Any] | None = None
    omit_if_default: bool = False
    omit_when: Callable[[Any, Any], bool] | None = None


@dataclass(frozen=True)
class SerdeSpec:
    """Compact per-class SerDe overrides used by :class:`SerDeMixin`."""

    kind: str | None | object = _SERDE_DEFAULT_KIND
    field_order: tuple[str, ...] | None = None
    fields: dict[str, SerdeFieldSpec] = field(default_factory=dict)


@cache
def _type_hints_for_cls(cls: type) -> dict[str, Any]:
    module = sys.modules[cls.__module__]
    return get_type_hints(cls, vars(module), vars(module))


def _field_default_value(f: Any) -> Any:
    if f.default is not MISSING:
        return f.default
    if f.default_factory is not MISSING:  # type: ignore[comparison-overlap]
        return f.default_factory()
    return MISSING


class SerDeMixin:
    """Shared JSON serialization/deserialization mixin for IR dataclasses."""

    KIND: ClassVar[str | None] = None
    SERDE: ClassVar[SerdeSpec] = SerdeSpec()

    @classmethod
    def _serde_kind(cls) -> str | None:
        if cls.SERDE.kind is not _SERDE_DEFAULT_KIND:
            return cast(str | None, cls.SERDE.kind)
        if "KIND" in cls.__dict__:
            return cast(str | None, cls.__dict__["KIND"])
        return cls.__name__

    @classmethod
    def _serde_field_spec(cls, field_name: str) -> SerdeFieldSpec:
        return cls.SERDE.fields.get(field_name, SerdeFieldSpec())

    @classmethod
    def _serde_union_dispatch_for(
        cls, owner_cls: type, annotated_type: Any
    ) -> Callable[[dict[str, Any]], Any] | None:
        module = sys.modules[owner_cls.__module__]
        module_vars = vars(module)
        dispatch_pairs = (
            ("Type", "type_from_json"),
            ("ConstExpr", "const_expr_from_json"),
            ("Decl", "decl_from_json"),
            ("MojoType", "mojo_type_from_json"),
            ("StructMember", "struct_member_from_json"),
            ("MojoDecl", "mojo_decl_from_json"),
        )
        for alias_name, helper_name in dispatch_pairs:
            if annotated_type == module_vars.get(alias_name):
                return cast(Callable[[dict[str, Any]], Any], module_vars.get(helper_name))
        return None

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        kind = self.__class__._serde_kind()
        if kind is not None:
            out["kind"] = kind

        ordered_names = self.SERDE.field_order or tuple(f.name for f in fields(cast(Any, self)))
        field_by_name = {f.name: f for f in fields(cast(Any, self))}
        for field_name in ordered_names:
            f = field_by_name[field_name]
            spec = self._serde_field_spec(field_name)
            v = getattr(self, f.name)
            if callable(spec.omit_when) and spec.omit_when(v, self):
                continue
            if spec.omit_if_default:
                default = _field_default_value(f)
                if default is not MISSING and v == default:
                    continue
            json_key = spec.json_key or f.name
            if callable(spec.encoder):
                out[json_key] = spec.encoder(v)
            else:
                out[json_key] = _encode_json_value(v)
        return out

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        kind = cls._serde_kind()
        if kind is not None:
            cls._serde_expect_kind(d, kind)

        type_hints = _type_hints_for_cls(cls)
        kwargs: dict[str, Any] = {}
        for f in fields(cast(Any, cls)):
            spec = cls._serde_field_spec(f.name)
            json_key = spec.json_key or f.name
            if json_key in d:
                raw = d[json_key]
            else:
                if callable(spec.missing_from):
                    raw = spec.missing_from(d)
                elif f.default is not MISSING or f.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                    continue
                else:
                    raise KeyError(json_key)

            if callable(spec.decoder):
                kwargs[f.name] = spec.decoder(raw)
            else:
                kwargs[f.name] = _decode_json_value(raw, type_hints.get(f.name, f.type), cls)
        return cls(**kwargs)  # type: ignore[call-arg]

    @staticmethod
    def _serde_expect_kind(d: dict[str, Any], kind: str) -> None:
        if d.get("kind") != kind:
            raise ValueError(f"expected kind {kind!r}, got {d.get('kind')!r}")
