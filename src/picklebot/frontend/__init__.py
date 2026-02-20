"""Frontend abstraction for pickle-bot."""

from picklebot.frontend.base import Frontend, SilentFrontend
from picklebot.frontend.console import ConsoleFrontend
from picklebot.frontend.messagebus_frontend import MessageBusFrontend

__all__ = ["Frontend", "SilentFrontend", "ConsoleFrontend", "MessageBusFrontend"]
