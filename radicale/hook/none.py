from radicale import hook


class Hook(hook.BaseHook):
    @property
    def enabled(self) -> bool:
        """Check if this hook is enabled."""
        return False

    def notify(self, notification_item):
        """Notify nothing. Empty hook."""
