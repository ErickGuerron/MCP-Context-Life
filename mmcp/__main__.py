from __future__ import annotations

import sys
import types

from mmcp.presentation import __main__ as _impl

_module = sys.modules[__name__]


class _ProxyModule(types.ModuleType):
    def __getattr__(self, name):
        return getattr(_impl, name)

    def __setattr__(self, name, value):
        if name not in {"__dict__", "__class__", "__doc__", "__file__", "__loader__", "__package__", "__spec__"}:
            setattr(_impl, name, value)
        super().__setattr__(name, value)


_module.__dict__.update({k: v for k, v in vars(_impl).items() if not (k.startswith("__") and k.endswith("__"))})
_module.__class__ = _ProxyModule
