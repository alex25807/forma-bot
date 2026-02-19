"""Access control: free / standard / premium."""

from app.services.database import (
    a_has_premium_access as has_premium_access,
    a_has_standard_access as has_standard_access,
    a_get_user_plan as get_user_plan,
)


async def can_recipe(user_id: int) -> bool:
    """Recipes require standard+ or whitelist."""
    return await has_standard_access(user_id)


async def can_export(user_id: int) -> bool:
    """Export (Excel + save chart) requires premium or whitelist."""
    return await has_standard_access(user_id)


async def can_download_menu(user_id: int) -> bool:
    """Download menu as file requires standard+."""
    return await has_standard_access(user_id)


def can_view_chart(user_id: int) -> bool:
    """Everyone can view the progress chart in the bot."""
    return True
