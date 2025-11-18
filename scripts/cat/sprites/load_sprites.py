import logging
import os
from copy import copy

import pygame
import ujson
import time

from scripts.cat.enums import CatGroup
from scripts.game_structure import constants, image_cache
from scripts.game_structure.game.settings import game_setting_get
from scripts.temp_util import read_sprite_dict, read_json, all_mods, base_mod


logger = logging.getLogger(__name__)


class Sprites:
    """ Class that handles and hold all spritesheets. """

    class SpriteSheet:
        def __init__(self, mod, path):
            self.image = None
            self.mod = mod
            self.path = path
            self.ready = False

        @property
        def sprite(self):
            if self.image is None:
                with self.mod.open_path(self.path, text=False) as file:
                    name = self.path.split('/')[-1]
                    self.image = pygame.image.load(file, namehint=name).convert_alpha()
            return self.image


    class SpriteCache:
        def __init__(self, spritesheet, x, y, size):
            self.image = None
            self.spritesheet = spritesheet
            self.x = x
            self.y = y
            self.size = size
            self.ready = False

        @property
        def sprite(self):
            if self.image is None:
                self.image = pygame.Surface.subsurface(
                    self.spritesheet.sprite,
                    self.x, self.y,
                    self.size[0], self.size[1]
                )
            return self.image


    class PaletteSpriteCache:
        def __init__(self, base_sprite, palette_set, palette_name):
            self.image = None
            self.base_sprite = base_sprite
            self.palette_set = palette_set
            self.palette_name = palette_name
            self.ready = False

        @property
        def sprite(self):
            if self.image is None:
                self.image = self.palette_set.apply(
                    self.base_sprite.sprite,
                    self.palette_name
                )
            return self.image


    class PaletteSet:
        def __init__(self, path, palette_names):
            self.palettes = None
            self.base_palette = None
            self.path = path
            self.palette_names = palette_names

        def apply(self, sprite, palette):
            if palette == 'BASE':
                return sprite

            if self.palettes is None:
                image = pygame.image.load(path)
                with pygame.PixelArray(image) as array:
                    n = array.shape[1]   # pylint: disable=unsubscriptable-object
                    rows = [
                        [ image.unmap_rbg(color) for color in array[::, i] ]
                        for i in range(0, n)
                    ]
                    self.base_palette = rows[0]
                    self.palettes = dict(zip(self.palette_names, rows[1::]))

            sprite = sprite.copy()
            with pygame.PixelArray(sprite) as array:
                for old_color, new_color in zip(self.palette_names, self.palettes[palette]):
                    array.replace(old_color, new_color)

            return sprite


    class Blank:
        def __init__(self, size):
            self.sprite = pygame.Surface(
                size,
                pygame.HWSURFACE | pygame.SRCALPHA
            )


    cat_tints           = {}
    white_patches_tints = {}
    clan_symbols        = []

    # TODO: There are used from pelts.py. Would be nice to decouple,
    #       but they *are* required to be in sync. Needs thinking.
    POSE_DATA = read_sprite_dict('pose_sprite_data')
    COLLAR_DATA = read_sprite_dict('collar_sprite_data')
    WILD_DATA = read_sprite_dict('wild_sprite_data')
    PLANT_DATA = read_sprite_dict('plant_sprite_data')
    SCAR_DATA = read_sprite_dict('scar_sprite_data')
    SCAR_MISSING_PART_DATA = read_sprite_dict('scar_missing_sprite_data')
    SKIN_DATA = read_sprite_dict('skin_sprite_data')
    TORTIE_DATA = read_sprite_dict('tortie_patches_sprite_data')
    PELT_DATA = read_sprite_dict('pelt_sprite_data')
    EYE_DATA = read_sprite_dict('eye_sprite_data')
    WHITE_DATA = read_sprite_dict('white_patches_sprite_data')


    def __init__(self):
        self.symbol_dict   = None
        self.symbol_colors = None
        self.size          = None
        self.spritesheets  = {}
        self.images        = {}
        self.sprite_cache  = {}
        self.sprites       = self

        # Shared empty sprite for placeholders
        self.blank_sprite  = None

        self.load_tints()


    def __getitem__(self, name):
        return self.sprite_cache[name].sprite


    def get(self, name):
        return self.sprite_cache[name].sprite


    def load_tints(self):
        self.cat_tints = read_sprite_dict('tint', 'Tints')
        self.white_patches_tints = read_sprite_dict('white_patches_tint', 'White Patches Tints')


    def spritesheet(self, mod, path, name):
        """
        Add spritesheet called name from a_file.

        :param mod:  The mod containing the image.
        :param path: Path to the image to create a spritesheet from.
        :param name: Name to call the new spritesheet.
        """
        self.spritesheets[name] = self.SpriteSheet(mod, path)


    def make_single(self,
                    spritesheet,
                    name,
                    pos=(0, 0),
                    static=False,
                    sheet_size=None,
                    size=None,
                    palettes=None):
        """
        Extract a single sprite from a spritesheet.
        :param spritesheet: Name of spritesheet file.
        :param pos:         (x, y) tuple of offsets. NOT pixel offset, but offset in sprites.
        :param name:        Name of sprite being made.
        :param sheet_size:  Number of sprites in the grid, as an (x, y) tuple, if different
                            from default.
        :param size:        Size of each individual sprite, as an (x, y) tuple, if different
                            from default.
        :param palettes:    List of palette names.
        """

        if size is None:
            size = (self.size, self.size)
        x = pos[0] * size[0]
        y = pos[1] * size[1]

        try:
            new_sprite = self.SpriteCache(
                self.spritesheets[spritesheet],
                x, y, size
            )

        except ValueError:
            # Fallback for non-existent sprites
            logger.warning(f"nonexistent sprite - {name}")
            if not self.blank_sprite:
                self.blank_sprite = self.Blank(size)
            new_sprite = self.blank_sprite

        if static:
            if sheet_size is None:
                sheet_size = (self.sheet_size[0], self.sheet_size[1])
            for i in range(sheet_size[0] * sheet_size[1]):
                self.add_sprite(f"{name}{i}", new_sprite)
        else:
            self.add_sprite(name, new_sprite)
            self.sprite_cache[name] = new_sprite


    def add_sprite(self, name, sprite):
        self.sprite_cache[name] = sprite


    def make_group(self, name, sheet_size=None, size=None, palettes=None):
        """
        Divide sprites on a spritesheet into groups of sprites that are easily accessible.
        :param name:      Name of spritesheet being made into a group of same name.
        :param sheet_size: Number of sprites in the grid, as an (x, y) tuple, if different
                          from default.
        :param size:      Size of each individual sprite, as an (x, y) tuple, if different
                          from default.
        :param palettes:  List of palette names.
        """

        if sheet_size is None:
            sheet_size = (self.sheet_size[0], self.sheet_size[1])

        # splitting group into separate sprites
        i = 0
        for y in range(self.sheet_size[1]):
            for x in range(self.sheet_size[0]):
                self.make_single(name, f"{name}{i}", (x, y), size=size)
                i += 1


    def load_file(self, mod, path, rel_path, name, subdir=None):
        def invalid(path, reason):
            logger.warning(f"Entry in sprites.json for {path} is not valid. Ignoring file. {reason}")

        spritesheet = f"{subdir}{name.upper()}" if subdir else name
        self.spritesheet(mod, path, spritesheet)

        if rel_path in mod.sprite_config:
            kind = mod.sprite_config[rel_path]
        elif subdir and subdir in mod.sprite_config:
            kind = mod.sprite_config[subdir]
        elif subdir and subdir in self.config:
            kind = self.config[subdir]
        else:
            kind = 'normal'
        arg = []
        if isinstance(kind, list):
            arg = kind[1:]
            kind = kind[0]

        match kind:
            case 'normal':
                self.make_group(spritesheet)

            case 'none':
                pass

            case 'single':
                self.make_single(spritesheet, spritesheet)

            case 'static':
                self.make_single(spritesheet, spritesheet, static=True)

            case 'json':
                # arg should be a path to a json file
                if len(arg) >= 1 and os.path.isfile(arg[0]):
                    specified = self.load_specified(spritesheet, arg[0])
                    if specified is not None:
                        self.specified[name] = specified
                else:
                    invalid(path, 'Value json requires a file as argument.')

            case _:
                invalid(path, 'Valid values are normal, none, single, static or json.')


    def load_dir(self, mod, path, subdir=None):
        for entry in mod.scan_dir(path):
            sub_path = entry.path
            is_dir = entry.is_dir()
            if not is_dir and entry.name[-4:] == '.png':
                rel_path = f"{subdir}/{entry.name}" if subdir else entry.name
                self.load_file(mod, entry.path, rel_path, entry.name[:-4], subdir)
            elif is_dir and not subdir:
                self.load_dir(mod, entry.path, entry.name)


    def load_all(self):
        # read sprites.json
        self.config = read_sprite_dict('sprites', 'Sprite Configuration')
        base_mod.sprite_config = self.config

        # get the width and height of the spritesheet
        self.spritesheet(base_mod, 'sprites/line.png', 'line')
        width, height = self.spritesheets['line'].sprite.get_size()

        self.sheet_size = tuple(self.config['_sheet_size_'])

        # check consistency of sheet size and determine sprite size
        if isinstance(self.size, int):
            pass
        elif width / self.sheet_size[0] == height / self.sheet_size[1]:
            self.size = width / self.sheet_size[0]
        else:
            self.size = 400  # default is 50, what base clangen uses
            print(f"The sprite grid size is set to {self.sheet_size[0]}x{self.sheet_size[1]}, "
                  f"which does not match the size of line.png.")
            print(f"Falling back to sprite size {self.size}.")
            print(f"When modifying the sprite grid size, the size set in "
                  f"sprites/dicts/sprites.json must match the size of line.png.")

        del width, height
        self.specified = {}

        # Process contents of sprites folder and mods
        for mod in all_mods:
            if not hasattr(mod, 'sprite_config'):
                mod.sprite_config = mod.load('sprites/dicts/sprites.json')
            self.load_dir(mod, 'sprites')

        # Save special sprite sets in individual variables, for convenience and compatibility.
        self.symbol_dict, self.clan_symbols = self.specified['symbols']


    def load_specified(self, spritesheet, json_path):
        """
        Extracts sprites from a spritesheet according to a specification in a json file.
        """

        def get_or_default(entry, name, default):
            if entry is not None and name in entry:
                return entry[name]
            else:
                return default


        entries = read_json(json_path)
        config = entries['_config_']
        prefix = get_or_default(config, 'prefix', '')
        kind = config['type']
        del(entries['_config_'])

        match kind:
            case 'list':
                return self.load_specified_list(spritesheet, prefix, entries)
            case 'palette':
                return self.load_specified_palette(spritesheet, prefix, entries)


    def load_specified_list(self, spritesheet, prefix, entries):

        def read_or_set(entry, name, value):
            if name not in entry:
                entry[name] = value
                read = False
            else:
                value = entry[name]
                read = True
            return (value, read)


        xpos = 0
        ypos = 0
        sprite_names = []

        for name, entry in entries.items():
            variants, _ = read_or_set(entry, 'variants', 1)
            ypos, read  = read_or_set(entry, 'ypos',     ypos)
            xpos, _     = read_or_set(entry, 'xpos',     0 if read else xpos)

            names = []
            for i in range(variants):
                sprite_name = f"{prefix}{name}{i}"
                self.make_single(spritesheet, sprite_name, (xpos, ypos))
                if 'exclude' not in entry or not entry['exclude']:
                    names.append(sprite_name)
                    sprite_names.append(sprite_name)
                xpos += 1
            entry['sprite_names'] = names

        return (entries, sprite_names)


    def load_specified_palette(self, spritesheet, prefix, entries):
        # TODO
        return None


    def get_symbol(self, symbol: str, force_light=False):
        """
        Change the color of the symbol to match the requested theme, then return it
        :param symbol: The clan symbol to convert
        :param force_light: Use to ignore dark mode and always display the light mode color
        """
        dark = not force_light and game_setting_get('dark mode')
        color_key = ('light' if dark else 'light') + '_mode_clan_symbols'
        color = constants.CONFIG['theme'][color_key]
        if color != self.symbol_colors:
            self.symbol_colors = copy(color)
            self.clan_symbol_cache = {}

        if symbol not in self.clan_symbol_cache:
            if symbol in self.sprite_cache:
                sprite = self[symbol]
            else:
                logger.warning(f"{symbol} is not a known Clan symbol! Using default.")
                sprite = self.sprites[self.clan_symbols[0]]

            recolored = copy(sprite)
            var = pygame.PixelArray(recolored)
            var.replace((87, 76, 45), pygame.Color(color), distance=0)
            del var

            self.clan_symbol_cache[symbol] = recolored

        return self.clan_symbol_cache[symbol]


    # TODO
    @staticmethod
    def get_platform(biome, season, show_nest, group: CatGroup) -> pygame.Surface:
        """
        Returns the relevant platform
        :param biome: The current game biome
        :param season: The current game season
        :param show_nest: If true, displays the nest
        :param group: Used to determine appropriate afterlife platform
        :return: pygame.Surface containing the desired platform
        """
        offset = 0 if game_setting_get("dark mode") else 80
        """Used to choose the dark mode version of platforms"""

        available_biome = ["Forest", "Mountainous", "Plains", "Beach"]

        if biome not in available_biome:
            biome = available_biome[0]
        if show_nest:
            biome = "nest"

        biome = biome.lower()

        platformsheet = image_cache.load_image(
            "resources/images/platforms.png"
        ).convert_alpha()

        order = ["beach", "forest", "mountainous", "nest", "plains", "dead"]

        if group and group.is_afterlife():
            biome_platforms = platformsheet.subsurface(
                pygame.Rect(0, order.index("dead") * 70, 640, 70)
            )

            if group == CatGroup.DARK_FOREST:
                return biome_platforms.subsurface(pygame.Rect(0 + offset, 0, 80, 70))
            elif group == CatGroup.STARCLAN:
                return biome_platforms.subsurface(pygame.Rect(160 + offset, 0, 80, 70))
            elif group == CatGroup.UNKNOWN_RESIDENCE:
                return biome_platforms.subsurface(pygame.Rect(320 + offset, 0, 80, 70))

        biome_platforms = platformsheet.subsurface(
            pygame.Rect(0, order.index(biome) * 70, 640, 70)
        ).convert_alpha()
        season_x = {
            "greenleaf": 0 + offset,
            "leaf-bare": 160 + offset,
            "leaf-fall": 320 + offset,
            "newleaf": 480 + offset,
        }

        return biome_platforms.subsurface(
            pygame.Rect(
                season_x[season.lower()],
                0,
                80,
                70,
            )
        )


# CREATE INSTANCE
sprites = Sprites()

