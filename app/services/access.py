"""Access control: free / paid / whitelist."""

from app.services.database import a_has_premium_access as has_premium_access


async def can_export(user_id: int) -> bool:
    """Export (Excel + save chart) requires premium or whitelist."""
    return await has_premium_access(user_id)


def can_view_chart(user_id: int) -> bool:
    """Everyone can view the progress chart in the bot."""
    return True
