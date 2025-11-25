import random
import logging
import traceback
from random import choice
from re import sub
from time import time_ns

import i18n

import scripts.game_structure.screen_settings
from scripts.cat.enums import CatAge, CatGroup
from scripts.cat.sprites import sprites
from scripts.cat.render import Render
from scripts.game_structure import constants, image_cache
from scripts.game_structure.localization import get_lang_config
from scripts.utility import adjust_list_text, union_of_entries, reverse_dict
from scripts.moss_util import read_resource_dict, OnUpdateList
from scripts.cat.accessory import Accessory, AccessoryDef

logger = logging.getLogger(__name__)


def weighted_choice(population, weights):
    return random.choices(population, weights, k=1)[0]

def choice_from_categories(categories, sets):
    return choice([ value for cat in categories for value in sets[cat] ])

def coin():
    return bool(random.getrandbits(1))

def weighted_coin(weight_true: int, weight_false: int):
    return random.randint(1, weight_true + weight_false) <= weight_true

def set_none_keys(target: dict):
    if '_None_' in target:
        target[None] = target['_None_']
        del target['_None_']
    for value in target.values():
        if isinstance(value, dict):
            set_none_keys(value)
    return target

def numbered(name, n):
    return [ name + ('' if n < 2 else f"_{i + 1}") for i in range(n) ]

def denumbered(name):
    parts = name.split('_')
    return (parts[0], 0) if len(parts) == 1 else (parts[0], int(parts[1]) - 1)


_moss_config = constants.CONFIG['moss']
_real_pelts = read_resource_dict('real_pelts', 'Real Pelts')
_fantasy_pelts = read_resource_dict('fantasy_pelts', 'Fantasy Pelts')

def _data_dict_for(config_key):
    return _real_pelts if _moss_config[config_key] else _fantasy_pelts


class Pelt:
    _pelt_data = read_resource_dict('pelt_data', 'Pelt Data')

    # ATTRIBUTES, including non-pelt related
    tortiemarking  = _data_dict_for('real_tortie_patches')['tortiepatches']['marking']
    tortiebases    = _data_dict_for('real_pelts'         )['tortiepatches']['bases']
    eye_patterns   = _data_dict_for('classic_hc'         )['eyepatterns']

    pelt_dict = _data_dict_for('real_pelts')['pelts']
    pelt_sets = list(pelt_dict.values())

    eyes_dict = _data_dict_for('real_eye_colors')['eyes']
    eye_colours = union_of_entries(eyes_dict)

    sprite_names = _data_dict_for('real_pelt_colors')['colors']
    sprite_sets = list(sprite_names.values())
    pelt_colours = union_of_entries(sprite_names)
    mottled_colors = set(sprite_names["black"] + sprite_names["brown"] + sprite_names["white"])

    white_patches = _data_dict_for('real_white_patches')['whitepatches']
    white_lists = [ white_patches['little'],
                    white_patches['mid'],
                    white_patches['high'],
                    white_patches['mostly'],
                    ["FULLWHITE"] ]
    white_low_end  = white_lists[0] + white_lists[1]
    white_high_end = white_lists[2] + white_lists[3] + white_lists[4]
    point_markings = white_patches['point']
    vit = white_patches['vit']

    all_scars = union_of_entries(_pelt_data['scars']['lists'])
    scar_reverse = reverse_dict(_pelt_data['scars']['lists'])

    conversion = set_none_keys(read_resource_dict('pelt_conversion', 'Old Save Conversion'))

    # Pelt editing
    @staticmethod
    def _edit_sprites_for(pelt, attr):
        if len(attr) > 1:
            return None
        return [ str(x) for x in Pelt._pelt_data['poses'][attr[0][7:]][pelt.length] ]
    @staticmethod
    def _edit_set_sprite(pelt, attr, value):
        pelt.cat_sprites[attr[0][7:]] = int(value)
    @staticmethod
    def _edit_get_sprite(pelt, attr):
        return str(pelt.cat_sprites[attr[0][7:]])
    _edit_sprite_funcs = (_edit_sprites_for, _edit_get_sprite, _edit_set_sprite, True)
        
    @staticmethod
    def _edit_set_suffix(pelt, attr, value):
        setattr(pelt, attr[0].split(' ')[-1], value)
    @staticmethod
    def _edit_get_suffix(pelt, attr):
        return getattr(pelt, attr[0].split(' ')[-1])
    _edit_suffix_funcs = (None, _edit_get_suffix, _edit_set_suffix, True)
    
    @staticmethod
    def _edit_accessory_children(pelt, attr):
        def available(slot):
            return sorted(Accessory.names_by_slot[slot])
        acc = (([ x for x in pelt.accessory if x.slot == attr[1] ] or [None])[0] 
               if len(attr) > 1 else None)
        if len(attr) == 3:
            attr = attr[:2] + [denumbered(attr[2])]
        match attr:
            case ['accessory']: 
                return sorted(Accessory.names_by_slot)
            case ['accessory', slot] if acc:
                return (['Remove', 'name'] + 
                        numbered('color',   len(acc.color)) + 
                        numbered('pattern', len(acc.pattern)))
            case ['accessory', slot]:
                return available(slot)
            case ['accessory', slot, ('name', _)]:
                return available(slot)
            case ['accessory', _, ('color', i)]:
                return acc.acc.available_colors(i)
            case ['accessory', _, ('pattern', i)]:
                return AccessoryDef.patterns
            case _:
                return None
    @staticmethod
    def _edit_accessory_get(pelt, attr):
        acc = (([ x for x in pelt.accessory if x.slot == attr[1] ] or [None])[0] 
               if len(attr) > 1 else None)
        if len(attr) == 3:
            attr = attr[:2] + [denumbered(attr[2])]
        match attr:
            case ['accessory', slot, ('name', _)]:
                return acc.name
            case ['accessory', slot, ('color', i)]:
                return acc.color[i]
            case ['accessory', slot, ('pattern', i)]:
                return acc.pattern[i]
            case _:
                return None
    @staticmethod
    def _edit_accessory_set(pelt, attr, value):
        acc = (([ x for x in pelt.accessory if x.slot == attr[1] ] or [None])[0] 
               if len(attr) > 1 else None)
        if len(attr) == 3:
            attr = attr[:2] + [denumbered(attr[2])]
        match attr:
            case ['accessory', slot] if value == 'Remove':
                pelt.accessory.remove(acc)
            case ['accessory', slot] | ['accessory', slot, ('name', _)]:
                pelt.accessory.append(value)
            case ['accessory', slot, ('color', i)]:
                acc.color[i] = value
            case ['accessory', slot, ('pattern', i)]:
                acc.pattern[i] = value
    _edit_accessory_funcs = (_edit_accessory_children, _edit_accessory_get, _edit_accessory_set, False)
   
    @staticmethod
    def _edit_scars_children(pelt, attr):
        match len(attr):
            case 1: 
                return ['Add'] + pelt.scars
            case 2:
                scars = Pelt.all_scars
                return scars if attr[1] == 'Add' else ['Remove'] + scars
            case _:
                return None
    @staticmethod
    def _edit_scars_get(pelt, attr):
        match attr:
            case ['scars', 'Add']:
                return None
            case ['scars', name]:
                return name
    @staticmethod
    def _edit_scars_set(pelt, attr, value):
        match attr:
            case ['scars', 'Add']:
                pelt.scars.append(value)
            case ['scars', name]:
                pelt.scars = [ x for x in pelt.scars + [value] if x != name and x != 'Remove' ]
    _edit_scars_funcs = (_edit_scars_children, _edit_scars_get, _edit_scars_set, False)
                
    @staticmethod
    def _tints(data):
        return union_of_entries(data["possible_tints"])
        
    edit_values = {
        'pelt name'         : union_of_entries(pelt_dict),
        'length'            : _pelt_data['pelt_length'],
        'colour'            : pelt_colours,
        'white_patches'     : [ x for y in white_lists for x in y ],
        'eye_colour'        : eye_colours,
        'eye_colour2'       : eye_colours,
        'eye_pattern'       : eye_patterns,
        'tortie_base'       : tortiebases,
        'tortie_colour'     : pelt_colours,
        'tortie_marking'    : tortiemarking,
        'tortie_pattern'    : tortiebases,
        'vitiligo'          : vit,
        'points'            : point_markings,
        'tint'              : _tints(sprites.cat_tints),
        'skin'              : _pelt_data['skin']['type'],
        'skin_color'        : _pelt_data['skin']['color'],
        'white_patches_tint': _tints(sprites.white_patches_tints),
        'reverse'           : ['False', 'True'],
        'tuft'              : _pelt_data['tuft']['type'],
        'tuft_color'        : _pelt_data['tuft']['color']['white'],
        'tortie_tuft'       : ['False', 'True'],
    }
    edit_funcs = { 
        'accessory'        : _edit_accessory_funcs,
        'scars'            : _edit_scars_funcs,     
        'pelt name'        : _edit_suffix_funcs,
        'sprite_newborn'   : _edit_sprite_funcs,
        'sprite_kitten'    : _edit_sprite_funcs,
        'sprite_adolescent': _edit_sprite_funcs,
        'sprite_adult'     : _edit_sprite_funcs,
        'sprite_senior'    : _edit_sprite_funcs
    }
    del _tints
    del _edit_sprites_for, _edit_set_sprite, _edit_get_sprite, _edit_sprite_funcs
    del _edit_set_suffix, _edit_get_suffix, _edit_suffix_funcs
    del _edit_accessory_children, _edit_accessory_get, _edit_accessory_set, _edit_accessory_funcs
    del _edit_scars_children, _edit_scars_get, _edit_scars_set, _edit_scars_funcs
    for x in edit_values.values():
        if isinstance(x, list) and len(x) > 10:
            x.sort()
    for key in ['white_patches', 'eye_colour2', 'eye_pattern', 'vitiligo', 'points', 'tuft', 
                'tortie_base', 'tortie_colour', 'tortie_marking', 'tortie_pattern']:
        edit_values[key] = ['None'] + edit_values[key]
    for key in ['tint', 'white_patches_tint']:
        edit_values[key] = ['none'] + edit_values[key]
    editable = sorted(set(edit_values) | set(edit_funcs))
    edit_translate_set = { 'None': None, 'False': False, 'True': True }
    edit_translate_get = { None: 'None', False: 'False', True: 'True' }


    """Holds all appearance information for a cat. """

    _scars = None
    _accessory = None
    
    def __init__(self,
                 name: str = "Solid",
                 length: str = "short",
                 color: str = "WHITE",
                 white_patches: str = None,
                 eye_colour: str = "BLUE",
                 eye_colour2: str = None,
                 eye_pattern: str = None,
                 tortie_base: str = None,
                 tortie_color: str = None,
                 tortie_marking: str = None,
                 tortie_pattern: str = None,
                 vitiligo: str = None,
                 points: str = None,
                 accessory: list[Accessory] = [],
                 paralyzed: bool = False,
                 opacity: int = 100,
                 scars: list = None,
                 tint: str = "none",
                 skin: str = "SOLID",
                 skin_color: str = "BLACK",
                 white_patches_tint: str = "offwhite",
                 sprite_newborn: int = None,
                 sprite_kitten: int = None,
                 sprite_adolescent: int = None,
                 sprite_adult: int = None,
                 sprite_senior: int = None,
                 sprite_para_adult: int = None,
                 reverse: bool = False,
                 tuft: str = None,
                 tuft_color: str = "BASE",
                 tortie_tuft: bool = False,
                 ) -> None:
        self.name = name
        self.colour = color
        self.white_patches = white_patches
        self.eye_colour = eye_colour
        self.eye_colour2 = eye_colour2
        self.eye_pattern = eye_pattern
        self.tortie_base = tortie_base
        self.tortie_marking = tortie_marking
        self.tortie_pattern = tortie_pattern
        self.tortie_colour = tortie_color
        self.vitiligo = vitiligo
        self.length = length
        self.points = points
        self.rebuild_sprite = True
        self.accessory = accessory
        self.paralyzed = paralyzed
        self.opacity = opacity
        self.scars = scars if isinstance(scars, list) else []
        self.tint = tint
        self.white_patches_tint = white_patches_tint
        self.screen_scale = scripts.game_structure.screen_settings.screen_scale
        self.cat_sprites = {"kitten"      : sprite_kitten     or 0,
                            "adolescent"  : sprite_adolescent or 0,
                            "young adult" : sprite_adult      or 0,
                            "adult"       : sprite_adult      or 0,
                            "senior adult": sprite_adult      or 0,
                            "senior"      : sprite_senior     or 0,
                            'newborn'     : sprite_newborn    or 0,
                            "para_adult"  : sprite_para_adult or 0}
        self.reverse = reverse
        self.skin = skin
        self.skin_color = skin_color
        self.tuft = tuft
        self.tuft_color = tuft_color
        self.tortie_tuft = tortie_tuft


    @staticmethod
    def load_from_cat(cat_dict):
        pelt_dict = {}
        for conv in Pelt.conversion['from_cat']:
            if 'keys' not in conv:
                keys = { conv['from']: conv['to'] }
            else:
                keys = { conv['from'].replace('*', x):
                         conv['to']  .replace('*', x)
                         for x in conv['keys'] }
            for old, new in keys.items():
                if old in cat_dict:
                    if 'op' in conv:
                        match conv['op']:
                            case 'append':
                                if new in pelt_dict:
                                    pelt_dict[new].append(cat_dict[old])
                                else:
                                    pelt_dict[new] = [cat_dict[old]]
                    else:
                        pelt_dict[new] = cat_dict[old]
        return Pelt.load(pelt_dict)


    @staticmethod
    def load(pelt_dict):
        for attr, sub_dict in Pelt.conversion['attribute'].items():
            if attr not in pelt_dict:
                continue
            current = pelt_dict[attr]
            if current not in sub_dict:
                continue
            for key, value in sub_dict[current].items():
                if key == '*':
                    key = attr
                if value == '*':
                    value = current
                pelt_dict[key] = value
        for key, prefix in Pelt.conversion['remove_prefix'].items():
            if key in pelt_dict and pelt_dict[key] and prefix in pelt_dict[key]:
                pelt_dict[key] = pelt_dict[key].replace(prefix, '').lower()
        Accessory.load_all(pelt_dict, Pelt.conversion['accessory'])
        pelt = Pelt(**pelt_dict)
        pelt.check_and_convert()
        return pelt


    @property
    def accessory(self):
        return self._accessory

    @accessory.setter
    def accessory(self, val):
        if isinstance(val, list):
            self.__make_accessory_list((Accessory.load(item) for item in val))
        else:
            if not hasattr(self, '_accessory'):
                self.__make_accessory_list()
            if isinstance(val, str) or isinstance(val, Accessory):
                self._accessory.append(Accessory.load(val))

    def _prune_accessories(self):
        # TODO: Also check limitation from scars
        if len(self._accessory) > len({ x.slot for x in self._accessory }):
            elems = { x.slot: x for x in self._accessory }.values()
            self.__make_accessory_list(elems)
        self.rebuild_sprite = True

    def __make_accessory_list(self, elems = ()):
        self._accessory = OnUpdateList(lambda : self._prune_accessories(),
                                       lambda x: Accessory.load(x),
                                       elems)
        if elems:
            self._prune_accessories()


    @property
    def scars(self):
        return self._scars

    @scars.setter
    def scars(self, val):
        self._update_scars(val)

    def _update_scars(self, val=None):
        orig = set(self._scars if val is None else val)
        for kind, exclusions in Pelt._pelt_data['scars']['exclude'].items():
            exclude = [ v for k, lst in exclusions.items() if k in orig for v in lst ]
            if kind == 'scars':
                exclude = set(exclude)
                val = { x for x in orig if x not in exclude }
            elif len(exclude) > 0:
                is_attrs = type(exclude[0]) is dict
                test = Pelt.__filter_attrs if is_attrs else Pelt.__filter_not_in
                keep = lambda x: all(( test(x, y) for y in exclude ))
                item = getattr(self, kind)
                if isinstance(item, list):
                    item = [ x for x in item if keep(x) ]
                else:
                    item = item if keep(item) else None
                setattr(self, kind, item)

        for combined, parts in Pelt._pelt_data['scars']['combine'].items():
            if all(( x in val for x in parts )):
                val = { x for x in val if x not in parts } | { combined }

        self._scars = OnUpdateList(lambda : self._update_scars(), None, val)


    @staticmethod
    def __filter_attrs(item, attrs):
        return all([ getattr(item, k) != v for k, v in attrs.items() ])

    @staticmethod
    def __filter_not_in(item, values):
        return item not in values


    @property
    def paralyzed(self):
        return self._paralyzed

    @paralyzed.setter
    def paralyzed(self, val):
        self.rebuild_sprite = True
        self._paralyzed = val


    def get_accessory_save(self):
        return [ acc.get_save() for acc in self.accessory ]


    @staticmethod
    def generate_new_pelt(gender: str, parents: tuple = (), age: str = "adult"):
        new_pelt = Pelt()

        pelt_white = new_pelt.init_pattern_color(parents, gender)
        new_pelt.init_white_patches(pelt_white, parents)
        new_pelt.init_sprite()
        new_pelt.init_scars(age)
        new_pelt.init_accessories(age)
        new_pelt.init_eyes(parents)
        new_pelt.init_pattern()
        new_pelt.init_tint()

        return new_pelt


    def render(self,
               pose,
               dead=False,
               group=None,
               can_fade=True,
               scars_hidden=False,
               acc_hidden=False,
               load_only=False,
               name=None):
        try:
            t = time_ns()
            render = Render(pose, flip= self.reverse, load_only= load_only)
            render.set(colormap= 'pelt')

            # Moss settings
            black   = constants.CONFIG["moss"]["black_lineart"]
            tint_on = constants.CONFIG["moss"]["enable_tints"]

            # Tufts
            if self.tuft is not None:
                if self.tuft_color == "WHITE":
                    color = "BLACK" if self.white_patches_tint == "black" else "WHITE"
                    index = 0
                else:
                    color = self.tortie_colour if self.tortie_tuft else self.colour
                    index = Pelt._pelt_data['tuft']['color']['other'].index(self.tuft_color)
                render.set(sprite= self.tuft, color= color)
                render.paint('tufts', index)
                render.paint('tuftlines', 5, color= "BLACK" if black else color)

            # Pelt
            def paint_pelt(render):
                render.paint('base', 1, sprite= 'SOLID')
                render.paint_all(('under', 0), ('mid', 2), ('dark', 3), ('shade', 4), ('highlight', 0))
                render.paint('line', 5, sprite= '')

            tortie = self.name in ['Tortie', 'Calico']
            render.set(color= self.colour, sprite= self.tortie_base if tortie else self.name)
            paint_pelt(render)

            if tortie:
                render.set(color= self.tortie_colour, sprite= self.tortie_pattern)
                render.add_layer('base', sprite= 'SOLID')
                paint_pelt(render)
                render.set(color=self.tortie_colour, sprite=self.tortie_marking)
                render.paint('tortiemask', blend= 'alpha')
                render.merge_layer()

            # Tint
            if tint_on and self.tint is not None:
                if self.tint in Render.colors['tint']:
                    render.paint(colormap= 'tint', color= self.tint, index= 0)
                elif self.tint in Render.colors['dilute_tint']:
                    render.paint(colormap= 'dilute_tint', color= self.tint, index= 0, blend= 'add')

            # White patches, vit & points
            tint = self.white_patches_tint
            if tint not in Render.colors['patches_tint']:
                tint = None
            render.set(colormap= 'patches_tint')
            for sprite in [self.white_patches, self.points]:
                if sprite:
                    render.paint('white', sprite= sprite, color= tint, index= 0 if tint else None)
            if self.vitiligo:
                render.paint('white', sprite= self.vitiligo)

            # Eyes
            render.set(colormap= 'eyes', color= self.eye_colour, sprite= '')
            render.paint_all(('eyebase', 0), ('eyemid', 1), ('eyetop', 2), ('eyeshade', 3))
            if self.eye_pattern != None:
                render.set(color= self.eye_colour2)
                render.add_layer('eyebase')
                render.paint_all(('eyebase', 0), ('eyemid', 1), ('eyetop', 2), ('eyeshade', 3))
                render.paint('eyes2', sprite= self.eye_pattern, blend= 'alpha')
                render.merge_layer()
            render.paint('eyelight')

            # Lineart
            unknown = dead and group == CatGroup.UNKNOWN_RESIDENCE
            forest  = dead and group == CatGroup.DARK_FOREST
            render.set(sprite= '', colormap= 'line')
            if black:
                render.set(color= 'BLACK')
            elif unknown:
                render.set(color= 'PURPLE')
            elif forest:
                render.set(color= 'RED')
            elif dead:
                render.set(color= 'BLUE')
            if black or dead:
                render.paint('line', 0)
            if forest:
                render.paint('lineartdf')
            elif dead and not unknown:
                render.paint('lineartdead')

            # Skin
            render.paint('skin', 0, sprite= self.skin, colormap= 'skin', color= self.skin_color)

            # Scars
            if not scars_hidden:
                args_lists = Pelt._pelt_data['scars']['render']
                reverse = Pelt.scar_reverse
                for scar in self.scars:
                    for args in args_lists[reverse[scar]]:
                        render.paint(sprite= scar, **args)

            # Accessories
            if not acc_hidden:
                for acc in sorted(self.accessory, key= lambda x: x.order):
                    acc.render(render)

            # Fading
            if dead and can_fade and self.opacity <= 97:
                render.set(sprite= str((80 - self.opacity) // 35 + 1))
                render.paint('fademask', blend= 'alpha')
                sheet = 'fade' + ('df' if forest else ('ur' if unknown else 'starclan'))
                render.add_layer(sheet, insert= True).merge_layer()

            sprite = render.image
            t2 = time_ns()
            #print(f"Rendered {name}'s pelt in {(t2 - t) / 1000000} ms.")

        except (TypeError, KeyError):
            traceback.print_exc()
            logger.exception("Failed to load sprite")

            # Placeholder image
            sprite = image_cache.load_image('sprites/error_placeholder.png').convert_alpha()

        return sprite


    def check_and_convert(self):
        """Checks for old-type values for the appearance-related properties
        that are stored in Pelt, and converts them. To be run when loading a cat in."""

        poses = self.cat_sprites
        for age in ['newborn', 'kitten', 'adolescent', 'adult', 'senior']:
            available = Pelt._pelt_data['poses'][age][self.length]
            if poses[age] not in available:
                poses[age] = choice(available)
                if age == 'adult':
                    poses['young adult'] = poses['senior adult'] = poses[age]



    def excluded_scars(self):
        data = Pelt._pelt_data['scars']['exclude']['scars']
        return { x for y in self.scars if y in data for x in data[y] }


    def excluded_accessory_slots(self):
        from_scars = Pelt._pelt_data['scars']['exclude']['accessory']
        used    = { x.slot for x in self.accessory }
        blocked = { x['slot'] for a in ( y for y in self.scars if y in from_scars )
                              for x in from_scars[a] if 'slot' in x }
        return used | blocked


    def remove_accessory_in_slot(self, slot):
        self.accessory = [ x for x in self.accessory if x.slot != slot ]


    def add_accessory_for_event(self, possible):
        acc = Accessory.create_random_for_event(possible, self.excluded_accessory_slots())
        if acc is None:
            return False
        else:
            self.accessory.append(acc)
            return True


    # Pelt editing
    def edit_options_for(self, attribute):
        n = len(attribute)
        if n == 0:
            return Pelt.editable
        
        first = attribute[0]
        funcs = Pelt.edit_funcs.get(first)
        if n == 1 and first in Pelt.edit_values:
            return Pelt.edit_values[first]
        elif funcs and funcs[0]:
            return funcs[0](self, attribute)
        return None

    def edit_get(self, attribute):
        first = attribute[0]
        funcs = Pelt.edit_funcs.get(first)
        translate = funcs is None or funcs[3]
        if funcs:
            value = funcs[1](self, attribute)
        else:
            value = getattr(self, first)
        if translate and value in Pelt.edit_translate_get:
            value = Pelt.edit_translate_get[value]
        return value

    def edit_set(self, attribute, value):
        first = attribute[0]
        funcs = Pelt.edit_funcs.get(first)
        translate = funcs is None or funcs[3]
        if translate and value in Pelt.edit_translate_set:
            value = Pelt.edit_translate_set[value]
        if funcs:
            funcs[2](self, attribute, value)
        else:
            setattr(self, first, value)
        self.rebuild_sprite = True


    @staticmethod
    def _calc_inheritance_weights(category, groupings, parent_values, ensure_not_zero = True):
        weight_data = Pelt._pelt_data['inheritance'][category]
        n = len(next(iter(weight_data.values())))
        zero = [0 for i in range(n)]
        unknown = weight_data['_unknown_'] if '_unknown_' in weight_data else zero
        weights = [0 for i in range(n)]

        for value in parent_values:
            if value is None:
                add = unknown
            else:
                add = zero
                for key in weight_data:
                    if key in groupings and value in groupings[key] or key == value:
                        add = weight_data[key]
                        break

            for x in range(n):
                weights[x] += add[x]

        # If we have no weights at all, replace with equal chance for all
        if ensure_not_zero and not any(weights):
            weights = [1 for i in range(n)]

        return weights


    def init_eyes(self, parents):
        """Sets eye color for this cat's pelt. Takes parents' eye colors into account.
        Heterochromia is possible based on the white-ness of the pelt, so the pelt color and white_patches must be
        set before this function is called.

        :param parents: List[Cat] representing this cat's parents

        :return: None
        """
        if weighted_coin(1, len(parents)):
            self.eye_colour = choice(Pelt.eye_colours)
        else:
            self.eye_colour = choice(parents).pelt.eye_colour

        # White patches must be initalized before eye color.
        num = constants.CONFIG["cat_generation"]["base_heterochromia"]
        if self.white_patches == "FULLWHITE" or self.colour == "WHITE" or self.colour == "SNOW WHITE":
            num -= 100
        elif self.white_patches in Pelt.white_high_end:
            num -= 90
        for _par in parents:
            if _par.pelt.eye_colour2:
                num -= 10
        if num < 0:
            num = 1

        if not random.randint(0, num):
            color_wheel = [ x for x in Pelt.eyes_dict.values() if self.eye_colour not in x ]
            self.eye_colour2 = choice(choice(color_wheel))
            self.eye_pattern = choice(Pelt.eye_patterns)


    def pattern_color_inheritance(self, parents: tuple = (), gender="female"):
        # Collect parent pelt categories. Some are sets to remove duplicates.
        par_pelts       = [ p.pelt for p in parents ]
        par_peltlength  = { p.length if p else None   for p in par_pelts }
        par_peltcolours = { p.colour if p else None   for p in par_pelts }
        par_white       = [ p.white  if p else coin() for p in par_pelts ]
        par_tufts       = { p.tuft   if p else None   for p in par_pelts }
        torties = Pelt.pelt_dict['torties']
        par_torties   = [ p and p.name in torties for p in par_pelts ]
        par_peltnames = { 
            p.tortie_base.capitalize() if t else p.name 
            for p, t in zip(par_pelts, par_torties)
        }
        # Now filter out unknown
        par_pelts       = [ p for p in par_pelts if p ]
        par_tufts_color = { p.tuft_color for p in par_pelts }

        # If this list is empty, something went wrong.
        if not par_peltcolours:
            print("Warning - no parents: pelt randomized")
            return self.randomize_pattern_color(gender)

        # There is a 1/10 chance for kits to have the exact same pelt as one of their parents
        if not random.randint(
            0, constants.CONFIG["cat_generation"]["direct_inheritance"]
        ):  # 1/10 chance
            selected = choice(par_pelts)
            self.name = selected.name
            self.length = selected.length
            self.colour = selected.colour
            self.tortie_base = selected.tortie_base
            return selected.white

        # PELT
        
        # Determine pelt.
        weights = Pelt._calc_inheritance_weights('pelts', Pelt.pelt_dict, par_peltnames)

        # Now, choose the pelt category and pelt. The extra 0 is for the tortie pelts,
        chosen_pelt = choice(weighted_choice(Pelt.pelt_sets, weights + [0]))

        # Tortie chance
        female = gender == 'female'
        key = 'base_female_tortie' if female else 'base_male_tortie'
        tortie_chance = constants.CONFIG['cat_generation'][key]
        if any(par_torties):
            tortie_chance = int(tortie_chance / 2) if female else tortie_chance - 1

        # Determine tortie:
        chosen_tortie_base = None
        if random.getrandbits(tortie_chance) == 1:
            # If it is tortie, the chosen pelt above becomes the base pelt.
            chosen_tortie_base = chosen_pelt

            if chosen_tortie_base in ("TwoColour", "SingleColour"):
                chosen_tortie_base = "Solid"

            chosen_tortie_base = chosen_tortie_base.lower()
            chosen_pelt = random.choice(torties)

        # PELT COLOUR
        weights = Pelt._calc_inheritance_weights('colors', Pelt.sprite_names, par_peltcolours)
        chosen_pelt_color = choice(weighted_choice(Pelt.sprite_sets, weights))

        # PELT LENGTH
        # TODO: move weights to pelt_data
        weights = [0, 0, 0]  # Weights for each length. It goes (short, medium, long)
        for p_ in par_peltlength:
            if p_ == "short":
                add_weight = (50, 10, 2)
            elif p_ == "medium":
                add_weight = (25, 50, 25)
            elif p_ == "long":
                add_weight = (2, 10, 50)
            elif p_ is None:
                add_weight = (10, 10, 10)
            else:
                add_weight = (0, 0, 0)

            for x in range(0, len(weights)):
                weights[x] += add_weight[x]

        # A quick check to make sure all the weights aren't 0
        if all([x == 0 for x in weights]):
            weights = [1, 1, 1]

        chosen_pelt_length = weighted_choice(Pelt._pelt_data['pelt_length'], weights)

        # PELT WHITE
        # There are 94 percentage points that can be added by
        # parents having white. If we have more than two, this
        # will keep that the same.
        per_parent = int(94 / len(par_white))
        chance = 3 + per_parent * sum(1 for p in par_white if p)

        chosen_white = random.randint(1, 100) <= chance

        # Adjustments to pelt chosen based on if the pelt has white in it or not.

        if chosen_pelt in ("TwoColour", "SingleColour"):
            if chosen_white:
                chosen_pelt = "Solid"
            else:
                chosen_pelt = "Solid"
        elif chosen_pelt == "Calico":
            if not chosen_white:
                chosen_pelt = "Tortie"

        # SET THE PELT
        self.name = chosen_pelt
        self.colour = chosen_pelt_color
        self.length = chosen_pelt_length
        self.tortie_base = (
            chosen_tortie_base  # This will be none if the cat isn't a tortie.
        )
        return chosen_white


    def randomize_pattern_color(self, gender):
        # ------------------------------------------------------------------------------------------------------------#
        #   PELT
        # ------------------------------------------------------------------------------------------------------------#

        # Determine pelt.
        chosen_pelt = choice(
            weighted_choice(Pelt.pelt_sets, (35, 20, 30, 15, 20, 15, 0))
        )

        # Tortie chance
        # There is a default chance for female tortie, slightly increased for completely random generation.
        tortie_chance_f = constants.CONFIG["cat_generation"]["base_female_tortie"] - 1
        tortie_chance_m = constants.CONFIG["cat_generation"]["base_male_tortie"]
        if gender == "female":
            torbie = random.getrandbits(tortie_chance_f) == 1
        else:
            torbie = random.getrandbits(tortie_chance_m) == 1

        chosen_tortie_base = None
        if torbie:
            # If it is tortie, the chosen pelt above becomes the base pelt.
            chosen_tortie_base = chosen_pelt

            if chosen_tortie_base in ("TwoColour", "SingleColour"):
                chosen_tortie_base = "Solid"

            chosen_tortie_base = chosen_tortie_base.lower()
            chosen_pelt = random.choice(Pelt.pelt_dict['torties'])

        # ------------------------------------------------------------------------------------------------------------#
        #   PELT COLOUR
        # ------------------------------------------------------------------------------------------------------------#

        chosen_pelt_color = choice(choice(Pelt.sprite_sets))

        # ------------------------------------------------------------------------------------------------------------#
        #   PELT LENGTH
        # ------------------------------------------------------------------------------------------------------------#

        chosen_pelt_length = choice(Pelt._pelt_data['pelt_length'])

        # ------------------------------------------------------------------------------------------------------------#
        #   PELT WHITE
        # ------------------------------------------------------------------------------------------------------------#

        chosen_white = random.randint(1, 100) <= 40

        # Adjustments to pelt chosen based on if the pelt has white in it or not.

        if chosen_pelt in ("TwoColour", "SingleColour"):
            if chosen_white:
                chosen_pelt = "Solid"
            else:
                chosen_pelt = "Solid"
        elif chosen_pelt == "Calico":
            if not chosen_white:
                chosen_pelt = "Tortie"

        self.name = chosen_pelt
        self.colour = chosen_pelt_color
        self.length = chosen_pelt_length
        self.tortie_base = (
            chosen_tortie_base  # This will be none if the cat isn't a tortie.
        )
        return chosen_white


    def init_pattern_color(self, parents, gender) -> bool:
        """Inits self.name, self.colour, self.length,
        self.tortie_base and determines if the cat
        will have white patche or not.
        Return TRUE is the cat should have white patches,
        false is not."""

        if parents:
            # If the cat has parents, use inheritance to decide pelt.
            chosen_white = self.pattern_color_inheritance(parents, gender)
        else:
            chosen_white = self.randomize_pattern_color(gender)

        return chosen_white


    def init_sprite(self):
        self.reverse = bool(random.getrandbits(1))

        # skin chances
        data = Pelt._pelt_data['skin']
        self.skin = choice(data['type'])
        self.skin_color = choice(data['color'])

        # poses
        data = Pelt._pelt_data['poses']
        poses = self.cat_sprites

        poses['newborn'] = choice(data['newborn'][self.length])
        poses['kitten' ] = choice(data['kitten'][self.length])

        poses['adolescent'] = choice(data['aging'][str(poses['kitten'])])
        poses['adult'     ] = choice(data['aging'][str(poses['adolescent'])])
        poses['senior'    ] = choice(data['aging'][str(poses['adult'])])

        poses['young adult' ] = poses['adult']
        poses['senior adult'] = poses['adult']


    @staticmethod
    def __roll(chance):
        """
        Takes a chance expressed as a "1 in x" chance, with 0 meaning never.
        Returns the result of the roll as a boolean.
        """
        return chance > 0 and random.randint(1, chance) == 1

    def init_scars(self, age):
        data = Pelt._pelt_data['scars']

        if Pelt.__roll(data['generate']['chance'][age]):
            lists = [ data['lists'][key] for key in data['generate']['use_lists'] ]
            self.scars += [choice(choice(lists))]


    def init_accessories(self, age):
        if Pelt.__roll(Pelt._pelt_data['accessory_chance'][age]):
            self.accessory = [Accessory.create_random_from_set('initial')]
        else:
            self.accessory = []


    def init_pattern(self):
        if self.name in Pelt.pelt_dict['torties']:
            if not self.tortie_base:
                self.tortie_base = choice(Pelt.tortiebases)
            if not self.tortie_marking:
                self.tortie_marking = choice(Pelt.tortiemarking)

            color_sets = _data_dict_for('real_tortie_colors')['tortiecolors']
            self.tortie_colour = color_sets['_default_']  # Default if not set below

            wildcard_chance = constants.CONFIG["cat_generation"]["wildcard_tortie"]
            if self.colour:
                # The "not wildcard_chance" allows users to set wildcard_tortie to 0
                # and always get wildcard torties.
                if not wildcard_chance or random.getrandbits(wildcard_chance) == 1:
                    # This is the "wildcard" chance, where you can get funky combinations.
                    # people are fans of the print message, so I'm putting it back
                    print("Wildcard tortie!")

                    # Allow any pattern:
                    self.tortie_pattern = choice(Pelt.tortiebases)

                    # Allow any colors that aren't the base color.
                    possible_colors = Pelt.pelt_colours.copy()
                    possible_colors.remove(self.colour)
                    self.tortie_colour = choice(possible_colors)

                else:
                    # Normal generation
                    if self.tortie_base in ("solid"):
                        self.tortie_pattern = choice(Pelt.tortiebases)
                    else:
                        self.tortie_pattern = weighted_choice([self.tortie_base, "solid"], [97, 3])

                    for key, colors in Pelt.sprite_names.items():
                        if self.colour in colors:
                            color_set = color_sets[key]
                            break

                    def choose_color(key):
                        return choice_from_categories(color_set[key], Pelt.sprite_names)

                    self.tortie_colour = choose_color('*')
                    if 'base' in color_set:
                        self.colour = choose_color('base')

        else:
            self.tortie_base = None
            self.tortie_pattern = None
            self.tortie_colour = None
            self.tortie_marking = None

    def white_patches_inheritance(self, parents: tuple):
        par_whitepatches = set()
        par_points = []
        for p in parents:
            if p:
                if p.pelt.white_patches:
                    par_whitepatches.add(p.pelt.white_patches)
                if p.pelt.points:
                    par_points.append(p.pelt.points)

        if not parents:
            print("Error - no parents. Randomizing white patches.")
            self.randomize_white_patches()
            return

        # Direct inheritance. Will only work if at least one parent has white patches, otherwise continue on.
        if par_whitepatches and not random.randint(
            0, constants.CONFIG["cat_generation"]["direct_inheritance"]
        ):
            # This ensures Torties and Calicos won't get direct inheritance of incorrect white patch types
            par_wp_filtered = par_whitepatches
            if self.name == "Tortie":
                par_wp_filtered = [x for x in par_whitepatches if x not in Pelt.white_high_end]
            elif self.name == "Calico":
                par_wp_filtered = [x for x in par_whitepatches if x not in Pelt.white_low_end]

            # Only proceed with the direct inheritance if there are white patches that match the pelt.
            if par_wp_filtered:
                self.white_patches = choice(list(par_wp_filtered))

                # Direct inheritance also effect the point marking.
                if par_points and self.name != "Tortie":
                    self.points = choice(par_points)
                else:
                    self.points = None
                return

        # dealing with points
        if par_points:
            chance = 10 - len(par_points)
        else:
            chance = 40
        # Chance of point is 1 / chance.
        if self.name != "Tortie" and not int(random.random() * chance):
            self.points = choice(Pelt.point_markings)
        else:
            self.points = None

        weights = Pelt._calc_inheritance_weights('white_patches', 
                                                 Pelt.white_patches, 
                                                 par_whitepatches)
        if not any(weights):
            key = '_no_patches_' if all(parents) else '_any_unknown_'
            weights = Pelt._pelt_data['inheritance']['white_patches'][key]

        # Adjust weights for torties, since they can't have anything greater than mid_white:
        if self.name == "Tortie":
            weights = weights[:2] + [0, 0, 0]
        elif self.name == "Calico":
            weights = [0, 0, 0] + weights[3:]
        # Another check to make sure not all the values are zero. This should never happen, but better
        # safe than sorry.
        if not any(weights):
            weights = [2, 1, 0, 0, 0]

        chosen_white_patches = choice(weighted_choice(Pelt.white_lists, weights))

        self.white_patches = chosen_white_patches
        if self.points and self.white_patches in Pelt.white_low_end:
            self.points = None


    def randomize_white_patches(self):
        # Points determination. Tortie can't be pointed
        if self.name != "Tortie" and not random.getrandbits(
            constants.CONFIG["cat_generation"]["random_point_chance"]
        ):
            # Cat has colorpoint!
            self.points = choice(Pelt.point_markings)
        else:
            self.points = None

        # Adjust weights for torties, since they can't have anything greater than mid_white:
        if self.name == "Tortie":
            weights = (2, 1, 0, 0, 0)
        elif self.name == "Calico":
            weights = (0, 0, 20, 15, 1)
        else:
            weights = (10, 10, 10, 10, 1)

        chosen_white_patches = choice(weighted_choice(Pelt.white_lists, weights))

        self.white_patches = chosen_white_patches
        if self.points and self.white_patches in Pelt.white_high_end:
            self.points = None


    def init_white_patches(self, pelt_white, parents: tuple):
        # Vit can roll for anyone, not just cats who rolled to have white in their pelt.
        par_vit = []
        for p in parents:
            if p:
                if p.pelt.vitiligo:
                    par_vit.append(p.pelt.vitiligo)

        vit_chance = max(constants.CONFIG["cat_generation"]["vit_chance"] - len(par_vit), 0)
        if not random.getrandbits(vit_chance):
            self.vitiligo = choice(Pelt.vit)

        # If the cat was rolled previously to have white patches, then determine the patch they will have
        # these functions also handle points.
        if pelt_white:
            if parents:
                self.white_patches_inheritance(parents)
            else:
                self.randomize_white_patches()
        else:
            self.white_patches = None
            self.points = None
        #tufts
        #set tortie tuft
        if self.name == "Tortie":
            tt_chance = random.randint(1, 100)
            if tt_chance > 50:
                self.tortie_tuft = True
        elif self.name == "Calico":
            tt_chance = random.randint(1, 100)
            if tt_chance > 50:
                self.tortie_tuft = True
        else:
            self.tortie_tuft = False

        #get parents info
        par_tuft = []
        par_tuft_color = []
        for p in parents:
            if p:
                if p.pelt.tuft:
                    par_tuft.append(p.pelt.tuft)
                    par_tuft_color.append(p.pelt.tuft_color)

        #longhair have better chance of tufts
        if self.length == "long":
            base_tuft_chance = random.randint(1, 100)
            longhair_chance = 30
            tuft_chance = base_tuft_chance + longhair_chance
        else:
            tuft_chance = random.randint(1, 100)
        if tuft_chance > 70:
            data = Pelt._pelt_data['tuft']
            types = data['type']
            colors = data['color']['white' if pelt_white else 'other']
            if parents:
                if weighted_coin(5 * len(par_tuft), len(types)):
                    types = par_tuft
                if weighted_coin(5 * len(par_tuft_color), len(colors)):
                    colors = par_tuft_color
            self.tuft = choice(types)
            self.tuft_color = choice(colors)
        else:
            self.tuft = None
            self.tuft_color = "BASE"




    def init_tint(self):
        """Sets tint for pelt and white patches"""

        # PELT TINT
        # Basic tints as possible for all colors.
        base_tints = sprites.cat_tints["possible_tints"]["basic"]
        if self.colour in sprites.cat_tints["colour_groups"]:
            color_group = sprites.cat_tints["colour_groups"].get(self.colour, "warm")
            color_tints = sprites.cat_tints["possible_tints"][color_group]
        else:
            color_tints = []

        if base_tints or color_tints:
            self.tint = choice(base_tints + color_tints)
        else:
            self.tint = "none"

        # WHITE PATCHES TINT
        if self.white_patches or self.points:
            # Now for white patches
            base_tints = sprites.white_patches_tints["possible_tints"]["basic"]
            if self.colour in sprites.cat_tints["colour_groups"]:
                color_group = sprites.white_patches_tints["colour_groups"].get(
                    self.colour, "white"
                )
                color_tints = sprites.white_patches_tints["possible_tints"][color_group]
            else:
                color_tints = []

            if base_tints or color_tints:
                if constants.CONFIG["moss"]["black_white_patches"]:
                    black_patches = sprites.white_patches_tints["possible_tints"]["blackpatches"]
                    self.white_patches_tint = choice(base_tints + color_tints + black_patches)
                else:
                    self.white_patches_tint = choice(base_tints + color_tints)
            else:
                self.white_patches_tint = "none"
        else:
            self.white_patches_tint = "none"


    def is_mottled(self):
        return self.colour in Pelt.mottled_colors and self.tortie_colour in Pelt.mottled_colors


    @property
    def white(self):
        return self.white_patches or self.points


    def describe_eyes(self):
        return (
            adjust_list_text(
                [ i18n.t(f"cat.eyes.{x}") for x in [ self.eye_colour, self.eye_colour2 ] ]
            )
            if self.eye_colour2
            else i18n.t(f"cat.eyes.{self.eye_colour}")
        )


    @staticmethod
    def describe_appearance(cat, short=False):
        """Return a description of a cat

        :param Cat cat: The cat to describe
        :param bool short: Whether to return a heavily-truncated description, default False
        :return str: The cat's description
        """


        config = get_lang_config()["description"]
        ruleset = config["ruleset"]
        output = []
        pelt_pattern, pelt_color = _describe_pattern(cat, short)
        for rule, args in ruleset.items():
            temp = unpack_appearance_ruleset(cat, rule, short, pelt_pattern, pelt_color)

            if args == "" or temp == "":
                output.append(temp)
                continue

            # handle args
            argpool = {
                arg: unpack_appearance_ruleset(
                    cat, arg, short, pelt_pattern, pelt_color
                )
                for arg in args
            }
            argpool["key"] = temp
            argpool["count"] = 1 if short else 2
            output.append(i18n.t(**argpool))


        # don't forget the count argument!
        groups = []
        for grouping in config["groups"]:
            temp = ""
            items = [
                i18n.t(output[i], count=1 if short else 2)
                for i in grouping["values"]
                if output[i] != ""
            ]
            if len(items) == 0:
                continue
            if "pre_value" in grouping:
                temp = grouping["pre_value"]

            if grouping["format"] == "list":
                temp += adjust_list_text(items)
            else:
                temp += grouping["format"].join(items)


            if "post_value" in grouping:
                temp += grouping["post_value"]
            groups.append(temp)

        return "".join(groups)


def _describe_pattern(cat, short=False):
    color_name = [f"cat.pelts.{str(cat.pelt.colour)}"]
    pelt_name = f"cat.pelts.{cat.pelt.name}{'' if short else '_long'}"
    if cat.pelt.name in Pelt.pelt_dict['torties']:
        pelt_name, color_name = _describe_torties(cat, color_name, short)

    color_name = [i18n.t(piece, count=1) for piece in color_name]
    color_name = "".join(color_name)

    if cat.pelt.white_patches:
        if cat.pelt.white_patches == "FULLWHITE":
            # If the cat is fullwhite, discard all other information. They are just white
            color_name = i18n.t("cat.pelts.FULLWHITE")
            pelt_name = ""
        elif cat.pelt.name != "Calico":
            white = i18n.t("cat.pelts.FULLWHITE")
            if i18n.t("cat.pelts.WHITE", count=1) in color_name:
                color_name = white
            elif cat.pelt.white_patches in Pelt.white_patches['mostly']:
                color_name = adjust_list_text([white, color_name])
            else:
                color_name = adjust_list_text([color_name, white])

    if cat.pelt.points:
        color_name = i18n.t("cat.pelts.point", color=color_name)
        if "ginger point" in color_name:
            color_name.replace("ginger point", "flame point")
            # look, I'm leaving this as a quirk of the english language, if it's a problem elsewhere lmk

    return pelt_name, color_name


def _describe_torties(cat, color_name, short=False) -> [str, str]:
    # Calicos and Torties need their own desciptions
    if short:
        # If using short, don't describe the colors of calicos and torties.
        # Just call them calico, tortie, or mottled
        if cat.pelt.is_mottled():
            return "cat.pelts.mottled", ""
        else:
            return f"cat.pelts.{cat.pelt.name}", ""

    base = cat.pelt.tortie_base.lower()

    patches_color = f"cat.pelts.{cat.pelt.tortie_colour}"
    color_name.append("/")
    color_name.append(patches_color)

    if cat.pelt.is_mottled():
        return "cat.pelts.mottled_long", color_name
    else:
        if base in tuple(tabby.lower() for tabby in Pelt.pelt_dict['stripes']) + (
            "bengal",
            "rosette",
            "speckled",
        ):
            base = f"cat.pelts.{cat.pelt.tortie_base.capitalize()}_long"
        else:
            base = ""
        return base, color_name


_scar_details = [
    "NOTAIL",
    "HALFTAIL",
    "NOPAW",
    "NOLEFTEAR",
    "NORIGHTEAR",
    "NOEAR",
]

def unpack_appearance_ruleset(cat, rule, short, pelt, color):
    if rule == "scarred":
        if not short and len(cat.pelt.scars) >= 3:
            return "cat.pelts.scarred"
    elif rule == "fur_length":
        if not short and cat.pelt.length == "long":
            return "cat.pelts.long_furred"
    elif rule == "pattern":
        return pelt
    elif rule == "color":
        return color
    elif rule == "cat":
        if cat.genderalign in ("female", "trans female"):
            return "general.she-cat"
        elif cat.genderalign in ("male", "trans male"):
            return "general.tom"
        else:
            return "general.cat"
    elif rule == "vitiligo":
        if not short and cat.pelt.vitiligo:
            return "cat.pelts.vitiligo"
    elif rule == "amputation":
        if not short:
            scarlist = []
            for scar in cat.pelt.scars:
                if scar in _scar_details:
                    scarlist.append(i18n.t(f"cat.pelts.{scar}"))
            return (
                adjust_list_text(list(set(scarlist))) if len(scarlist) > 0 else ""
            )  # note: this doesn't preserve order!
    else:
        raise Exception(f"Unmatched ruleset item {rule} in describe_appearance!")
    return ""
