"""
API provider registry for managing LLM provider implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from pi_ai.event_stream import AssistantMessageEventStream
from pi_ai.types import (
    Api,
    Context,
    Model,
    SimpleStreamOptions,
    StreamOptions,
)


class StreamFunction(Protocol):
    """Protocol for stream functions."""

    def __call__(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        ...


class StreamSimpleFunction(Protocol):
    """Protocol for simple stream functions."""

    def __call__(
        self,
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        ...


@dataclass
class ApiProvider:
    """API provider with stream functions."""

    api: Api
    stream: StreamFunction
    stream_simple: StreamSimpleFunction


@dataclass
class _RegisteredApiProvider:
    """Internal registered provider with optional source ID."""

    provider: ApiProvider
    source_id: str | None = None


_api_provider_registry: dict[str, _RegisteredApiProvider] = {}


def _wrap_stream(api: Api, stream_fn: StreamFunction) -> StreamFunction:
    """Wrap stream function with API validation."""

    def wrapped(
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        if model.api != api:
            raise ValueError(f"Mismatched api: {model.api} expected {api}")
        return stream_fn(model, context, options)

    return wrapped


def _wrap_stream_simple(api: Api, stream_fn: StreamSimpleFunction) -> StreamSimpleFunction:
    """Wrap simple stream function with API validation."""

    def wrapped(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        if model.api != api:
            raise ValueError(f"Mismatched api: {model.api} expected {api}")
        return stream_fn(model, context, options)

    return wrapped


def register_api_provider(
    provider: ApiProvider,
    source_id: str | None = None,
) -> None:
    """Register an API provider."""
    wrapped_provider = ApiProvider(
        api=provider.api,
        stream=_wrap_stream(provider.api, provider.stream),
        stream_simple=_wrap_stream_simple(provider.api, provider.stream_simple),
    )
    _api_provider_registry[provider.api] = _RegisteredApiProvider(
        provider=wrapped_provider,
        source_id=source_id,
    )


def get_api_provider(api: Api) -> ApiProvider | None:
    """Get an API provider by API type."""
    entry = _api_provider_registry.get(api)
    return entry.provider if entry else None


def get_api_providers() -> list[ApiProvider]:
    """Get all registered API providers."""
    return [entry.provider for entry in _api_provider_registry.values()]


def unregister_api_providers(source_id: str) -> None:
    """Unregister all API providers with a given source ID."""
    to_remove = [
        api for api, entry in _api_provider_registry.items() if entry.source_id == source_id
    ]
    for api in to_remove:
        del _api_provider_registry[api]


def clear_api_providers() -> None:
    """Clear all registered API providers."""
    _api_provider_registry.clear()
