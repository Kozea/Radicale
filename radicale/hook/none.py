from radicale import hook


class Hook(hook.BaseHook):
    def notify(self, notification_item):
        """Notify nothing. Empty hook."""
