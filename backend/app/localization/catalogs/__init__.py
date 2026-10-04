"""Localization catalogs package initialization."""

from backend.app.localization.catalogs.en import CATALOG_EN
from backend.app.localization.catalogs.hi import CATALOG_HI
from backend.app.localization.catalogs.mr import CATALOG_MR

ALL_CATALOGS = {
    "en": CATALOG_EN,
    "hi": CATALOG_HI,
    "mr": CATALOG_MR,
}

__all__ = ["ALL_CATALOGS", "CATALOG_EN", "CATALOG_HI", "CATALOG_MR"]
