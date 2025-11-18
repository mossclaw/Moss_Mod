import logging
import ujson
import os
import io
from zipfile import ZipFile, is_zipfile
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #

def read_json(path, description_for_error = None, use_mods=True):
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
    return read_json(f"{subdir}/dicts/{name}.json", description_for_error, use_mods)


def read_sprite_dict(name, description_for_error = None, use_mods = True):
    return read_dict('sprites', name, description_for_error, use_mods)


def read_resource_dict(name, description_for_error = None, use_mods = True):
    return read_dict('resources', name, description_for_error, use_mods)


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
            self.expand_part(data, modded)
    
    def expand_part(self, data, modded):
        if isinstance(modded, dict) and isinstance(data, dict):
            for key in modded:
                if key in data:
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
        self.mod_path = path
        self.len = len(path) + 1
    
    def real_path(self, path):
        return f"{self.mod_path}/{path}"
    
    def virtual_path(self, path):
        return path[self.len:]

class ZipModMod(ModMod):
    def __init__(self, path):
        self.zip_path = path
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
            elif is_zipfile(path):
                mod_mods.append(ZipModMod(path))
        except:
            raise
            pass
except:
    raise
    pass
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
