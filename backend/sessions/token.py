# backend/sessions/token.py
#
# LiveKit access token generation.
# Kept isolated so the rest of the codebase doesn't import livekit directly.

from django.conf import settings
from livekit.api import AccessToken, VideoGrants


def generate_token(room_name: str, user_identity: str, user_display_name: str) -> str:
    """
    Return a signed LiveKit JWT for the given user and room.

    Args:
        room_name:         LiveKit room name the token grants access to.
        user_identity:     Unique stable identifier for the participant
                           (we use str(user.id)).
        user_display_name: Display name shown in the room (user.username).
    """
    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(user_identity)
        .with_name(user_display_name)
        .with_grants(VideoGrants(room_join=True, room=room_name))
    )
    return token.to_jwt()
