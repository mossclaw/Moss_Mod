import os
from copy import copy

import pygame
import ujson
import time

from scripts.game_structure.game_essentials import game


class Sprites:

    class SpriteSheet:
        def __init__(self, a_file):
            self.image = None
            self.a_file = a_file
    
        @property
        def sprite(self):
            if not self.image:
                self.image = pygame.image.load(self.a_file).convert_alpha()
            return self.image


    class SpriteCache:
        def __init__(self, spritesheet, x, y, size):
            self.image = None
            self.spritesheet = spritesheet
            self.x = x
            self.y = y
            self.size = size

        @property
        def sprite(self):
            if not self.image:
                self.image = pygame.Surface.subsurface(
                    self.spritesheet.sprite,
                    self.x, self.y,
                    self.size, self.size
                )
            return self.image


    class Blank:
        def __init__(self, size):
            self.sprite = pygame.Surface(
                (size, size),
                pygame.HWSURFACE | pygame.SRCALPHA
            )


    cat_tints = {}
    white_patches_tints = {}
    clan_symbols = []
    real_pelts = {}

    def __init__(self):
        """Class that handles and hold all spritesheets. 
        Size is normally automatically determined by the size
        of the lineart. If a size is passed, it will override 
        this value. """
        self.symbol_dict = None
        self.size = None
        self.spritesheets = {}
        self.images = {}
        self.sprite_cache = {}
        self.sprites = self

        # Shared empty sprite for placeholders
        self.blank_sprite = None

        self.load_tints()


    def __getitem__(self, name):
        return self.sprite_cache[name].sprite


    def get(self, name):
        return self.sprite_cache[name].sprite


    def load_tints(self):
        self.cat_tints = self.read_dict('tint', 'Tints')
        self.white_patches_tints = self.read_dict('white_patches_tint', 'White Patches Tints')
        self.real_pelts = self.read_dict('real_pelts', 'Real Pelts')


    def read_dict(self, name, description):
        try:
            with open(f'sprites/dicts/{name}.json', 'r') as read_file:
                return ujson.loads(read_file.read())
        except IOError:
            print(f'ERROR: Reading {description}')
            return {}


    def spritesheet(self, a_file, name):
        """
        Add spritesheet called name from a_file.

        Parameters:
        a_file -- Path to the file to create a spritesheet from.
        name -- Name to call the new spritesheet.
        """
        self.spritesheets[name] = self.SpriteSheet(a_file)


    def make_single(self,
                    spritesheet,
                    name,
                    pos=(0, 0),
                    static=False):
        """
        Extract a single sprite from a spritesheet.
        :param spritesheet: Name of spritesheet file
        :param pos: (x,y) tuple of offsets. NOT pixel offset, but offset of other sprites
        :param name: Name of sprite being made
        """

        x = pos[0] * self.size
        y = pos[1] * self.size

        # extracting on-demand sprite and storing in self.sprite_cache
        try:
            new_sprite = self.SpriteCache(
                self.spritesheets[spritesheet],
                x, y, self.size
            )

        except ValueError:
            # Fallback for non-existent sprites
            print(f"WARNING: nonexistent sprite - {name}")
            if not self.blank_sprite:
                self.blank_sprite = self.Blank(self.size)
            new_sprite = self.blank_sprite

        if static:
            for i in range(self.sprites_x * self.sprites_y):
                self.sprite_cache[f'{name}{i}'] = new_sprite
        else:
            self.sprite_cache[name] = new_sprite


    def make_group(self, name):
        """
        Divide sprites on a spritesheet into groups of sprites that are easily accessible
        :param name: Name of spritesheet being made into a group of same name
        """

        # splitting group into separate sprites
        i = 0
        for y in range(self.sprites_y):
            for x in range(self.sprites_x):
                self.make_single(name, f"{name}{i}", (x, y))
                i += 1


    def load_file(self, path, name, subdir=None):
        spritesheet = f'{subdir}{name.upper()}' if subdir else name
        self.spritesheet(f'sprites/{path}', spritesheet)
        
        if path in self.config:
            kind = self.config[path]
        elif subdir and subdir in self.config:
            kind = self.config[subdir]
        else:
            kind = 'normal'
        
        match kind:
            case 'normal':
                self.make_group(spritesheet)
                
            case 'none':
                pass
                
            case 'single':
                self.make_single(spritesheet, spritesheet)
                
            case 'static':
                self.make_single(spritesheet, spritesheet, static=True)
                
            case _:
                # kind should be a path to a json file
                if os.path.isfile(kind):
                    # TODO: for now use old logic
                    pass
                else:
                    print(f"WARNING: Entry in sprites.json for {path} is not valid. Ignoring file.")
                    print( "         Valid values are normal, none, single, static "
                                    "or a path to a json file.")


    def load_dir(self, path, subdir=None):
        for file_name in os.listdir(path):
            sub_path = f'{path}/{file_name}'
            if os.path.isfile(sub_path) and file_name[-4:] == '.png':
                rel_path = f'{subdir}/{file_name}' if subdir else file_name
                self.load_file(rel_path, file_name[:-4], subdir)
            elif os.path.isdir(sub_path) and not subdir:
                self.load_dir(sub_path, file_name)
            

    def load_all(self):
        # read sprites.json
        self.config = self.read_dict('sprites', 'Sprite Configuration')

        # get the width and height of the spritesheet
        self.spritesheet(f'sprites/line.png', 'line')
        width, height = self.spritesheets['line'].sprite.get_size()
        
        sheet_size = self.config['_sheet_size_']
        self.sprites_x = sheet_size[0]
        self.sprites_y = sheet_size[1]
        
        # check consistency of sheet size and determine sprite size
        if isinstance(self.size, int):
            pass
        elif width / self.sprites_x == height / self.sprites_y:
            self.size = width / self.sprites_x
        else:
            self.size = 400  # default, what base clangen uses
            print(f"The sprite grid size is set to {self.sprites_x}x{self.sprites_y}, "
                  f"which does not match the size of line.png.")
            print(f"Falling back to sprite size {self.size}.")
            print(f"When modifying the sprite grid size, the size set in "
                  f"sprites/dicts/sprites.json must match the size of line.png.")

        del width, height  # unneeded
        
        # Process contents of sprites folder
        self.load_dir('sprites')
        self.load_symbols()


    def load_symbols(self):
        """
        loads clan symbols
        """

        if os.path.exists("resources/dicts/clan_symbols.json"):
            with open(
                "resources/dicts/clan_symbols.json", encoding="utf-8"
            ) as read_file:
                self.symbol_dict = ujson.loads(read_file.read())

        # U and X omitted from letter list due to having no prefixes
        letters = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
            "T",
            "V",
            "W",
            "Y",
            "Z",
        ]

        # sprite names will format as "symbol{PREFIX}{INDEX}", ex. "symbolSPRING0"
        y_pos = 1
        for letter in letters:
            x_mod = 0
            for i, symbol in enumerate(
                [
                    symbol
                    for symbol in self.symbol_dict
                    if letter in symbol and self.symbol_dict[symbol]["variants"]
                ]
            ):
                if self.symbol_dict[symbol]["variants"] > 1 and x_mod > 0:
                    x_mod += -1
                for variant_index in range(self.symbol_dict[symbol]["variants"]):
                    x_pos = i + x_mod

                    if self.symbol_dict[symbol]["variants"] > 1:
                        x_mod += 1
                    elif x_mod > 0:
                        x_pos += -1

                    self.clan_symbols.append(f"symbol{symbol.upper()}{variant_index}")
                    self.make_single(
                        "symbol",
                        f"symbol{symbol.upper()}{variant_index}",
                        (x_pos, y_pos)
                    )

            y_pos += 1


    def get_symbol(self, symbol: str, force_light=False):
        """Change the color of the symbol to match the requested theme, then return it
        :param Surface symbol: The clan symbol to convert
        :param force_light: Use to ignore dark mode and always display the light mode color
        """
        symbol = self.sprites.get(symbol)
        if symbol is None:
            logger.warning("%s is not a known Clan symbol! Using default.")
            symbol = self.sprites[self.clan_symbols[0]]

        recolored_symbol = copy(symbol)
        var = pygame.PixelArray(recolored_symbol)
        var.replace(
            (87, 76, 45),
            pygame.Color(game.config["theme"]["dark_mode_clan_symbols"])
            if not force_light and game.settings["dark mode"]
            else pygame.Color(game.config["theme"]["light_mode_clan_symbols"]),
            distance=0,
        )
        del var

        return recolored_symbol

# CREATE INSTANCE
sprites = Sprites()
