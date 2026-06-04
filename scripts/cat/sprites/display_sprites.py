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
    poses: list = sprites.POSE_DATA["poses"]

    if life_state is not None:
        age = life_state
    else:
        age = cat.age

    if always_living:
        dead = False
    else:
        dead = cat.dead

    # setting the cat_sprite (bc this makes things much easier)
    cat_sprite = str(0)
    if (
            not disable_sick_sprite
            and cat.not_working()
            and age != CatAge.NEWBORN
            and constants.CONFIG["cat_sprites"]["sick_sprites"]
    ):

        if cat.pelt.length == "long":
            if age in CatAge.KITTEN:
                cat_sprite = str(49)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(51)
            elif age in CatAge.SENIOR:
                cat_sprite = str(55)
            else:
                cat_sprite = str(53)
        else:
            if age in CatAge.KITTEN:
                cat_sprite = str(48)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(50)
            elif age in CatAge.SENIOR:
                cat_sprite = str(54)
            else:
                cat_sprite = str(52)

    elif cat.pelt.paralyzed and age != "newborn":
        if cat.pelt.length == "long":
            if age in CatAge.KITTEN:
                cat_sprite = str(41)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(43)
            elif age in CatAge.SENIOR:
                cat_sprite = str(47)
            else:
                cat_sprite = str(45)
        else:
            if age in CatAge.KITTEN:
                cat_sprite = str(40)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(42)
            elif age in CatAge.SENIOR:
                cat_sprite = str(46)
            else:
                cat_sprite = str(44)

    elif constants.CONFIG["fun"]["all_cats_are_newborn"]:
        cat_sprite = str(cat.pelt.cat_sprites["newborn"])
    else:
        cat_sprite = str(cat.pelt.cat_sprites[age])


    return cat.pelt.render(cat_sprite,
                           dead,
                           cat.status.group,
                           not cat.prevent_fading and get_clan_setting("fading"),
                           scars_hidden,
                           acc_hidden,
                           load_only,
                           cat.name)


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
