import logging
import ujson
import os
import io
from zipfile import ZipFile, is_zipfile
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #


def _read_single_json(path, use_mods=True):
    with open(path, 'r', encoding='utf-8') as read_file:
        data = ujson.loads(read_file.read())
        if use_mods:
            mod_expand(data, path)
        return data
    

def read_json(path, description_for_error = None, use_mods=True, exception=False, fallback=None):
    def error(description_for_error):
        if description_for_error is not None:
            logger.error(f"Failed to read {description_for_error}.")
        
    try:
        return _read_single_json(path, use_mods)
    except FileNotFoundError:
        if fallback:
            return _read_single_json(fallback, use_mods)
        elif exception:
            raise
    except IOError:
        if exception:
            raise
    error(description_for_error)
    return {}


def read_dict(subdir, name, description_for_error = None, use_mods = True, exception=False):
    return read_json(f"{subdir}/dicts/{name}.json", description_for_error, use_mods, exception)


def read_sprite_dict(name, description_for_error = None, use_mods = True, exception=False):
    return read_dict('sprites', name, description_for_error, use_mods, exception)


def read_resource_dict(name, description_for_error = None, use_mods = True, exception=False):
    return read_dict('resources', name, description_for_error, use_mods, exception)


# ---------------------------------------------------------------------------- #
#                            Mod-mod support                                   #
# ---------------------------------------------------------------------------- #

def mod_expand(data, path):
    global mod_mods
    for mod in mod_mods:
        mod.expand(data, path)


class _DirEntry:
    def __init__(self, path, is_dir):
        self.path = path.replace('\\', '/')
        self.parts = self.path.split('/')
        self.name = self.parts[-1] if self.parts[-1] else self.parts[-2]
        self.is_dir = is_dir


class ModMod():
    def __init__(self, path):
        self.mod_path = path
    
    def real_path(self, path):
        return path
    
    def virtual_path(self, path):
        return path
    
    def open_path(self, path, text=True):
        path = self.real_path(path)
        if text:
            return open(path, encoding='utf-8')
        else:
            return open(path, 'rb')
    
    def scan_dir(self, path):
        try:
            return [ _DirEntry(self.virtual_path(x.path), x.is_dir()) 
                     for x in os.scandir(self.real_path(path)) ]
        except:
            return []
    
    def expand(self, data, path):
        modded = self.load(path)
        if modded:
            print(f"Expanding file {path} from mod-mod at {self.mod_path}")
            self.expand_part(data, modded)
    
    def expand_part(self, data, modded):
        if isinstance(modded, dict) and isinstance(data, dict):
            for key in modded:
                replace = key[0] == '-'
                if replace:
                    key = key[1:]
                
                if not replace and key in data:
                    self.expand_part(data[key], modded[key])
                else:
                    data[key] = modded[key]
        elif isinstance(modded, list) and isinstance(data, list):
            data.extend(set(modded) - set(data))
        else:
            pass # TODO: error message
    
    def load(self, path):
        try:
            with self.open_path(path) as read_file:
                return ujson.loads(read_file.read())
        except (IOError, KeyError):
            return None


class DirModMod(ModMod):
    def __init__(self, path):
        ModMod.__init__(self, path)
        self.len = len(path) + 1
    
    def real_path(self, path):
        return f"{self.mod_path}/{path}"
    
    def virtual_path(self, path):
        return path[self.len:]

class ZipModMod(ModMod):
    def __init__(self, path):
        ModMod.__init__(self, path)
        self.zip = ZipFile(path)
        self.fs = self.build_fs()
    
    def build_fs(self):
        files = self.zip.infolist()
        fs = {'': []}
        for file in files:
            file = _DirEntry(file.filename, file.is_dir())
            base = prev = ''
            for part in file.parts[:-1]:
                prev = base
                base += part + '/'
                if base not in fs:
                    fs[base] = []
            fs[prev if file.is_dir else base].append(file)
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
    def __init__(self):
        ModMod.__init__(self, 'BASE')


def load_mod(modlist, entry):
    path = entry.path
    
    if entry.is_dir():
        print(f"  Folder: {path}")
        modlist.append(DirModMod(path))
    elif is_zipfile(path):
        print(f"  Zip file: {path}")
        modlist.append(ZipModMod(path))



# Load mod list
mod_mods = []
base_mod = BaseMod()
load_order = read_json('mods/load_order.json')
load_order_set = set(load_order)
load_order_present = dict()
print('Finding mod-mods...')
for entry in os.scandir('mods'):
    path = entry.path
    name = path[5:].removesuffix('.zip')
    if name in load_order_set:
        load_order_present[name] = entry
    else:
        load_mod(mod_mods, entry)
for name in load_order:
    if name in load_order_present:
        load_mod(mod_mods, load_order_present[name])
    else:
        print(f"  {name} was in load_order.json, but not present in mods folder. Ignoring.")
print(f"{len(mod_mods)} mod-mods found.")
all_mods = [base_mod] + mod_mods


# ---------------------------------------------------------------------------- #
#                            Utility classes                                   #
# ---------------------------------------------------------------------------- #

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
