from scripts.cat.save_load import load_instance, load_instance_list
from scripts.moss_util import read_resource_dict, add_function_mod
from random import choice
from itertools import zip_longest, product


def _set_fixed(rand, fixed):
    if fixed is None:
        return rand
    if isinstance(fixed, list):
        return [ r if f is None else f for r, f in zip_longest(rand, fixed[:len(rand)]) ]
    if len(rand) >= 1:
        rand[0] = fixed
    return rand


def _combine_function_mod(data, path, root):
    if not path == f"resources/lang/{root}/cat/accessories.{root}.json":
        return
    
    for key, accessories in _combinations.items():
        for name, parts in accessories.items():
            part_dicts = [ data[key] for key in parts if key in data ]
            if (name not in data 
                    and 'combined' in data 
                    and key in data['combined']):
                combine_dict = data['combined'][key]
                data[name] = translation_dict = {}
                for plural_key, fmt in combine_dict.items():
                    strings = [ part[plural_key] for part in part_dicts ]
                    value = fmt.format(*strings)
                    translation_dict[plural_key] = value

add_function_mod(_combine_function_mod)
_combinations = {}


class AccessoryDef:
    _accessory_data = read_resource_dict('accessories')
    colors = _accessory_data['colors']
    patterns = _accessory_data['patterns']

    def __init__(self,
                 name:     str,
                 slot:     str,
                 event:    str,
                 color:    list[str],
                 patterns,
                 sprites:  list,
                 sheets:   list,
                 order:    int,
                 combine:  dict):
        self.name = name
        self.slot = slot
        self.event = event

        n_pat = patterns if isinstance(patterns, int) else len(patterns or [])
        n = max(len(color), n_pat, len(sheets), len(sprites), 1)
        self.sprites = [ s if s else name for s in sprites ]
        if len(sprites) < n:
            self.sprites += [name] * (n - len(sprites))
        if len(sheets) < n:
            if color or n > 1:
                sheets = ['base'] * (n - len(sheets)) + sheets
            else:
                sheets = ['']
        self.sheets = [ s if s.startswith('acc') else 'acc' + s for s in sheets ]
        if isinstance(patterns, int):
            patterns = [i for i in range(1, patterns + 1)]
        elif patterns is None:
            patterns = []
        if len(patterns) < n:
            patterns += [0] * (n - len(patterns))
        self.patterns = patterns
        
        if len(color) < n:
            color += [None] * (n - len(color))
        self.color_expanded = color
        self.color = [ x for x in color if x is not None ]

        if order is None and slot is not None:
            order = AccessoryDef._accessory_data['default_order'][slot]
        self.order = order
        
        if combine is not None:
            for key, val in combine.items():
                if isinstance(val, int):
                    combine[key] = { 'part': val }
        self.combine = combine


    def __format__(self, spec):
        return self.name


    def available_colors(self, i):
        return AccessoryDef.colors[self.color[i]] if i < len(self.color) else None


    def random_colors(self, fixed= None):
        return _set_fixed(AccessoryDef.__random_colors(self.color), fixed)


    def random_patterns(self, fixed= None):
        return _set_fixed(AccessoryDef.__random_patterns(max(self.patterns)), fixed)
    
    
    class __ColorIter:
        def __init__(self, expanded, condensed):
            self.expanded = expanded
            self.condensed = condensed
        
        def __iter__(self):
            self.e_it = iter(self.expanded)
            self.c_it = iter(self.condensed)
            return self
        
        def __next__(self):
            return None if next(self.e_it) is None else next(self.c_it)

    
    def color_for_render(self, color):
        return AccessoryDef.__ColorIter(self.color_expanded, color)


    def fix(self, acc):
        n = len(self.color)
        if len(acc.color) != n:
            rand_func = AccessoryDef.__random_colors
            acc.color = acc.color[:n] + rand_func(self.color[len(acc.color):])
        for i, col in enumerate(acc.color):
            if self.color[i] is not None and col not in AccessoryDef.colors[self.color[i]]:
                acc.color[i] = AccessoryDef.__random_color(self.color[i])

        n = max(self.patterns)
        if len(acc.pattern) != n:
            rand_func = AccessoryDef.__random_patterns
            acc.pattern = acc.pattern[:n] + rand_func(n - len(acc.pattern))


    @staticmethod
    def __combine(key, *parts):
        def extract(key, part, value, new, tag, is_set):
            if not is_set:
                if tag in part.combine[key]:
                    is_set = True
                    value = part.combine[key][tag]
                elif value is None:
                    value = new
            return (value, is_set)
        
        exclude = set()
        for part in parts:
            if 'exclude' in part.combine[key]:
                exclude.update(part.combine[key]['exclude'])

        slot_set  = False
        event_set = False
        order_set = False
        name     = None
        slot     = None
        event    = None
        order    = None
        color    = []
        patterns = []
        sprites  = []
        sheets   = []
        
        for part in parts:
            if part.name in exclude:
                return None
            name = part.name if name is None else name + '+' + part.name
            slot,  slot_set  = extract(key, part, slot,  part.slot,  'slot', slot_set)
            event, event_set = extract(key, part, event, part.event, 'ev',   event_set)
            order, order_set = extract(key, part, order, part.order, 'ord',  order_set)
            color   .extend(part.color_expanded)
            patterns.extend(part.patterns)
            sprites .extend(part.sprites)
            sheets  .extend(part.sheets)
        
        _combinations.setdefault(key, {})[name] = [ part.name for part in parts ]
        
        return AccessoryDef(name, slot, event, color, patterns, sprites, sheets, order, None)


    @staticmethod
    def __random_color(category):
        return choice(AccessoryDef.colors[category])


    @staticmethod
    def __random_colors(categories):
        return [ None if x is None else AccessoryDef.__random_color(x) for x in categories ]


    @staticmethod
    def __random_patterns(n):
        return [ choice(AccessoryDef.patterns) for x in range(0, n) ]


    @staticmethod
    def load_available():
        def load(name, data):
            result = load_instance(data, AccessoryDef, load_args, [ name ])
            return result

        def make_acc_dict(get_key):
            acc_dict = dict()
            for acc in AccessoryDef.available.values():
                key = get_key(acc)
                if key is not None:
                    if key not in acc_dict:
                        acc_dict[key] = []
                    acc_dict[key].append(acc)
            return acc_dict
        
        def make_combinations(available):
            combinations = {}
            for part in available.values():
                if part.combine is not None:
                    for key, val in part.combine.items():
                        i = val['part'] - 1
                        if key not in combinations:
                            combinations[key] = []
                        while i >= len(combinations[key]):
                            combinations[key].append([])
                        combinations[key][i].append(part)
            for key, lists in combinations.items():
                for parts in product(*lists):
                    acc = AccessoryDef.__combine(key, *parts)
                    if acc is not None:
                        available[acc.name] = acc
        
        def remove_no_slot(available):
            for name in tuple(available):
                if available[name].slot is None:
                    del available[name]


        load_args = { 'slot': [],
                      'ev'  : ['opt'],
                      'col' : ['list', 'opt'],
                      'pat' : ['opt'],
                      'spr' : ['list', 'opt'],
                      'sh'  : ['list', 'opt'],
                      'ord' : ['opt'],
                      'comb': ['opt'],
                      }
        entries = AccessoryDef._accessory_data['list'].items()
        AccessoryDef.available = { name: load(name, data) for name, data in entries }
        make_combinations(AccessoryDef.available)
        remove_no_slot(AccessoryDef.available)
        AccessoryDef.events = make_acc_dict(lambda x: x.event)
        AccessoryDef.slots  = make_acc_dict(lambda x: x.slot)

        AccessoryDef.sets = {
            key: [ x for y in tags for x in AccessoryDef.events[y] ]
            for key, tags in AccessoryDef._accessory_data['sets'].items()
        }


AccessoryDef.load_available()



class Accessory:
    _load_args = [ [], ['list', 'opt'], ['list', 'opt'] ]
    
    @staticmethod
    def _make_name_dict(acc_dict):
        return { k: [ x.name for x in v ] for k, v in acc_dict.items() }
    names_by_slot  = _make_name_dict(AccessoryDef.slots)
    names_by_event = _make_name_dict(AccessoryDef.events)
    del _make_name_dict


    def __init__(self,
                 accessory,
                 color:   list[str] = [],
                 pattern: list[str] = []):
        self.acc = Accessory.__lookup(accessory)
        self.color = color
        self.pattern = pattern


    @property
    def name(self):
        return self.acc.name


    @property
    def slot(self):
        return self.acc.slot


    @property
    def event(self):
        return self.acc.event


    @property
    def order(self):
        return self.acc.order


    def get_save(self):
        def single(val):
            return val[0] if len(val) == 1 else val
        if self.pattern:
            return [self.name, single(self.color), single(self.pattern)]
        elif self.color:
            return [self.name, single(self.color)]
        else:
            return self.name


    def render(self, render):
        render.set(colormap= 'accessory', sprite= self.name)
        sets = zip_longest(self.acc.sprites, 
                           self.acc.color_for_render(self.color), 
                           self.acc.patterns, 
                           self.acc.sheets)
        for sprite, color, pattern, sheet in sets:
            render.set(sprite= sprite, color= color)
            if color is None:
                render.paint(sheet)
            else:
                render.add_layer(sheet)
                render.paint(sheet, 0)
                if pattern > 0:
                    pattern = self.pattern[pattern - 1]
                    render.add_layer('accpattern', sprite= pattern)
                    render.paint('accpattern', sprite= pattern, blend= 'mult')
                    render.paint(sheet, blend= 'alpha')
                    render.merge_layer()
                render.merge_layer()


    @staticmethod
    def __lookup(accessory):
        if isinstance(accessory, str):
            if accessory in AccessoryDef.available:
                accessory = AccessoryDef.available[accessory]
            else:
                raise ValueError(f"No accessory named {accessory}.")
        return accessory


    @staticmethod
    def __slot(accessory):
        if isinstance(accessory, dict):
            accessory = accessory['*']
        return Accessory.__lookup(accessory)


    @staticmethod
    def create_random_from_set(set_name):
        return Accessory.create_random(AccessoryDef.sets[set_name])


    @staticmethod
    def create_random_for_event(possible, exclude_slots = []):
        if isinstance(possible, str):
            return Accessory.create_random(AccessoryDef.events[possible])

        def list_of_accs(x, lists):
            if isinstance(x, str) and x.lower() in lists:
                return lists[x.lower()]
            else:
                return [x]

        expanded = [ list_of_accs(x, AccessoryDef.events) for x in possible ]
        acc_list = [ x for y in expanded for x in y if Accessory.__slot(x) not in exclude_slots ]
        return Accessory.create_random(acc_list) if acc_list else None


    @staticmethod
    def create_random_for_slot(slot):
        return Accessory.create_random(AccessoryDef.slots[slot])


    @staticmethod
    def create_random(available):
        if isinstance(available, list):
            accessory = choice(available)
        else:
            accessory = available
        if isinstance(accessory, dict):
            color   = accessory['col'] if 'col' in accessory else None
            pattern = accessory['pat'] if 'pat' in accessory else None
            accessory = accessory['*']
        else:
            (color, pattern) = (None, None)
        accessory = Accessory.__lookup(accessory)
        return Accessory(
            accessory,
            accessory.random_colors(color),
            accessory.random_patterns(pattern))


    @staticmethod
    def load(data):
        if isinstance(data, Accessory):
            return data
        if isinstance(data, str):
            return Accessory.create_random(data)
        return load_instance_list(data, Accessory, Accessory._load_args)


    @staticmethod
    def load_all(data, conv):
        def convert_one(data, acc, key, attr, append):
            if key in data:
                if acc is not None:
                    if append:
                        getattr(acc, attr).append(data[key])
                    else:
                        setattr(acc, attr, [data[key]])
                del data[key]

        def convert_col_pat(data, acc=None):
            convert_one(data, acc, 'accessory_color',    'color',   False)
            convert_one(data, acc, 'accessory_color2',   'color',   True)
            convert_one(data, acc, 'accessory_pattern',  'pattern', False)
            convert_one(data, acc, 'accessory_pattern2', 'pattern', True)
        
        def from_convert(conv):
            conv = { ('accessory' if k == '*' else k): v for k,v in conv.items() }
            return Accessory(**conv)

        if 'accessory' not in data:
            return
        accs = data['accessory']
        if not accs:
            convert_col_pat(data)
            return

        if isinstance(accs, str):
            data['accessory'] = accs = [ accs ]

        for i, acc in enumerate(accs):
            if isinstance(acc, str):
                if acc in conv:
                    accs[i] = from_convert(conv[acc])
                else:
                    accs[i] = Accessory(acc)
            elif isinstance(acc, list):
                if acc[0] in conv:
                    acc_conv = conv[acc[0]]
                    if len(acc_conv) == 1:
                        acc[0] = acc_conv['*']
                        accs[i] = Accessory.load(acc)
                    else:
                        accs[i] = from_convert(acc_conv)
                else:
                    accs[i] = Accessory.load(acc)

        convert_col_pat(data, accs[0] if len(accs) > 0 else None)

        for acc in accs:
            acc.acc.fix(acc)
