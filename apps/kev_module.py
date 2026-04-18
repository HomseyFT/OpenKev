"""Abstract base class that every OpenKev app module must implement.

The navigator (the outer window that shows each app as a tab) uses this
interface to:

* query which files a module currently has open (so it can avoid opening the
  same file in two places)
* ask the module to focus a specific file if the user tries to re-open it

Modules that don't deal with files (e.g. KevPilot, Kev Teams) still implement
the interface — they just return an empty list and make ``focus_file`` a no-op.

Implementation note: we combine ``abc.ABCMeta`` with Qt's shiboken metaclass
so subclasses that forget to implement the abstract methods fail loudly at
instantiation time rather than exploding mid-runtime.
"""

from abc import ABCMeta, abstractmethod

from PySide6.QtWidgets import QWidget


class _KevModuleMeta(type(QWidget), ABCMeta):  # type: ignore[misc]
    """Combined metaclass so QWidget and ABCMeta can coexist."""


class KevModule(QWidget, metaclass=_KevModuleMeta):
    """Base class for all OpenKev app modules."""

    #: Human-readable name shown in the navigator tab, e.g. ``"Wei Word"``.
    app_name: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        # Shiboken's metaclass swallows ABCMeta's ``__abstractmethods__`` set,
        # so we compute the missing implementations manually by walking MRO
        # and checking for any method still flagged ``__isabstractmethod__``.
        missing = sorted(
            name
            for name in dir(type(self))
            if getattr(getattr(type(self), name, None), "__isabstractmethod__", False)
        )
        if missing:
            raise TypeError(
                f"Cannot instantiate {type(self).__name__}: "
                f"missing abstract methods {missing}"
            )
        super().__init__(parent)

    @property
    @abstractmethod
    def open_files(self) -> list[str]:
        """Return absolute paths of every file currently open in this module.

        Untitled/unsaved documents MUST be excluded. The navigator uses this to
        prevent opening the same file twice across modules.
        """

    @abstractmethod
    def focus_file(self, filepath: str) -> None:
        """Bring the view associated with ``filepath`` into focus.

        Called by the navigator when the user tries to open a file that is
        already open in this module.
        """
