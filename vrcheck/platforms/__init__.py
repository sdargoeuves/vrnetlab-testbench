from .aoscx import Aoscx
from .asav import Asav
from .base import Marker, Platform
from .exos import Exos
from .voss import Voss
from .vsrx import Vsrx

# Add new platforms here.
PLATFORMS: list[Platform] = [Aoscx(), Asav(), Exos(), Voss(), Vsrx()]


def platform_for(image: str) -> Platform | None:
    return next((p for p in PLATFORMS if p.image in image), None)


__all__ = ["Marker", "Platform", "PLATFORMS", "platform_for"]
