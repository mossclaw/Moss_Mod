import logging
import ujson
import json
import os
import io
import i18n

from zipfile import ZipFile, is_zipfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #


def _decode_json(path, content):
    try:
        return ujson.loads(content)
    except ujson.JSONDecodeError:
        pass
    try:
        # Use standard json for the better error messages
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"{path}: {e.msg}", e.doc, e.pos)


def _read_single_json(path, use_mods=True):
    with open(path, 'r', encoding='utf-8') as read_file:
        data = _decode_json(path, read_file.read())
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
#                            i18n extension                                    #
# ---------------------------------------------------------------------------- #

class ModdedLoader(i18n.loaders.loader.Loader):
    delegate = i18n.resource_loader.loaders['json']
    
    def __init__(self):
        super(ModdedLoader, self).__init__()
        self.delegate = ModdedLoader.delegate

    def load_resource(self, filename, root_data):
        data = self.delegate.load_resource(filename, root_data)
        mod_expand(data, filename.replace('\\', '/'), root_data)
        return data


i18n.resource_loader.register_loader(ModdedLoader, ['json'])


# ---------------------------------------------------------------------------- #
#                            Mod-mod support                                   #
# ---------------------------------------------------------------------------- #

def mod_expand(data, path, root=None):
    global mod_mods
    for mod in mod_mods:
        mod.expand(data, path, root)


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
    
    def info_path(self, path):
        return f"{self.mod_path}/{path}"
    
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
    
    def expand(self, data, path, root=None):
        modded = self.load(path)
        if root is not None and modded is not None:
            modded = modded[root] if root in modded else None
        if modded:
            logger.info(f"Expanding file {path} from mod-mod at {self.mod_path}")
            self.expand_part(data, modded)
    
    def expand_part(self, data, modded):
        if isinstance(modded, dict) and isinstance(data, dict):
            for key in modded:
                prefix = key[0] if key[0] in '-+' else ''
                data_keys = (key[1:] if prefix else key),
                if data_keys == ('#',):
                    present = set(x.strip('-+') for x in modded.keys)
                    data_keys = set(data.keys()) - present
                for data_key in data_keys:
                    if prefix != '-' and data_key in data:
                        self.expand_part(data[data_key], modded[key], prefix == '+')
                    elif prefix != '+':
                        data[data_key] = modded[key]
        elif isinstance(modded, list) and isinstance(data, list):
            add = set(modded) - set(data)
            data.extend(x for x in modded if x in add)
        else:
            pass # TODO: error message
    
    def load(self, path):
        try:
            with self.open_path(path) as read_file:
                return _decode_json(self.info_path(path), read_file.read())
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



# Load mod list
def load_mod(modlist, entry):
    path = entry.path
    if entry.is_dir():
        logger.info(f"  Folder: {path}")
        modlist.append(DirModMod(path))
    elif is_zipfile(path):
        logger.info(f"  Zip file: {path}")
        modlist.append(ZipModMod(path))

mod_mods = []
base_mod = BaseMod()
_load_order = read_json('mods/load_order.json')
_load_order_set = set(_load_order)
_load_order_present = dict()
logger.info('Finding mod-mods...')
for entry in os.scandir('mods'):
    path = entry.path
    name = path[5:].removesuffix('.zip')
    if name in _load_order_set:
        _load_order_present[name] = entry
    else:
        load_mod(mod_mods, entry)
for name in _load_order:
    if name in _load_order_present:
        load_mod(mod_mods, _load_order_present[name])
    else:
        logger.info(f"  {name} was in load_order.json, but not present in mods folder. Ignoring.")
logger.info(f"{len(mod_mods)} mod-mods found.")
del _load_order, _load_order_set, _load_order_present
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
