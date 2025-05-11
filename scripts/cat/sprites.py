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
        try:
            with open("sprites/dicts/tint.json", 'r') as read_file:
                self.cat_tints = ujson.loads(read_file.read())
        except IOError:
            print("ERROR: Reading Tints")

        try:
            with open("sprites/dicts/white_patches_tint.json", 'r') as read_file:
                self.white_patches_tints = ujson.loads(read_file.read())
        except IOError:
            print("ERROR: Reading White Patches Tints")

        try:
            with open("sprites/dicts/real_pelts.json", 'r') as read_file:
                self.real_pelts = ujson.loads(read_file.read())
        except IOError:
            print("ERROR: Reading Real Pelts")

    def spritesheet(self, a_file, name):
        """
        Add spritesheet called name from a_file.

        Parameters:
        a_file -- Path to the file to create a spritesheet from.
        name -- Name to call the new spritesheet.
        """
        self.spritesheets[name] = self.SpriteSheet(a_file)

    def make_group(self,
                   spritesheet,
                   pos,
                   name,

                   sprites_x=8,
                   sprites_y=8,
                   no_index=False):  # pos = ex. (2, 3), no single pixels
        """
        Divide sprites on a spritesheet into groups of sprites that are easily accessible
        :param spritesheet: Name of spritesheet file
        :param pos: (x,y) tuple of offsets. NOT pixel offset, but offset of other sprites
        :param name: Name of group being made
        :param sprites_x: default 3, number of sprites horizontally
        :param sprites_y: default 3, number of sprites vertically
        :param no_index: default False, set True if sprite name does not require cat pose index
        """

        group_x_ofs = pos[0] * sprites_x * self.size
        group_y_ofs = pos[1] * sprites_y * self.size
        i = 0


        # splitting group into on-demand singular sprites and storing in self.sprite_cache
        for y in range(sprites_y):
            for x in range(sprites_x):
                if no_index:
                    full_name = f"{name}"
                else:
                    full_name = f"{name}{i}"

                try:
                    new_sprite = self.SpriteCache(
                        self.spritesheets[spritesheet],
                        group_x_ofs + x * self.size,
                        group_y_ofs + y * self.size,
                        self.size
                    )

                except ValueError:
                    # Fallback for non-existent sprites
                    print(f"WARNING: nonexistent sprite - {full_name}")
                    if not self.blank_sprite:
                        self.blank_sprite = self.Blank(self.size)
                    new_sprite = self.blank_sprite

                self.sprite_cache[full_name] = new_sprite
                i += 1

    def make_group_split(self,
                         subdir,
                         name,
                         part):
        spritesheet = f'{name}{part}'
        self.spritesheet(f"sprites/{subdir}/{part}.png".lower(), spritesheet)
        self.make_group(spritesheet, (0, 0), spritesheet)

    def load_all(self):
        # get the width and height of the spritesheet
        lineart = pygame.image.load('sprites/lineart.png')
        width, height = lineart.get_size()
        del lineart  # unneeded

        # if anyone changes lineart for whatever reason update this
        if isinstance(self.size, int):
            pass
        elif width / 8 == height / 8:
            self.size = width / 8
        else:
            self.size = 400  # default, what base clangen uses
            print(f"lineart.png is not 3x7, falling back to {self.size}")
            print(f"if you are a modder, please update scripts/cat/sprites.py and "
                  f"do a search for 'if width / 3 == height / 7:'")

        del width, height  # unneeded

        for x in [
            'line', 'lineartdf', 'lineartdead', 'symbols',
            'fademask',
            'base', 
            'eyebase', 'eyemid', 'eyetop', 'eyeshade', 'eyelight'

        ]:
            if 'lineart' in x and game.config['fun']['april_fools']:
                self.spritesheet(f"sprites/{x}.png", x)
            else:
                self.spritesheet(f"sprites/{x}.png", x)

        # Line art
        self.make_group('lineartdead', (0, 0), 'lineartdead')
        self.make_group('lineartdf', (0, 0), 'lineartdf')

        # Fading Fog
        for i in range(0, 3):
            self.make_group('fademask', (i, 0), f'fademask{i}')


        self.make_group('eyebase', (0, 0), 'eyebase')
        self.make_group('eyemid', (0, 0), 'eyemid')
        self.make_group('eyetop', (0, 0), 'eyetop')
        self.make_group('eyeshade', (0, 0), 'eyeshade')
        self.make_group('eyelight', (0, 0), 'eyelight')

        eye_patterns = [
            ['TRUE', 'CENTRAL', 'QUARTER', 'SLIVER', 'SPECKLES', 'FROSTED'],
            ['RING', 'HALFCENTRAL', 'HALFRING', 'BUBBLE', 'OUTRING', 'SWAP'],
            ['SWITCH', 'TRANSFORM']
        ]

        for row, patterns in enumerate(eye_patterns):
            for col, pattern in enumerate(patterns):
                self.make_group_split('eyes2', 'eyes2', pattern)

        # Define white patches
        white_patches = [
            ['FULLWHITE', 'ANY', 'TUXEDO', 'LITTLE', 'COLOURPOINT', 'VAN', 'ANYTWO', 'MOON'],
            ['PHANTOM', 'POWDER', 'BLEACHED', 'SAVANNAH', 'FADESPOTS', 'PEBBLESHINE', 'EXTRA', 'ONEEAR'],
            ['BROKEN', 'LIGHTTUXEDO', 'BUZZARDFANG', 'RAGDOLL', 'LIGHTSONG', 'VITILIGO', 'BLACKSTAR', 'PIEBALD'],
            ['CURVED', 'PETAL', 'SHIBAINU', 'OWL', 'TIP', 'FANCY', 'FRECKLES', 'RINGTAIL'],
            ['HALFFACE', 'PANTSTWO', 'GOATEE', 'VITILIGOTWO', 'PAWS', 'MITAINE', 'BROKENBLAZE', 'SCOURGE'],
            ['DIVA', 'BEARD', 'TAIL', 'BLAZE', 'PRINCE', 'BIB', 'VEE', 'UNDERS']

        ]

        white_patches2 = [
            ['HONEY', 'FAROFA', 'DAMIEN', 'MISTER', 'BELLY', 'TAILTIP', 'TOES', 'TOPCOVER'],
            ['APRON', 'CAPSADDLE', 'MASKMANTLE', 'SQUEAKS', 'STAR', 'TOESTAIL', 'RAVENPAW', 'PANTS'],
            ['REVERSEPANTS', 'SKUNK', 'KARPATI', 'HALFWHITE', 'APPALOOSA', 'DAPPLEPAW', 'HEART', 'LILTWO'],
            ['GLASS', 'MOORISH', 'SEPIAPOINT', 'MINKPOINT', 'SEALPOINT', 'MAO', 'LUNA', 'CHESTSPECK'],
            ['WINGS', 'PAINTED', 'HEARTTWO', 'WOODPECKER', 'BOOTS', 'MISS', 'COW', 'COWTWO'],
            ['BUB', 'BOWTIE', 'MUSTACHE', 'REVERSEHEART', 'SPARROW', 'VEST', 'LOVEBUG', 'TRIXIE']
        ]

        white_patches3 = [
            ['SAMMY', 'SPARKLE', 'RIGHTEAR', 'LEFTEAR', 'ESTRELLA', 'SHOOTINGSTAR', 'EYESPOT', 'REVERSEEYE'],
            ['FADEBELLY', 'FRONT', 'BLOSSOMSTEP', 'PEBBLE', 'TAILTWO', 'BUDDY', 'BACKSPOT', 'EYEBAGS'],
            ['BULLSEYE', 'FINN', 'DIGIT', 'KROPKA', 'FCTWO', 'FCONE', 'MIA', 'SCAR'],
            ['BUSTER', 'SMOKEY', 'HAWKBLAZE', 'CAKE', 'ROSINA', 'PRINCESS', 'LOCKET', 'BLAZEMASK'],
            ['TEARS', 'DOUGIE']
        ]

        white_patches_moss = [
            ['CHANCE', 'MOSSY', 'MOTH', 'NIGHTMIST', 'FALCON', 'VENUS', 'RETSUKO', 'TIDAL'],
            ['DIAMOND', 'ECLIPSE', 'SNOWSTORM', 'PEPPER', 'COWTHREE', 'COWFOUR', 'COWFIVE', 'COWSIX'],
            ['COWSEVEN', 'COWEIGHT', 'COWNINE', 'COWTEN', 'COWELEVEN', 'FRECKLEMASK', 'SPLAT', 'BATWING'],
            ['SMALLPATCHES']
        ]

        for row, patches in enumerate(white_patches):
            for col, patch in enumerate(patches):
                self.make_group_split('whitepatches', 'white', patch)
        for row, patches in enumerate(white_patches2):
            for col, patch in enumerate(patches):
                self.make_group_split('whitepatches2', 'white', patch)
        for row, patches in enumerate(white_patches3):
            for col, patch in enumerate(patches):
                self.make_group_split('whitepatches3', 'white', patch)
        for row, patches in enumerate(white_patches_moss):
            for col, patch in enumerate(patches):
                self.make_group_split('whitepatchesmoss', 'white', patch)

        # base pelt - to be expanded with extras later
        self.make_group('base', (0, 0), 'baseSOLID')
        self.make_group('line', (0, 0), 'line')

        # Middle color layer
        mids = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN', 'BRINDLE', 'CLASSIC'],
            ['FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE', 'SMOKE', 'FOG', 'MIST', 'SPLOTCH'],
            ['SABER', 'SMUDGE', 'ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]

        for row, mid in enumerate(mids):
            for col, md in enumerate(mid):
                self.make_group_split('mid', 'mid', md)

        # Highlight color layer
        highlights = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN', 'BRINDLE', 'CLASSIC'],
            ['FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE', 'SMOKE', 'FOG', 'MIST', 'SPLOTCH'],
            ['SABER', 'SMUDGE', 'ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]

        for row, highlight in enumerate(highlights):
            for col, hl in enumerate(highlight):
                self.make_group_split('highlight', 'highlight', hl)

        # Dark color layer
        darks = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN', 'BRINDLE', 'CLASSIC'],
            ['FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE', 'SMOKE', 'FOG', 'MIST', 'SPLOTCH'],
            ['SABER', 'SMUDGE', 'ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]

        for row, dark in enumerate(darks):
            for col, dr in enumerate(dark):
                self.make_group_split('dark', 'dark', dr)

        # Darker color layer
        shades = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN', 'BRINDLE', 'CLASSIC'],
            ['FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE', 'SMOKE', 'FOG', 'MIST', 'SPLOTCH'],
            ['SABER', 'SMUDGE', 'ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]

        for row, shade in enumerate(shades):
            for col, sh in enumerate(shade):
                self.make_group_split('shade', 'shade', sh)

        # Unders color layer
        unders = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN', 'BRINDLE', 'CLASSIC'],
            ['FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE', 'SMOKE', 'FOG', 'MIST', 'SPLOTCH'],
            ['SABER', 'SMUDGE', 'ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]

        for row, under in enumerate(unders):
            for col, ud in enumerate(under):
                self.make_group_split('unders', 'under', ud)

        # tortiepatchesmasks
        tortiepatchesmasks = [
            ['ONE', 'TWO', 'THREE', 'FOUR', 'REDTAIL', 'DELILAH', 'HALF', 'STREAK'],
            ['MASK', 'SMOKE', 'MINIMALONE', 'MINIMALTWO', 'MINIMALTHREE', 'MINIMALFOUR', 'OREO', 'SWOOP'],
            ['CHIMERA', 'CHEST', 'ARMTAIL', 'GRUMPYFACE', 'MOTTLED', 'SIDEMASK', 'EYEDOT', 'BANDANA'],
            ['PACMAN', 'STREAMSTRIKE', 'SMUDGED', 'DAUB', 'EMBER', 'BRIE', 'ORIOLE', 'ROBIN'],
            ['BRINDLE', 'PAIGE', 'ROSETAIL', 'SAFI', 'DAPPLENIGHT', 'BLANKET', 'BELOVED', 'BODY'],
            ['SHILOH', 'FRECKLED', 'HEARTBEAT']
        ]

        tortiepatchesmasksmoss = [
            ['VIPER', 'SKULL', 'POINTS', 'DITTO', 'TABBY', 'SPECKLED', 'BENGAL', 'CLASSIC'],
            ['MACKEREL', 'MARBLED', 'SABER', 'ROSETTE', 'MASKED', 'DUST', 'MAXIMUMONE', 'MAXIMUMTWO'],
            ['MAXIMUMTHREE', 'MAXIMUMFOUR', 'MAXIMUMFIVE', 'MAXIMUMSIX', 'MAXIMUMSEVEN', 'MAXIMUMEIGHT']
        ]

        for row, masks in enumerate(tortiepatchesmasks):
            for col, mask in enumerate(masks):
                self.make_group_split('tortiepatchesmasks', 'tortiemask', mask)

        for row, masks in enumerate(tortiepatchesmasksmoss):
            for col, mask in enumerate(masks):
                self.make_group_split('tortiesmoss', 'tortiemask', mask)

        # Define skin patterns
        skins = [
            ["SOLID", "TIP", "MARBLE", "FRECKLE"]
        ]

        for row, skins in enumerate(skins):
            for col, skin in enumerate(skins):
                self.make_group_split('skin', 'skin', skin)

        self.load_scars()
        self.load_symbols()

    def load_scars(self):
        """
        Loads scar sprites and puts them into groups.
        """

        # Define scars
        scars_data = [
            ["ONE", "TWO", "THREE", "FOUR", "BRIDGE", "RIGHTBLIND", "LEFTBLIND", "BOTHBLIND"],
            ["BEAKCHEEK", "BEAKLOWER", "BURNRUMP", "CATBITE", "RATBITE", "FROSTFACE", "FROSTMITT", "FROSTSOCK"],
            ["QUILLCHUNK", "QUILLSCRATCH", "SNOUT", "CHEEK", "SIDE", "THROAT", "TAILBASE", "BELLY"],
            ["TOETRAP", "SNAKE", "LEGBITE", "NECKBITE", "FACE", "HINDLEG", "BACK", "QUILLSIDE"],
            ["SCRATCHSIDE", "TOE", "BEAKSIDE", "CATBITETWO", "SNAKETWO", "MANLEG", "BURNPAWS", "BURNBELLY"]
        ]

        # define missing parts
        missing_parts_data = [
            ["LEFTEAR", "RIGHTEAR", "NOLEFTEAR", "NORIGHTEAR", "NOEAR", "NOPAW", "NOTAIL", "HALFTAIL"],
            ["MANTAIL", "TAILSCAR", "FROSTTAIL", "BURNTAIL", "BRIGHTHEART"]
        ]

        missing_parts_color_data = [
            ["LEFTEAR", "RIGHTEAR", "NOLEFTEAR", "NORIGHTEAR", "NOEAR", "NOPAW", "NOTAIL", "HALFTAIL"],
            ["MANTAIL", "TAILSCAR", "FROSTTAIL", "BURNTAIL", "BRIGHTHEART"]
        ]

        # scars 
        for row, scars in enumerate(scars_data):
            for col, scar in enumerate(scars):
                self.make_group_split('scars', 'scars', scar)

        # missing parts
        for row, missing_parts in enumerate(missing_parts_data):
            for col, missing_part in enumerate(missing_parts):
                self.make_group_split('missingscars', 'scars', missing_part)

        for row, missing_parts_color in enumerate(missing_parts_color_data):
            for col, missing_part_color in enumerate(missing_parts_color):
                self.make_group_split('missingscarscolor', 'scarscolor', missing_part_color)

        # accessories
        #to my beloved modders, im very sorry for reordering everything <333 -clay
        medherbs1_data = [
            ["MAPLE LEAF", "HOLLY", "BLUE BERRIES", "FORGET ME NOTS", "RYE STALK", "CATTAIL", "SUNGLASSES", "LUNA MOTH"],
            ["ATLAS MOTH", "BIRD SKULL", "LUCKY CLOVER", "BLUEBELLS", "LILY OF THE VALLEY", "SNAPDRAGON", "ANTLERS", "STICK"],
            ["FIREFLIES", "SPROUT", "MUSHROOM", "JUNIPER", "RASPBERRY", "LAVENDER", "OAK LEAVES", "LILAC"],
            ["MAPLE SEED", "SEAWEED", "LILY PAD", "MONSTERA", "WILD FLOWERS", "TWIGS", "CLOVER", "SERPENT"],
            ["MOSS BALL", "RAINBOW COLLAR", "RAINBOW HARNESS", "RAINBOW BANDANA"]
        ]

        # medcatherbs
        for row, herbs in enumerate(medherbs1_data):
            for col, herb in enumerate(herbs):
                self.make_group_split('medherbs', 'acc', herb)

        # please im begging you
        accbases_data = [
            ["COLLAR", "HARNESS", "BANDANA", "POPPY", "HERBS", "DAISY", "BULB", "PETALS"],
            ["FEATHER", "CICADA", "BUTTERFLY", "MOTH", "NETTLES", "HEATHER", "GORSE", "CATMINT"],
            ["LAUREL", "IVY", "BUTTERFLIES", "WREATH", "FLOWER WREATH", "SHELL", "CRYSTAL"]
        ]

        for row, accbases in enumerate(accbases_data):
            for col, accbase in enumerate(accbases):
                self.make_group_split('accbase', 'accbase', accbase)

        accadds_data = [
            ["COLLAR", "HARNESS", "BANDANA", "POPPY", "HERBS", "DAISY", "BULB", "PETALS"],
            ["FEATHER", "CICADA", "BUTTERFLY", "MOTH", "NETTLES", "HEATHER", "GORSE", "CATMINT"],
            ["LAUREL", "IVY", "BUTTERFLIES", "WREATH", "FLOWER WREATH", "SHELL", "CRYSTAL"]
        ]

        for row, accadds in enumerate(accadds_data):
            for col, accadd in enumerate(accadds):
                self.make_group_split('accadd', 'accadd', accadd)

        accpatterns1_data = [
            ["STRIPES", "NOTES", "STARS", "IVYS", "PAWPRINTS", "PLAID", "ZEBRA", "HEARTS"],
            ["FLORAL", "SQUIGGLE", "WAVES", "DIAMONDS", "BUTTERFLIESONE", "BUTTERFLIESTWO", "FLOWERPRINTONE", "FLOWERPRINTTWO"],

        ]
        accpatterns2_data = [
            ["CONVERSE", "FRUIT", "GEOMETRICONE", "CHECKERS", "PLAIDTWO", "WINTERSWEATER", "FLOWERPRINTTHREE", "FLOWERPRINTFOUR"]
        ]

        for row, accpatterns in enumerate(accpatterns1_data):
            for col, accpattern in enumerate(accpatterns):
                self.make_group_split('accpattern1', 'accpattern', accpattern)

        for row, accpatterns in enumerate(accpatterns2_data):
            for col, accpattern in enumerate(accpatterns):
                self.make_group_split('accpattern2', 'accpattern', accpattern)

        acccollars_data = [
            ["BELL", "BOW", "STUDDED", "FANG", "COWBOY HAT"]
        ]

        for row, acccollars in enumerate(acccollars_data):
            for col, acccollars in enumerate(acccollars):
                self.make_group_split('collaradd', 'acccollars', acccollars)

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
                    self.make_group(
                        "symbols",
                        (x_pos, y_pos),
                        f"symbol{symbol.upper()}{variant_index}",
                        sprites_x=1,
                        sprites_y=1,
                        no_index=True,
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
