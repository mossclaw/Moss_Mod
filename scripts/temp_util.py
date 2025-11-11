import logging
import ujson
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                            Loading json files                                #
# ---------------------------------------------------------------------------- #


def read_json(path, description_for_error = None):
    try:
        with open(path, 'r', encoding="utf-8") as read_file:
            return ujson.loads(read_file.read())
    except IOError:
        if description_for_error is not None:
            raise Exception(f"Failed to read {description_for_error} from {path}.")
            logger.error(f"Failed to read {description_for_error}.")
        return {}


def read_dict(subdir, name, description_for_error = None):
    return read_json(f"{subdir}/dicts/{name}.json", description_for_error)


def read_sprite_dict(name, description_for_error = None):
    return read_dict('sprites', name, description_for_error)


def read_resource_dict(name, description_for_error = None):
    return read_dict('resources', name, description_for_error)


# ---------------------------------------------------------------------------- #
#                            Collection Utilities                              #
# ---------------------------------------------------------------------------- #


def union_of_entries(dict_of_lists):
    return sorted({ x for y in dict_of_lists.values() for x in y })


def reverse_dict(dict_of_lists):
    return { item: key for key, items in dict_of_lists.items() for item in items }


class OnUpdateList(list):
    def __init__(self, func, convert, elems):
        list.__init__(self, elems)
        self.func = func
        self.convert = convert

    def append(self, elem):
        if self.convert is not None:
            elem = (self.convert)(elem)
        list.append(self, elem)
        (self.func)()
