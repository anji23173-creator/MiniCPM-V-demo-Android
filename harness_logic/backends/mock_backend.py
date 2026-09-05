from __future__ import annotations

from ..backend import HarnessBackend


class MockBackend(HarnessBackend):
    """Runnable stand-in backend for tests and no-model demos."""


class LlamaBackendAdapter(MockBackend):
    """Compatibility name matching the Android adapter layer."""
