
class Chronicle:
    per_cat = {}
    
    @staticmethod
    def reset():
        Chronicle.per_cat.clear()
    
    @staticmethod
    def handle_event(event):
        for cat in event.cats_involved:
            chronicle = Chronicle.per_cat.get(cat)
            if chronicle:
                chronicle.log(event)
    
    def __init__(self, cat_id, game):
        self.events = []
        self.cat_id = cat_id
        self.game = game
        Chronicle.per_cat[cat_id] = self
    
    def log(self, event):
        self.events.append((self.game.clan.age, event.text))
