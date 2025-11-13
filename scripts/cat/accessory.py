from scripts.cat.save_load import load_instance, load_instance_list
from scripts.temp_util import read_resource_dict
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
                 patterns: int,
                 sprites:  list,
                 sheets:   list):
        self.name = name
        self.slot = slot
        self.event = event
        self.color = color
        self.patterns = patterns or 0

        n = max(len(color), self.patterns, len(sheets), len(sprites), 1)
        self.sprites = [ s if s else name for s in sprites ]
        if len(sprites) < n:
            self.sprites += [name] * (n - len(sprites))
        if len(sheets) < n:
            if color or n > 1:
                sheets = ['base'] * (n - len(sheets)) + sheets
            else:
                sheets = ['']
        self.sheets = [ 'acc' + s for s in sheets ]


    def __format__(self, spec):
        return self.name


    def random_colors(self):
        return AccessoryDef.__random_colors(self.color)


    def random_patterns(self):
        return AccessoryDef.__random_patterns(self.patterns)


    def fix(self, acc):
        n = len(self.color)
        if len(acc.color) != n:
            rand_func = AccessoryDef.__random_colors
            acc.color = acc.color[:n] + rand_func(self.color[len(acc.color):])
        for i, col in enumerate(acc.color):
            if col not in AccessoryDef.colors[self.color[i]]:
                acc.color[i] = AccessoryDef.__random_color(self.color[i])

        n = self.patterns
        if len(acc.pattern) != n:
            rand_func = AccessoryDef.__random_patterns
            acc.pattern = acc.pattern[:n] + rand_func(n - self.patterns)


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
    _load_args = [ [], ['list', 'opt'], ['list', 'opt'] ]

    def __init__(self,
                 accessory,
                 color: list[str] = [],
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
        sets = zip_longest(self.acc.sprites, self.color, self.pattern, self.acc.sheets)
        for sprite, color, pattern, sheet in sets:
            render.set(sprite= sprite, color= color)
            if color is None:
                render.paint(sheet)
            else:
                render.add_layer(sheet)
                render.paint(sheet, 0)
                if pattern is not None:
                    render.add_layer('accpattern', sprite= pattern)
                    render.paint('accpattern', sprite= pattern, blend= 'mult')
                    render.paint(sheet, blend= 'alpha')
                    render.merge_layer()
                render.merge_layer()


    @staticmethod
    def __lookup(accessory):
        if isinstance(accessory, str):
            accessory = AccessoryDef.available[accessory]
        return accessory


    @staticmethod
    def create_random_from_set(set_name):
        return Accessory.create_random(AccessoryDef.sets[set_name])


    @staticmethod
    def create_random_for_event(possible, exclude_slots = []):
        if isinstance(possible, str):
            Accessory.create_random(AccessoryDef.events[possible])

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
        if 'accessory' not in data:
            return
        accs = data['accessory']
        if not accs:
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

        if len(accs) > 0:
            acc = accs[0]
            if 'accessory_color' in data:
                acc.color = [ data['accessory_color'] ]
                if 'accessory_color2' in cat_data:
                    acc.color.append(cat_data['accessory_color2'])
            if 'accessory_pattern' in data:
                acc.pattern = [ data['accessory_pattern'] ]
                if 'accessory_pattern2' in cat_data:
                    acc.pattern.append(cat_data['accessory_pattern2'])

        for acc in accs:
            acc.acc.fix(acc)
