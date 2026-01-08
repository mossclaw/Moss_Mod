# How to make mod-mods

## What to change
First, you need to identify what you want to add or change.

You can use this system to modify most .json files in the game, 
as well as adding or replacing spites.

### Some common changes
#### Adding pelt colors
- Add a new entry under `"pelt"` in `resources/dicts/colors.json`.
- Add the name of the color to at least one of the lists under `"colors"` in `resources/dicts/fantasy_pelts.json` and optionally `resources/dicts/real_pelts.json`.

#### Adding eye colors
- Add a new entry under `"eyes"` in `resources/dicts/colors.json`.
- Add the name of the color to at least one of the lists under `"eyes"` in `resources/dicts/fantasy_pelts.json` and optionally `resources/dicts/real_pelts.json`.

## How to change it
The base structure of a mod-mod is a directory containing directories that mirror the 
relevant part of the games's directory structure. 

### Sprite sheets
If you want to add a sprite sheet, you add a `sprites` directory with the relevant 
sub-directories and .png files. Making the game make use of them will then require 
also changing some .json files.

If you include a spritesheet with the same name and path as one in the game, then 
yours will simply replace the base one.

### Json files
To change a .json file, you need to put one with the same name and path under your mod-mod 
folder as one from the base game. It does not simply replace that file, instead they are 
_merged_.

To change something, include as much of the structure of the original .json as needed to 
specify the right place in the file. When the equivalent dict exists in both the original
and the mod, then for each key in the mod dict:
- If the key starts with a `-`: 
  The `-` is removed from the key, and whatever value was in the original under the new key 
  is replaced with the value from the mod. If the new key is not in the original, it and its 
  value are added.
- If the key is not in the original:
  The key and its value are added to the original.
- If the key is in the original:
  - If both original and modded values are dicts:
    They are merged in the way described here.
  - If both original and modded values are lists:
    Any elements in the modded list that are not already in the original list are appended 
    to the end of it.
  - Otherwise:
    Nothing happens.

### Example
Say we want to create a mod-mod named "deathray" that adds two new eye colors designed to 
sear the viewer's retinas.

We would create a directory `mods/deathray`, and add two .json files:

`mods/deathray/resources/dicts/colors.json`:
```json
{
  "eyes": {
    "-DEATHRAY" : ["#ffffff", "#ffffff", "#ffffff", "#ffffff"],
    "-CONTRAST" : ["#ffffff", "#000000", "#ffffff", "#000000"]
  }
}
```
The reason we prepended the keys with `-` is so that conflicts with other mod-mods adding a color with the same name will be resolved by load order. In the abcense of name conflicts it has no effect.

`mods/deathray/resources/dicts/fantasy_pelts.json`:
```json
{
  "eyes": {
    "yellow": ["DEATHRAY", "CONTRAST"]
  }
}
```
Thus adding both new colors to the "yellow" color group.

## Sharing your mod-mod
To make sharing your mod-mod with others easier, you can make it a .zip file instead of 
a directory. To do so, you create a zip file containing the *contents* of the directory.
So if you were to zip up `mods/deathray` and add it in zipped form to the game instead, 
you would have a file `mods/deathray.zip`. If you open the zip file, the immediate (top-level) 
contents should be the same as in the directory version.

### Load order
If several mod-mods replace the same thing, then the one loaded last gets the final say.
To determine the order, there is a file `load_order.json` in the mods folder. 
It should contain a Json list, with the names of the mod-mods you want to control the order of. 
Any mod-mods listed there will be loaded _last_, in the order mentioned. 
In the example above, the name in the entry would be `"deathray"`, no matter if it is the 
zip or directory version.
