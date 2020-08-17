from radicale import hook


class Hook(hook.BaseHook):
    def notify(self, content):
        """Notify nothing. Empty hook."""
