"""Access control: free / paid / whitelist."""

from app.services.database import has_premium_access


def can_export(user_id: int) -> bool:
    """Export (Excel + save chart) requires premium or whitelist."""
    return has_premium_access(user_id)


def can_view_chart(user_id: int) -> bool:
    """Everyone can view the progress chart in the bot."""
    return True
