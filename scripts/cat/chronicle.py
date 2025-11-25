import i18n

from scripts.game_structure.game.save_load import safe_save
from scripts.moss_util import read_json


class Chronicle:
    per_cat = {}
    remove_suffixes = [
        "relationships.positive_postscript",
        "relationships.positive_postscript_low",
        "relationships.positive_postscript_medium",
        "relationships.positive_postscript_high",
        "relationships.negative_postscript",
        "relationships.negative_postscript_low",
        "relationships.negative_postscript_medium",
        "relationships.negative_postscript_high",
        "relationships.neutral_postscript",
    ]
    
    @staticmethod
    def reset():
        Chronicle.per_cat.clear()
    
    @staticmethod
    def handle_event(event):
        text = None
        for cat in event.cats_involved:
            if not text:
                text = event.text
                for remove in Chronicle.remove_suffixes:
                    text = text.removesuffix(i18n.t(remove))
            chronicle = Chronicle.per_cat.get(cat)
            if chronicle:
                chronicle.log(text)
    
    def __init__(self, cat_id, game):
        self.events = []
        self.cat_id = cat_id
        self.game = game
        Chronicle.per_cat[cat_id] = self
    
    def __save_path(self, save_dir):
        return save_dir / f"{self.cat_id}.json"
    
    def log(self, text):
        self.events.append((self.game.clan.age, text))
    
    def load(self, save_dir):
        self.events = read_json(self.__save_path(save_dir), use_mods= False)
        if self.events:
            for i in range(len(self.events)):
                self.events[i] = tuple(self.events[i])
        else:
            self.events = []
        print(repr(self.events))
    
    def save(self, save_dir):
        safe_save(self.__save_path(save_dir), self.events, indent= 0)
    
    def delete(self, save_dir):
        self.__save_path(save_dir).unlink(missing_ok= True)
            
