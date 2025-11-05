import pygame
from scripts.temp_util import read_resource_dict
from scripts.cat.sprites.load_sprites import sprites


class Render:
    _create_flags = pygame.HWSURFACE | pygame.SRCALPHA
    _blend = { None : 0,
              'mult': pygame.BLEND_RGB_MULT,
              'add' : pygame.BLEND_RGB_ADD,
              'min' : pygame.BLEND_RGB_MIN,
             }
    colors = read_resource_dict('colors')

    def __init__(self, pose, size=None, flip=False, only_load=False):
        if size is None:
            size = sprites.size
        if type(size) is int or type(size) is float:
            size = (size, size)
        self.pose = str(pose)
        self.only_load = only_load
        self.size = size
        self.flip = flip
        self.colormap = None
        self.color = None
        self.sprite = None
        self.stack = []
        self.add_layer()


    @property
    def image(self):
        if len(self.stack) > 1:
            raise RuntimeError('merge_layer must be called as many times as add_layer.')
        if self.flip:
            return pygame.transform.flip(self.stack[0], True, False)
        else:
            return self.stack[0]


    def set(self, colormap=None, color=None, sprite=None):
        if colormap is not None:
            self.colormap = colormap
        if color is not None:
            self.color = color
        if sprite is not None:
            self.sprite = sprite
        return self


    def paint(self, sheet=None, index=None, colormap=None, color=None, sprite=None, blend=None):
        if self.only_load:
            self.__load_only(sheet, sprite)
        elif sheet is None:
            self.__tint(self.stack[-1], colormap, color, index, blend)
        else:
            image = self.__load(sheet, sprite)
            self.__tint(image, colormap, color, index)
            self.__merge(image, blend)
        return self


    def paint_all(self, *operations):
        for operation in operations:
            if type(operation) is dict:
                self.paint(**operation)
            else:
                self.paint(*operation)
        return self


    def add_layer(self, sheet=None, sprite=None, insert=False):
        if self.only_load:
            self.__load_only(sheet, sprite)
        else:
            if sheet is None:
                image = pygame.Surface(self.size, Render._create_flags)
            else:
                image = self.__load(sheet, sprite)
            if insert:
                self.stack[-1:] = [image, self.stack[-1]]
            else:
                self.stack.append(image)
        return self


    def merge_layer(self, blend=None):
        if not self.only_load:
            self.__merge(self.stack.pop(), blend)
        return self


    def __merge(self, image, blend, target=None):
        if target is None:
            target = self.stack[-1]
        target.blit(image, (0, 0), special_flags=Render._blend[blend])


    def __tint(self, image, colormap, color, index, blend=None):
        if index is None:
            return
        if colormap is None:
            colormap = self.colormap
        if color is None:
            color = self.color
        if colormap is None or color is None:
            raise ValueError(
                'Both colormap and color must be set or passed to paint when index != None.')

        tint = pygame.Surface(self.size).convert_alpha()
        tint.fill(Render.colors[colormap][color][index])
        self.__merge(tint, blend or 'mult', image)


    def __load(self, sheet, sprite=None):
        return self.__load_only(sheet, sprite).copy().convert_alpha()


    def __load_only(self, sheet, sprite=None):
        if sprite is None:
            sprite = self.sprite
        if sprite is None:
            raise ValueError('sprite must be set or passed to paint.')
        return sprites[sheet + sprite.upper() + self.pose]
