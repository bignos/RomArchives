# -*- coding: utf-8 -*-

# -[ Imports ]-

from utils import (
    helpers,
    scraper
)

# -[ Constants ]-

CONF = helpers.load_json('conf/application.json')

# -[ Private ]-

# -[ Public ]-


def get_platforms() -> list:
    """
    Get all platforms
    """
    return [p['name'] for p in CONF['platforms']]


def load_platform(platform: str) -> list:
    """
    Load a platform

    :param platform: Platform name
    """
    if platform not in [p['name'] for p in CONF['platforms']]:
        raise Exception(f"Platform {platform} not found")

    conf = [p for p in CONF['platforms'] if p['name'] == platform][0]
    roms = scraper.get_rom_list(
        url=conf['url'],
        platform=platform,
        ext=conf['ext']
    )
    return roms
