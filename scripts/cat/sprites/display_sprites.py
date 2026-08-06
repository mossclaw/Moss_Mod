import logging
import traceback

import pygame

from scripts.cat.enums import CatAge, CatGroup
from scripts.cat.sprites.load_sprites import sprites
from scripts.clan_package.settings import get_clan_setting
from scripts.game_structure import constants, image_cache
from scripts.game_structure.game import game_setting_get
from scripts.ui.scale import ui_scale_dimensions
from scripts.cat.pelts import Pelt

logger = logging.getLogger(__name__)


def generate_sprite(
    cat,
    life_state=None,
    scars_hidden=False,
    acc_hidden=False,
    always_living=False,
    disable_sick_sprite=False,
    load_only=False,
) -> pygame.Surface:
    """
    Generates the sprite for a cat, with optional arguments that will override certain things.

    :param life_state: sets the age life_stage of the cat, overriding the one set by its age. Set to string.
    :param scars_hidden: If True, doesn't display the cat's scars. If False, display cat scars.
    :param acc_hidden: If True, hide the accessory. If false, show the accessory.
    :param always_living: If True, always show the cat with living lineart
    :param disable_sick_sprite: If true, never use the not_working lineart.
                    If false, use the cat.not_working() to determine the no_working art.
    """
    age = life_state or cat.age.pose_age()
    newborn = age == CatAge.NEWBORN
    sick = (not newborn 
            and not disable_sick_sprite 
            and cat.not_working()
            and constants.CONFIG["cat_sprites"]["sick_sprites"])
    paralyzed = not newborn and cat.pelt.paralyzed
    
    return cat.pelt.render(get_cat_sprite(cat, age, sick, paralyzed),
                           cat.dead and not always_living,
                           cat.status.group,
                           not cat.prevent_fading and get_clan_setting("fading"),
                           scars_hidden,
                           acc_hidden,
                           load_only,
                           cat.name)


def get_cat_sprite(cat, age, sick, paralyzed):
    if sick or paralyzed:
        poses = Pelt._pelt_data['poses']['sick' if sick else 'paralyzed']
        return poses[age][cat.pelt.length]
    if constants.CONFIG["fun"]["all_cats_are_newborn"]:
        age = CatAge.NEWBORN
    return cat.pelt.cat_sprites[age]


def update_sprite(cat):
    # First, check if the cat is faded.
    if cat.faded:
        # Don't update the sprite if the cat is faded.
        return

    # apply
    cat.sprite = generate_sprite(cat)
    # update class dictionary
    cat.all_cats[cat.ID] = cat


def update_mask(cat):
    if cat.faded or cat.dead:
        # should never need a mask since they can't appear on the Clan screen
        cat.sprite_mask = None
        return

    val = pygame.mask.from_surface(
        pygame.transform.scale(cat.sprite, ui_scale_dimensions((50, 50))), threshold=250
    )

    inflated_mask = pygame.Mask(
        (
            val.get_size()[0] + 10,
            val.get_size()[1] + 10,
        )
    )
    inflated_mask.draw(val, (5, 5))
    for _ in range(3):
        outline = inflated_mask.outline()
        for point in outline:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    try:
                        inflated_mask.set_at((point[0] + dx, point[1] + dy), 1)
                    except IndexError:
                        continue
    cat.sprite_mask = inflated_mask
