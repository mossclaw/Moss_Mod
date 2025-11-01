from scripts.cat.save_load import load_instance

class Accessory:
    LOAD_ARGS = { 'name':    [],
                  'color':   ['list'],
                  'pattern': ['list'],
                  'slot':    ['opt'],
                  'tag':     ['opt'],
                }
    
    def __init__(self, 
                 name: str, 
                 color: [str], 
                 pattern: [str], 
                 slot: str = None,
                 tag: str = None):
        self.name = name
        self.color = color
        self.pattern = pattern
        self.slot = slot
        self.parent = None
    
    
    @staticmethod
    def load(data: dict):
        return load_instance(data, Accessory, LOAD_ARGS)
    
    
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
