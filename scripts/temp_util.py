import logging
import ujson
import os
import io
from zipfile import ZipFile
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #

def read_json(path, description_for_error = None):
    try:
        with open(path, 'r', encoding='utf-8') as read_file:
            data = ujson.loads(read_file.read())
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
    global mod_mods
    for mod in mod_mods:
        mod.expand(data, path)


class ModMod():
    def real_path(self, path):
        return path
    
    def open_path(self, path, text=True):
        path = self.real_path(path)
        if text:
            return open(path, encoding='utf-8')
        else:
            return open(path, 'rb')
    
    def scan_dir(self, path):
        return os.scandir(self.real_path(path))
    
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
    
    def load(self, path):
        try:
            with self.open_path(path) as read_file:
                return ujson.loads(read_file.read())
        except IOError | KeyError:
            return None


class DirModMod(ModMod):
    def __init__(self, path):
        self.mod_path = path
    
    def real_path(self, path):
        return f"{self.mod_path}/{path}"


class ZipModMod(ModMod):
    def __init__(self, path):
        self.zip_path = path
        self.zip = ZipFile(path)
        self.fs = self.build_fs()
    
    def build_fs(self):
        files = self.zip.infolist()
        fs = {'': []}
        for file in files:
            parts = file.filename.split('/')
            file.path = file.filename
            file.name = parts[-1]
            
            base = prev = ''
            for part in parts[:-1]:
                prev = base
                base += part + '/'
                if base not in fs:
                    fs[base] = []
            fs[base if file.name else prev].append(file)
        return fs

    def open_path(self, path, text=True):
        file = self.zip.open(path)
        if text:
            file = io.TextIOWrapper(file, encoding='utf-8')
        return file
    
    def scan_dir(self, path):
        if path[-1] != '/':
            path += '/'
        return self.fs[path] if path in self.fs else []


class BaseMod(ModMod):
    pass



# Load mod list
mod_mods = []
base_mod = BaseMod()
try:
    for entry in os.scandir('mods'):
        try:
            path = entry.path
            if entry.is_dir():
                mod_mods.append(DirModMod(path))
            elif entry.is_file() and zipfile.is_zipfile(path):
                mod_mods.append(ZipModMod(path))
        except:
            pass
except:
    pass
all_mods = [base_mod] + mod_mods


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
