import pygame
from scripts.temp_util import read_resource_dict
from scripts.cat.sprites import sprites

class RenderStep:
    def __init__(self, order, source, index, size, sprite, color, extra):
        self.order = order
        self.source = source
        self.index = index

        self.size = size
        self.sprite = sprite
        self.color = color
        self.extra = extra


    def __lt__(self, other):
        if order != other.order:
            return order < other.order
        if source != other.source:
            return source < other.source
        return index < other.index


    def render(self, stack):
        layer = self.sprite.copy().convert_alpha()
        if self.color is not None:
            tint = pygame.Surface(self.size).convert_alpha()
            tint.fill(self.color)
            layer.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if 'push' in extra:
            stack.append(layer)
        else:
            flag = pygame.BLEND_RGB_MULT if 'blend' in extra else None
            stack[-1].blit(layer, (0, 0), special_flags=flag)
        if 'pop' in extra:
            layer = stack.pop()
            stack[-1].blit(layer, (0, 0))


def interpret_render(obj, elem):
    if type(elem) is list:
        for part in elem:
            if type(part) is list:
                part = [ interpret_render(obj, x) for x in part ]
                if (part[0] == part[1]) if len(part) > 2 else part[0]:
                    return part[-1]
            else:
                return interpret_render(obj, part)
        return None
    elif elem[0] == '.':
        return getattr(obj, elem[1:])
    else
        return elem


class RenderStack:
    surface_flags = pygame.HWSURFACE | pygame.SRCALPHA
    colors = read_resource_dict('colors')

    def __init__(self, size, flip, pose):
        if type(size) is int:
            size = (size, size)
        elif type(size) is not tuple:
            size = tuple(size)
        self.steps = []
        self.size = size
        self.flip = flip
        self.pose = str(pose)
        self.dirty = False
        self.depth = 0


    def add_chunk(self, obj, chunk):
        order = interpret_render(obj, chunk[0])
        name = interpret_render(obj, chunk[1]).upper()
        color_type = interpret_render(obj, chunk[2])
        color_name = interpret_render(obj, chunk[3]).upper()
        add(order, name, color_type, color_name, chunk[4:])


    def add(self, order, name, color_type, color_name, steps):
        colors = RenderStack.colors[color_type][chunk[color_name]
        for i, step in enumerate(steps):
            sprite = sprites[step[0] + name + self.pose]
            color = colors[step[1]] if len(step) > 1 and type(step[1]) is int else None
            extra = step[(1 if color is None else 2):]
            self.steps.append(RenderStep(order, name, i, self.size, sprite, color, extra))
        self.dirty = True


    def render(self):
        if self.dirty:
            self.steps.sort()

        stack = [pygame.Surface(self.size, RenderStack.surface_flags)]

        for step in self.steps:
            step.render(stack)
        sprite = stack[0]

        if self.flip:
            sprite = pygame.transform.flip(sprite, True, False)
        return sprite
