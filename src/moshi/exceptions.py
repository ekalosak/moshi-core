class UserAuthenticationError(Exception):
    """Raised when user authentication fails."""

    ...


class SysAuthError(Exception):
    """Raised when some server-side authentication fails."""

    ...


class UserResetError(Exception):
    """Raised when something unexpected happens and the user should reload the page."""

    ...
