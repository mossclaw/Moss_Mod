import os
from copy import copy

import pygame
import ujson

from scripts.game_structure.game_essentials import game


class Sprites:
    cat_tints = {}
    white_patches_tints = {}
    clan_symbols = []

    def __init__(self):
        """Class that handles and hold all spritesheets. 
        Size is normally automatically determined by the size
        of the lineart. If a size is passed, it will override 
        this value. """
        self.symbol_dict = None
        self.size = None
        self.spritesheets = {}
        self.images = {}
        self.sprites = {}

        # Shared empty sprite for placeholders
        self.blank_sprite = None

        self.load_tints()

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

    def spritesheet(self, a_file, name):
        """
        Add spritesheet called name from a_file.

        Parameters:
        a_file -- Path to the file to create a spritesheet from.
        name -- Name to call the new spritesheet.
        """
        self.spritesheets[name] = pygame.image.load(a_file).convert_alpha()

    def make_group(self,
                   spritesheet,
                   pos,
                   name,

                   sprites_x=6,
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


        # splitting group into singular sprites and storing into self.sprites section
        for y in range(sprites_y):
            for x in range(sprites_x):
                if no_index:
                    full_name = f"{name}"
                else:
                    full_name = f"{name}{i}"

                try:
                    new_sprite = pygame.Surface.subsurface(
                        self.spritesheets[spritesheet],
                        group_x_ofs + x * self.size,
                        group_y_ofs + y * self.size,
                        self.size, self.size
                    )

                except ValueError:
                    # Fallback for non-existent sprites
                    print(f"WARNING: nonexistent sprite - {full_name}")
                    if not self.blank_sprite:
                        self.blank_sprite = pygame.Surface(
                            (self.size, self.size),
                            pygame.HWSURFACE | pygame.SRCALPHA
                        )
                    new_sprite = self.blank_sprite

                self.sprites[full_name] = new_sprite
                i += 1

    def load_all(self):
        # get the width and height of the spritesheet
        lineart = pygame.image.load('sprites/lineart.png')
        width, height = lineart.get_size()
        del lineart  # unneeded

        # if anyone changes lineart for whatever reason update this
        if isinstance(self.size, int):
            pass
        elif width / 6 == height / 8:
            self.size = width / 6
        else:
            self.size = 50  # default, what base clangen uses
            print(f"lineart.png is not 3x7, falling back to {self.size}")
            print(f"if you are a modder, please update scripts/cat/sprites.py and "
                  f"do a search for 'if width / 3 == height / 7:'")

        del width, height  # unneeded

        for x in [
            'lineart', 'line', 'lineartdf', 'lineartdead', 'symbols',
            'fadestarclan', 'fadedarkforest', 'lightingnew', 'fademask', 'shadersnewwhite',
            'base', 'mid', 'dark', 'highlight', 'shade', 'unders',
            'eyebase', 'eyemid', 'eyetop', 'eyeshade', 'eyelight', 'eyes2', 'skin', 'scars', 'missingscars',
            'whitepatches', 'whitepatches2', 'whitepatchesmoss',
            'tortiepatchesmasks', 'tortiesmoss',
            'medcatherbs', 'accbase', 'accadd', 'accpattern', 'collaradd'

        ]:
            if 'lineart' in x and game.config['fun']['april_fools']:
                self.spritesheet(f"sprites/aprilfools{x}.png", x)
            else:
                self.spritesheet(f"sprites/{x}.png", x)

        # Line art
        self.make_group('lineart', (0, 0), 'lines')
        self.make_group('shadersnewwhite', (0, 0), 'shaders')
        self.make_group('lightingnew', (0, 0), 'lighting')

        self.make_group('lineartdead', (0, 0), 'lineartdead')
        self.make_group('lineartdf', (0, 0), 'lineartdf')

        # Fading Fog
        for i in range(0, 3):
            self.make_group('fademask', (i, 0), f'fademask{i}')
            self.make_group('fadestarclan', (i, 0), f'fadestarclan{i}')
            self.make_group('fadedarkforest', (i, 0), f'fadedf{i}')

        self.make_group('eyebase', (0, 0), 'eyebase')
        self.make_group('eyemid', (0, 0), 'eyemid')
        self.make_group('eyetop', (0, 0), 'eyetop')
        self.make_group('eyeshade', (0, 0), 'eyeshade')
        self.make_group('eyelight', (0, 0), 'eyelight')

        eye_patterns = [
            ['TRUE', 'CENTRAL', 'QUARTER', 'SLIVER', 'SPECKLES', 'FROSTED'],
            ['RING', 'HALFCENTRAL', 'HALFRING', 'BUBBLE', 'OUTRING', 'SWAP']
        ]

        for row, patterns in enumerate(eye_patterns):
            for col, pattern in enumerate(patterns):
                self.make_group('eyes2', (col, row), f'eyes2{pattern}')

        # Define white patches
        white_patches = [
            ['FULLWHITE', 'ANY', 'TUXEDO', 'LITTLE', 'COLOURPOINT', 'VAN', 'ANYTWO', 'MOON', 'PHANTOM', 'POWDER',
             'BLEACHED', 'SAVANNAH', 'FADESPOTS', 'PEBBLESHINE'],
            ['EXTRA', 'ONEEAR', 'BROKEN', 'LIGHTTUXEDO', 'BUZZARDFANG', 'RAGDOLL', 'LIGHTSONG', 'VITILIGO', 'BLACKSTAR',
             'PIEBALD', 'CURVED', 'PETAL', 'SHIBAINU', 'OWL'],
            ['TIP', 'FANCY', 'FRECKLES', 'RINGTAIL', 'HALFFACE', 'PANTSTWO', 'GOATEE', 'VITILIGOTWO', 'PAWS', 'MITAINE',
             'BROKENBLAZE', 'SCOURGE', 'DIVA', 'BEARD'],
            ['TAIL', 'BLAZE', 'PRINCE', 'BIB', 'VEE', 'UNDERS', 'HONEY', 'FAROFA', 'DAMIEN', 'MISTER', 'BELLY',
             'TAILTIP', 'TOES', 'TOPCOVER'],
            ['APRON', 'CAPSADDLE', 'MASKMANTLE', 'SQUEAKS', 'STAR', 'TOESTAIL', 'RAVENPAW', 'PANTS', 'REVERSEPANTS',
             'SKUNK', 'KARPATI', 'HALFWHITE', 'APPALOOSA', 'DAPPLEPAW']
        ]

        white_patches2 = [
            ['HEART', 'LILTWO', 'GLASS', 'MOORISH', 'SEPIAPOINT', 'MINKPOINT', 'SEALPOINT', 'MAO', 'LUNA', 'CHESTSPECK',
             'WINGS', 'PAINTED', 'HEARTTWO', 'WOODPECKER'],
            ['BOOTS', 'MISS', 'COW', 'COWTWO', 'BUB', 'BOWTIE', 'MUSTACHE', 'REVERSEHEART', 'SPARROW', 'VEST',
             'LOVEBUG', 'TRIXIE', 'SAMMY', 'SPARKLE'],
            ['RIGHTEAR', 'LEFTEAR', 'ESTRELLA', 'SHOOTINGSTAR', 'EYESPOT', 'REVERSEEYE', 'FADEBELLY', 'FRONT',
             'BLOSSOMSTEP', 'PEBBLE', 'TAILTWO', 'BUDDY', 'BACKSPOT', 'EYEBAGS'],
            ['BULLSEYE', 'FINN', 'DIGIT', 'KROPKA', 'FCTWO', 'FCONE', 'MIA', 'SCAR', 'BUSTER', 'SMOKEY', 'HAWKBLAZE',
             'CAKE', 'ROSINA', 'PRINCESS'],
            ['LOCKET', 'BLAZEMASK', 'TEARS', 'DOUGIE']
        ]

        white_patches_moss = [
            ['CHANCE', 'MOSSY', 'MOTH', 'NIGHTMIST', 'FALCON', 'VENUS', 'RETSUKO', 'TIDAL', 'DIAMOND', 'ECLIPSE', 'SNOWSTORM', 'PEPPER', 'COWTHREE', 'COWFOUR'],
            ['COWFIVE', 'COWSIX', 'COWSEVEN', 'COWEIGHT', 'COWNINE', 'COWTEN', 'COWELEVEN', 'FRECKLEMASK', 'SPLAT', 'BATWING', 'SMALLPATCHES']
        ]

        for row, patches in enumerate(white_patches):
            for col, patch in enumerate(patches):
                self.make_group('whitepatches', (col, row), f'white{patch}')
        for row, patches in enumerate(white_patches2):
            for col, patch in enumerate(patches):
                self.make_group('whitepatches2', (col, row), f'white{patch}')
        for row, patches in enumerate(white_patches_moss):
            for col, patch in enumerate(patches):
                self.make_group('whitepatchesmoss', (col, row), f'white{patch}')

        # base pelt - to be expanded with extras later
        self.make_group('base', (0, 0), 'baseSOLID')
        self.make_group('line', (0, 0), 'line')

        # Middle color layer
        mids = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN'],
            ['BRINDLE', 'CLASSIC', 'FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE'],
            ['SMOKE', 'FOG', 'MIST', 'SPLOTCH', 'SABER', 'SMUDGE'],
            ['ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]
        for row, mid in enumerate(mids):
            for col, md in enumerate(mid):
                self.make_group('mid', (col, row), f'mid{md}')

        # Highlight color layer
        highlights = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN'],
            ['BRINDLE', 'CLASSIC', 'FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE'],
            ['SMOKE', 'FOG', 'MIST', 'SPLOTCH', 'SABER', 'SMUDGE'],
            ['ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]
        for row, highlight in enumerate(highlights):
            for col, hl in enumerate(highlight):
                self.make_group('highlight', (col, row), f'highlight{hl}')

        # Dark color layer
        darks = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN'],
            ['BRINDLE', 'CLASSIC', 'FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE'],
            ['SMOKE', 'FOG', 'MIST', 'SPLOTCH', 'SABER', 'SMUDGE'],
            ['ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]
        for row, dark in enumerate(darks):
            for col, dr in enumerate(dark):
                self.make_group('dark', (col, row), f'dark{dr}')

        # Darker color layer
        shades = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN'],
            ['BRINDLE', 'CLASSIC', 'FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE'],
            ['SMOKE', 'FOG', 'MIST', 'SPLOTCH', 'SABER', 'SMUDGE'],
            ['ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]
        for row, shade in enumerate(shades):
            for col, sh in enumerate(shade):
                self.make_group('shade', (col, row), f'shade{sh}')

        # Unders color layer
        unders = [
            ['SOLID', 'TABBY', 'SPECKLED', 'ABYSSINIAN', 'BENGAL', 'LONGDAN'],
            ['BRINDLE', 'CLASSIC', 'FADED', 'MACKEREL', 'MARBLED', 'SINGLESTRIPE'],
            ['SMOKE', 'FOG', 'MIST', 'SPLOTCH', 'SABER', 'SMUDGE'],
            ['ROSETTE', 'MASKED', 'TICKED', 'AGOUTI', 'SOKOKE', 'BROKENMACKEREL'],
            ['BRAIDED', 'BROKENBRAIDED', 'DUST', 'CHARCOALBENGAL']
        ]
        for row, under in enumerate(unders):
            for col, ud in enumerate(under):
                self.make_group('unders', (col, row), f'under{ud}')

        # tortiepatchesmasks
        tortiepatchesmasks = [
            ['ONE', 'TWO', 'THREE', 'FOUR', 'REDTAIL', 'DELILAH', 'HALF', 'STREAK', 'MASK', 'SMOKE'],
            ['MINIMALONE', 'MINIMALTWO', 'MINIMALTHREE', 'MINIMALFOUR', 'OREO', 'SWOOP', 'CHIMERA', 'CHEST', 'ARMTAIL',
             'GRUMPYFACE'],
            ['MOTTLED', 'SIDEMASK', 'EYEDOT', 'BANDANA', 'PACMAN', 'STREAMSTRIKE', 'SMUDGED', 'DAUB', 'EMBER', 'BRIE'],
            ['ORIOLE', 'ROBIN', 'BRINDLE', 'PAIGE', 'ROSETAIL', 'SAFI', 'DAPPLENIGHT', 'BLANKET', 'BELOVED', 'BODY'],
            ['SHILOH', 'FRECKLED', 'HEARTBEAT']
        ]

        tortiepatchesmasksmoss = [
            ['VIPER', 'SKULL', 'POINTS', 'DITTO', 'TABBY', 'SPECKLED', 'BENGAL', 'CLASSIC', 'MACKEREL', 'MARBLED'],
            ['SABER', 'ROSETTE', 'MASKED', 'DUST', 'MAXIMUMONE', 'MAXIMUMTWO', 'MAXIMUMTHREE', 'MAXIMUMFOUR', 'MAXIMUMFIVE', 'MAXIMUMSIX'],
            ['MAXIMUMSEVEN', 'MAXIMUMEIGHT']
        ]

        for row, masks in enumerate(tortiepatchesmasks):
            for col, mask in enumerate(masks):
                self.make_group('tortiepatchesmasks', (col, row), f"tortiemask{mask}")

        for row, masks in enumerate(tortiepatchesmasksmoss):
            for col, mask in enumerate(masks):
                self.make_group('tortiesmoss', (col, row), f"tortiemask{mask}")

        # Define skin patterns
        skins = [
            ["SOLID", "TIP", "MARBLE", "FRECKLE"]
        ]

        for row, skins in enumerate(skins):
            for col, skin in enumerate(skins):
                self.make_group('skin', (col, row), f"skin{skin}")

        self.load_scars()
        self.load_symbols()

    def load_scars(self):
        """
        Loads scar sprites and puts them into groups.
        """

        # Define scars
        scars_data = [
            ["ONE", "TWO", "THREE", "MANLEG", "BRIGHTHEART", "MANTAIL", "BRIDGE", "RIGHTBLIND", "LEFTBLIND",
             "BOTHBLIND", "BURNPAWS", "BURNTAIL"],
            ["BURNBELLY", "BEAKCHEEK", "BEAKLOWER", "BURNRUMP", "CATBITE", "RATBITE", "FROSTFACE", "FROSTTAIL",
             "FROSTMITT", "FROSTSOCK", "QUILLCHUNK", "QUILLSCRATCH"],
            ["TAILSCAR", "SNOUT", "CHEEK", "SIDE", "THROAT", "TAILBASE", "BELLY", "TOETRAP", "SNAKE", "LEGBITE",
             "NECKBITE", "FACE"],
            ["HINDLEG", "BACK", "QUILLSIDE", "SCRATCHSIDE", "TOE", "BEAKSIDE", "CATBITETWO", "SNAKETWO", "FOUR"]
        ]

        # define missing parts
        missing_parts_data = [
            ["LEFTEAR", "RIGHTEAR", "NOTAIL", "NOLEFTEAR", "NORIGHTEAR", "NOEAR", "HALFTAIL", "NOPAW"]
        ]

        # scars 
        for row, scars in enumerate(scars_data):
            for col, scar in enumerate(scars):
                self.make_group('scars', (col, row), f'scars{scar}')

        # missing parts
        for row, missing_parts in enumerate(missing_parts_data):
            for col, missing_part in enumerate(missing_parts):
                self.make_group('missingscars', (col, row), f'scars{missing_part}')

        # accessories
        #to my beloved modders, im very sorry for reordering everything <333 -clay
        medcatherbs_data = [
            ["MAPLE LEAF", "HOLLY", "BLUE BERRIES", "FORGET ME NOTS", "RYE STALK", "CATTAIL", "SUNGLASSES", "LUNA MOTH", "ATLAS MOTH", "BIRD SKULL", "LUCKY CLOVER"],
            ["BLUEBELLS", "LILY OF THE VALLEY", "SNAPDRAGON", "ANTLERS", "STICK", "FIREFLIES", "SPROUT", "MUSHROOM", "JUNIPER", "RASPBERRY", "LAVENDER"],
            ["OAK LEAVES", "LILAC", "MAPLE SEED", "SEAWEED", "LILY PAD", "MONSTERA", "WILD FLOWERS", "TWIGS", "CLOVER", "SERPENT", "MOSS BALL"],
            ["RAINBOW COLLAR", "RAINBOW HARNESS", "RAINBOW BANDANA"]
        ]

        # medcatherbs
        for row, herbs in enumerate(medcatherbs_data):
            for col, herb in enumerate(herbs):
                self.make_group('medcatherbs', (col, row), f'acc{herb}')


        # please im begging you
        accbases_data = [
            ["COLLAR", "HARNESS", "BANDANA", "POPPY", "HERBS", "DAISY"],
            ["BULB", "PETALS", "FEATHER", "CICADA", "BUTTERFLY", "MOTH"],
            ["NETTLES", "HEATHER", "GORSE", "CATMINT", "LAUREL", "IVY"],
            ["BUTTERFLIES", "WREATH", "FLOWER WREATH", "SHELL", "CRYSTAL"]
        ]

        for row, accbases in enumerate(accbases_data):
            for col, accbase in enumerate(accbases):
                self.make_group('accbase', (col, row), f'accbase{accbase}')

        accadds_data = [
            ["COLLAR", "HARNESS", "BANDANA", "POPPY", "HERBS", "DAISY"],
            ["BULB", "PETALS", "FEATHER", "CICADA", "BUTTERFLY", "MOTH"],
            ["NETTLES", "HEATHER", "GORSE", "CATMINT", "LAUREL", "IVY"],
            ["BUTTERFLIES", "WREATH", "FLOWER WREATH", "SHELL", "CRYSTAL"]
        ]

        for row, accadds in enumerate(accadds_data):
            for col, accadd in enumerate(accadds):
                self.make_group('accadd', (col, row), f'accadd{accadd}')

        accpatterns_data = [
            ["STRIPES", "NOTES", "STARS", "IVYS", "PAWPRINTS", "PLAID"],
            ["ZEBRA", "HEARTS", "FLORAL", "SQUIGGLE", "WAVES", "DIAMONDS"],
            ["BUTTERFLIESONE", "BUTTERFLIESTWO", "FLOWERPRINTONE", "FLOWERPRINTTWO", "CONVERSE"]
        ]

        for row, accpatterns in enumerate(accpatterns_data):
            for col, accpattern in enumerate(accpatterns):
                self.make_group('accpattern', (col, row), f'accpattern{accpattern}')

        acccollars_data = [
            ["BELL", "BOW", "STUDDED", "FANG", "COWBOY HAT"]
        ]

        for row, acccollars in enumerate(acccollars_data):
            for col, acccollars in enumerate(acccollars):
                self.make_group('collaradd', (col, row), f'acccollars{acccollars}')

    def load_symbols(self):
        """
        loads clan symbols
        """

        if os.path.exists('resources/dicts/clan_symbols.json'):
            with open('resources/dicts/clan_symbols.json') as read_file:
                self.symbol_dict = ujson.loads(read_file.read())

        # U and X omitted from letter list due to having no prefixes
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
                   "V", "W", "Y", "Z"]

        # sprite names will format as "symbol{PREFIX}{INDEX}", ex. "symbolSPRING0"
        y_pos = 1
        for letter in letters:
            for i, symbol in enumerate([symbol for symbol in self.symbol_dict if
                                        letter in symbol and self.symbol_dict[symbol]["variants"]]):
                x_mod = 0
                for variant_index in range(self.symbol_dict[symbol]["variants"]):
                    x_mod += variant_index
                    self.clan_symbols.append(f"symbol{symbol.upper()}{variant_index}")
                    self.make_group('symbols',
                                    (i + x_mod, y_pos),
                                    f"symbol{symbol.upper()}{variant_index}",
                                    sprites_x=1, sprites_y=1, no_index=True)

            y_pos += 1

    def dark_mode_symbol(self, symbol):
        """Change the color of the symbol to dark mode, then return it
        :param Surface symbol: The clan symbol to convert"""
        dark_mode_symbol = copy(symbol)
        var = pygame.PixelArray(dark_mode_symbol)
        var.replace((87, 76, 45), (239, 229, 206))
        del var
        # dark mode color (239, 229, 206)
        # debug hot pink (255, 105, 180)

        return dark_mode_symbol

# CREATE INSTANCE
sprites = Sprites()
