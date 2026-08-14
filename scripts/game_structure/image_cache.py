import pygame
from scripts.cat.sprites.load_sprites import images


class Cache:
    def __init__(self):
        self._images = {}
    
    def __getitem__(self, x):
        if x not in self._images:
            self._images[x] = images[x]
        
        return self._images[x]


image_cache = Cache()
