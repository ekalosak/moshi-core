class SysAuthError(Exception):
    """Raised when some server-side authentication fails."""

    ...

class ParseError(Exception):
    """Raised when parsing fails."""

    ...

class UserAuthenticationError(Exception):
    """Raised when user authentication fails."""

    ...

class UserDNEError(Exception):
    """Raised when a user does not exist."""

    ...

class UserResetError(Exception):
    """Raised when something unexpected happens and the user should reload the page."""

    ...

