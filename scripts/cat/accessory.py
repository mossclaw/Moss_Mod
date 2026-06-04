from scripts.cat.save_load import load_instance, load_instance_list
from scripts.moss_util import read_resource_dict
from random import choice
from itertools import zip_longest

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
                 order:    int):
        self.name = name
        self.slot = slot
        self.event = event
        self.color = color

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
        self.sheets = [ 'acc' + s for s in sheets ]
        if isinstance(patterns, int):
            patterns = [i for i in range(1, patterns + 1)]
        elif patterns is None:
            patterns = []
        if len(patterns) < n:
            patterns += [0] * (n - len(patterns))
        self.patterns = patterns

        if order is None:
            order = AccessoryDef._accessory_data['default_order'][slot]
        self.order = order


    def __format__(self, spec):
        return self.name


    def available_colors(self, i):
        return AccessoryDef.colors[self.color[i]] if i < len(self.color) else None


    def random_colors(self):
        return AccessoryDef.__random_colors(self.color)


    def random_patterns(self):
        return AccessoryDef.__random_patterns(max(self.patterns))


    def fix(self, acc):
        n = len(self.color)
        if len(acc.color) != n:
            rand_func = AccessoryDef.__random_colors
            acc.color = acc.color[:n] + rand_func(self.color[len(acc.color):])
        for i, col in enumerate(acc.color):
            if col not in AccessoryDef.colors[self.color[i]]:
                acc.color[i] = AccessoryDef.__random_color(self.color[i])

        n = max(self.patterns)
        if len(acc.pattern) != n:
            rand_func = AccessoryDef.__random_patterns
            acc.pattern = acc.pattern[:n] + rand_func(n - len(acc.pattern))


    @staticmethod
    def __random_color(category):
        return choice(AccessoryDef.colors[category])


    @staticmethod
    def __random_colors(categories):
        return [ AccessoryDef.__random_color(x) for x in categories ]


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


        load_args = { 'slot': [],
                      'ev'  : ['opt'],
                      'col' : ['list', 'opt'],
                      'pat' : ['opt'],
                      'spr' : ['list', 'opt'],
                      'sh'  : ['list', 'opt'],
                      'ord' : ['opt'],
                      }
        entries = AccessoryDef._accessory_data['list'].items()
        AccessoryDef.available = { name: load(name, data) for name, data in entries }
        AccessoryDef.events = make_acc_dict(lambda x: x.event)
        AccessoryDef.slots  = make_acc_dict(lambda x: x.slot)

        AccessoryDef.sets = {
            key: [ x for y in tags for x in AccessoryDef.events[y] ]
            for key, tags in AccessoryDef._accessory_data['sets'].items()
        }


AccessoryDef.load_available()



class Accessory:
    @staticmethod
    def _make_name_dict(acc_dict):
        return { k: [ x.name for x in v ] for k, v in acc_dict.items() }
    _load_args = [ [], ['list', 'opt'], ['list', 'opt'] ]
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
        sets = zip_longest(self.acc.sprites, self.color, self.acc.patterns, self.acc.sheets)
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
    def create_random_from_set(set_name):
        return Accessory.create_random(AccessoryDef.sets[set_name])


    @staticmethod
    def create_random_for_event(possible, exclude_slots = []):
        if isinstance(possible, str):
            return Accessory.create_random(AccessoryDef.events[possible])

        def list_of_accs(x, lists):
            return lists[x.lower()] if x.lower() in lists else [Accessory.__lookup(x)]

        expanded = [ list_of_accs(x, AccessoryDef.events) for x in possible ]
        acc_list = [ x for y in expanded for x in y if x.slot not in exclude_slots ]
        return Accessory.create_random(acc_list) if acc_list else None


    @staticmethod
    def create_random_for_slot(slot):
        return Accessory.create_random(AccessoryDef.slots[slot])


    @staticmethod
    def create_random(available):
        if isinstance(available, list):
            available = choice(available)
        accessory = Accessory.__lookup(available)
        return Accessory(
            accessory,
            accessory.random_colors(),
            accessory.random_patterns())


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
                args = conv[acc] if acc in conv else { '*': acc }
                args['accessory'] = args['*']
                del args['*']
                accs[i] = Accessory(**args)
            elif isinstance(acc, list):
                accs[i] = Accessory.load(acc)

        convert_col_pat(data, accs[0] if len(accs) > 0 else None)

        for acc in accs:
            acc.acc.fix(acc)
