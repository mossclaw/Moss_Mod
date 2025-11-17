import logging
import ujson
import os
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #

def read_json(path, description_for_error = None, use_mods = True):
    try:
        with open(path, 'r', encoding='utf-8') as read_file:
            data = ujson.loads(read_file.read())
            if use_mods:
                mod_expand(data, path)
            return data
    except IOError:
        if description_for_error is not None:
            raise Exception(f"Failed to read {description_for_error} from {path}.")
            logger.error(f"Failed to read {description_for_error}.")
        return {}


def read_dict(subdir, name, description_for_error = None, use_mods = True):
    return read_json(f"{subdir}/dicts/{name}.json", description_for_error)


def read_sprite_dict(name, description_for_error = None):
    return read_dict('sprites', name, description_for_error)


def read_resource_dict(name, description_for_error = None):
    return read_dict('resources', name, description_for_error)


# ---------------------------------------------------------------------------- #
#                            Mod-mod support                                   #
# ---------------------------------------------------------------------------- #

def mod_expand(data, path):
    global mods
    for mod in mods:
        mod.expand(data, path)


class ModMod():
    def load(self, path):
        return None
    
    def expand(self, data, path):
        modded = self.load(path)
        if modded:
            self.expand_part(data, modded)
    
    def expand_part(self, data, modded):
        if isinstance(modded, dict) and isinstance(data, dict):
            for key in modded:
                if key in data:
                    self.expand_part(data[key], modded[key])
                else:
                    data[key] = modded[key]
        elif isinstance(modded, list) and isinstance(data, list):
            data.expand(set(modded) - set(data))
        else:
            pass # TODO: error message


class DirModMod(ModMod):
    def __init__(self, path):
        self.mod_path = path
        self.sprite_path = path + '/sprites'
        self.sprite_config = read_dict(self.sprite_path, 'sprites', use_mods= False)
    
    def load(self, path):
        try:
            with open(f"{self.mod_path}/{path}", 'r', encoding='utf-8') as read_file:
                return ujson.loads(read_file.read())
        except IOError:
            return None


# Load mod list
mods = []
try:
    for entry in os.scandir('mods'):
        try:
            if entry.is_dir():
                mods.append(DirModMod(entry.path))
        except:
            pass
except:
    pass


# ---------------------------------------------------------------------------- #
#                            Collection Utilities                              #
# ---------------------------------------------------------------------------- #


def union_of_entries(dict_of_lists):
    return sorted({ x for y in dict_of_lists.values() for x in y })


def reverse_dict(dict_of_lists):
    return { item: key for key, items in dict_of_lists.items() for item in items }


class OnUpdateList(list):
    def __init__(self, update, convert, elems):
        list.__init__(self, elems)
        self.update = update
        self.convert = convert

    def append(self, elem):
        if self.convert is not None:
            elem = (self.convert)(elem)
        list.append(self, elem)
        (self.update)()
