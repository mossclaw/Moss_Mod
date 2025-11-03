from scripts.cat.save_load import load_instance
from scripts.temp_util import read_resource_dict
from random import choice

class AccessoryDef:
    _accessory_data = read_resource_dict('accessories')
    colors = _accessory_data['colors']
    patterns = _accessory_data['patterns']

    def __init__(self,
                 name:     str,
                 slot:     str,
                 event:    str,
                 color:    list[str],
                 patterns: int):
        self.name = name
        self.slot = slot
        self.event = event
        self.color = color
        self.patterns = patterns


    def random_colors(self):
        return [ choice(AccessoryDef.colors[x]) for x in self.color ]


    def random_patterns(self):
        return [ choice(AccessoryDef.patterns) for x in range(1, self.patterns) ]


    @staticmethod
    def load_available():
        def load(name, data):
            result = load_instance(data, AccessoryDef, load_args, [ name ])
            if result.patterns is None:
                result.patterns = 0
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
    _load_args = { 'name':    [],
                   'color':   ['list'],
                   'pattern': ['list'],
                 }

    def __init__(self,
                 accessory,
                 color: list[str],
                 pattern: list[str]):
        self.accessory = Accessory._lookup(accessory)
        self.color = color
        self.pattern = pattern


    @staticmethod
    def _lookup(accessory):
        if type(accessory) is str:
            accessory = AccessoryDef.available[accessory]
        return accessory


    @property
    def name(self):
        return self.accessory.name


    @staticmethod
    def create_random_from_set(set_name):
        return Accessory.create_random(AccessoryDef.sets[set_name])


    @staticmethod
    def create_random_for_event(possible, exclude_slots = []):
        if type(possible) is str:
            Accessory.create_random(AccessoryDef.events[possible])
        lists = AccessoryDef.events
        def list_of_accs(name):
            low = lower(name)
            return lists[lower(x)] if lower(x) in lists else [Accessory._lookup(x)]

        expanded = [ list_of_accs(x) for x in possible_accs ]
        acc_list = [ x for y in expanded for x in y if x.slot not in exclude_slots ]
        return Accessory.create_random(acc_list) if acc_list else None


    @staticmethod
    def create_random_for_slot(slot):
        return Accessory.create_random(AccessoryDef.slots[slot])


    @staticmethod
    def create_random(available):
        if type(available) is list:
            available = choice(available)
        accessory = Accessory._lookup(available)
        return Accessory(
            accessory,
            accessory.random_colors(),
            accessory.random_patterns())


    @staticmethod
    def load(data: dict):
        return load_instance(data, Accessory, _load_args)


    @staticmethod
    def load_legacy(cat_data: dict):
        if 'accessory' not in cat_data:
            return None

        name = cat_data['accessory']
        color = [ cat_data['accessory_color'] ]
        if 'accessory_color2' in cat_data:
            color.append(cat_data['accessory_color2'])
        pattern = [ cat_data['accessory_pattern'] ]
        if 'accessory_pattern2' in cat_data:
            pattern.append(cat_data['accessory_pattern2'])

        # TODO: Probably need more legacy stuff here...

        return Accessory(name, color, pattern)
