"""
Module that handles the name generation for all cats.
"""

import os
import random

import ujson

from scripts.game_structure.game_essentials import game
from scripts.housekeeping.datadir import get_save_dir


class Name:
    """
    Stores & handles name generation.
    """

    if os.path.exists("resources/dicts/names/names.json"):
        with open("resources/dicts/names/names.json", encoding="utf-8") as read_file:
            names_dict = ujson.loads(read_file.read())

        if os.path.exists(get_save_dir() + "/prefixlist.txt"):
            with open(
                str(get_save_dir() + "/prefixlist.txt", "r"), encoding="utf-8"
            ) as read_file:
                name_list = read_file.read()
                if_names = len(name_list)
            if if_names > 0:
                new_names = name_list.split("\n")
                for new_name in new_names:
                    if new_name != "":
                        if new_name.startswith("-"):
                            while new_name[1:] in names_dict["normal_prefixes"]:
                                names_dict["normal_prefixes"].remove(new_name[1:])
                        else:
                            names_dict["normal_prefixes"].append(new_name)

        if os.path.exists(get_save_dir() + "/suffixlist.txt"):
            with open(
                str(get_save_dir() + "/suffixlist.txt", "r"), encoding="utf-8"
            ) as read_file:
                name_list = read_file.read()
                if_names = len(name_list)
            if if_names > 0:
                new_names = name_list.split("\n")
                for new_name in new_names:
                    if new_name != "":
                        if new_name.startswith("-"):
                            while new_name[1:] in names_dict["normal_suffixes"]:
                                names_dict["normal_suffixes"].remove(new_name[1:])
                        else:
                            names_dict["normal_suffixes"].append(new_name)

        if os.path.exists(get_save_dir() + "/specialsuffixes.txt"):
            with open(
                str(get_save_dir() + "/specialsuffixes.txt", "r"), encoding="utf-8"
            ) as read_file:
                name_list = read_file.read()
                if_names = len(name_list)
            if if_names > 0:
                new_names = name_list.split("\n")
                for new_name in new_names:
                    if new_name != "":
                        if new_name.startswith("-"):
                            del names_dict["special_suffixes"][new_name[1:]]
                        elif ":" in new_name:
                            _tmp = new_name.split(":")
                            names_dict["special_suffixes"][_tmp[0]] = _tmp[1]

    def __init__(
        self,
        status="warrior",
        prefix=None,
        suffix=None,
        colour=None,
        eyes=None,
        pelt=None,
        tortiepattern=None,
        biome=None,
        specsuffix_hidden=False,
        load_existing_name=False,
        
    ):
        self.status = status
        self.prefix = prefix
        self.suffix = suffix
        self.specsuffix_hidden = specsuffix_hidden
        # Track style-based names for parents
        self.prefix_styles = []
        self.suffix_styles = []

        name_fixpref = False
        # Set prefix
        if prefix is None:
            self.give_prefix(eyes, colour, biome)
            # needed for random dice when we're changing the Prefix
            name_fixpref = True

        # Set suffix
        if self.suffix is None:
            self.give_suffix(pelt, biome, tortiepattern)
            if name_fixpref and self.prefix is None:
                # needed for random dice when we're changing the Prefix
                name_fixpref = False

        if self.suffix and not load_existing_name:
            # Prevent triple letter names from joining prefix and suffix from occurring (ex. Beeeye)
            triple_letter = False
            possible_three_letter = (
                self.prefix[-2:] + self.suffix[0],
                self.prefix[-1] + self.suffix[:2],
            )
            if all(i == possible_three_letter[0][0] for i in possible_three_letter[0]) or all(i == possible_three_letter[1][0] for i in possible_three_letter[1]):
                triple_letter = True

            # Prevent double animal names (ex. Spiderfalcon)
            double_animal = False
            # Check if both prefix and suffix are tagged as 'animal'
            prefix_is_animal = (
                "animal" in self.names_dict["names"][self.prefix]["tags"] and
                "prefix" in self.names_dict["names"][self.prefix]["tags"]
            )
            suffix_is_animal = (
                "animal" in self.names_dict["names"][self.suffix]["tags"] and
                "suffix" in self.names_dict["names"][self.suffix]["tags"]
            )
            if prefix_is_animal and suffix_is_animal:
                double_animal = True

            # Prevent the inappropriate names
            nono_name = self.prefix + self.suffix
            # Prevent double names (ex. Iceice)
            # Prevent suffixes containing the prefix (ex. Butterflyfly)

            i = 0
            while (
                nono_name.lower() in self.names_dict["inappropriate_names"]
                or triple_letter
                or double_animal
                or (
                    self.prefix.lower() in self.suffix.lower()
                    and str(self.prefix) != ""
                )
                or (
                    self.suffix.lower() in self.prefix.lower()
                    and str(self.suffix) != ""
                )
            ):

                # check if random die was for prefix
                if name_fixpref:
                    self.give_prefix(eyes, colour, biome)
                else:
                    self.give_suffix(pelt, biome, tortiepattern)

                nono_name = self.prefix + self.suffix
                possible_three_letter = (
                    self.prefix[-2:] + self.suffix[0],
                    self.prefix[-1] + self.suffix[:2],
                )
                if not (
                    all(
                        i == possible_three_letter[0][0]
                        for i in possible_three_letter[0]
                    )
                    or all(
                        i == possible_three_letter[1][0]
                        for i in possible_three_letter[1]
                    )
                ):
                    triple_letter = False
                if not (
                    self.prefix in self.names_dict["animal_prefixes"]
                    and self.suffix in self.names_dict["animal_suffixes"]
                ):
                    double_animal = False
                i += 1

    # Generate possible prefix
    def give_prefix(self, eyes, colour, biome):
        """Generate possible prefix based on parent styles and appearance."""
        if game.config["cat_name_controls"]["always_name_after_appearance"]:
            named_after_appearance = True
        else:
            named_after_appearance = not random.getrandbits(2)

        named_after_biome = not random.getrandbits(3)

        possible_prefix_categories = self.get_style_based_prefixes(eyes, colour, biome)

        # If there are style-based prefix options, choose one
        if named_after_appearance and possible_prefix_categories and not named_after_biome:
            self.prefix = random.choice(possible_prefix_categories)
        elif named_after_biome and possible_prefix_categories:
            self.prefix = random.choice(possible_prefix_categories)
        else:
            # If no specific styles, pick a random prefix with the "prefix" tag
            prefix_names = [
                name for name, info in self.names_dict["names"].items()
                if "prefix" in info["tags"]
            ]
            self.prefix = random.choice(prefix_names)

        self.track_prefix_style()

    # Generate possible suffix
    def give_suffix(self, pelt, biome, tortiepattern):
        """Generate suffix, factoring in style preferences."""
        # If there is no pelt pattern or it's "SingleColour", random suffix
        if pelt is None or pelt == "SingleColour":
            suffix_names = [
                name for name, info in self.names_dict["names"].items()
                if "suffix" in info["tags"]
            ]
            self.suffix = random.choice(suffix_names)
        else:
            # Pick a random suffix based on "suffix" tag
            suffix_names = [
                name for name, info in self.names_dict["names"].items()
                if "suffix" in info["tags"]
            ]
            self.suffix = random.choice(suffix_names)
            
        self.track_suffix_style()


    def get_style_based_prefixes(self, eyes, colour, biome):
        """Filter possible prefixes based on parent styles and tags."""
        possible_prefixes = []

        # Look for names tagged with the "eyes" style
        if eyes:
            eye_style_names = [
                name for name, info in self.names_dict["names"].items()
                if "eyes" in info["tags"]
            ]
            if eye_style_names:
                possible_prefixes.append(random.choice(eye_style_names))

        # Check if colour has associated prefix options
        if colour:
            colour_style_names = [
                name for name, info in self.names_dict["names"].items()
                if "color" in info["tags"]
            ]
            if colour_style_names:
                possible_prefixes.append(random.choice(colour_style_names))

        # Check if biome has associated prefix options
        if biome and biome in self.names_dict["styles"]["nature"]:
            biome_style_names = [
                name for name, info in self.names_dict["names"].items()
                if biome in info["tags"]
            ]
            if biome_style_names:
                possible_prefixes.append(random.choice(biome_style_names))

        return possible_prefixes

    def track_prefix_style(self):
        """Assign the name's style based on the tags in its dictionary entry."""
        name_info = self.names_dict["names"].get(self.prefix)
        if name_info:
            tags = name_info["tags"]
            for style, related_tags in self.names_dict["styles"].items():
                if any(tag in tags for tag in related_tags):
                    self.prefix_styles.append(style)

    def track_suffix_style(self):
        """Track the suffix styles similarly to the prefix."""
        name_info = self.names_dict["names"].get(self.suffix)
        if name_info:
            tags = name_info["tags"]
            for style, related_tags in self.names_dict["styles"].items():
                if any(tag in tags for tag in related_tags):
                    self.suffix_styles.append(style)

    def __repr__(self):
        # Handles predefined suffixes (such as newborns being kit),
        # then suffixes based on ages (fixes #2004, just trust me)
        if (
            self.status in self.names_dict["special_suffixes"]
            and not self.specsuffix_hidden
        ):
            return self.prefix + self.names_dict["special_suffixes"][self.status]
        if game.config["fun"]["april_fools"]:
            return self.prefix + "egg"
        return self.prefix + self.suffix


names = Name()
names.prefix_history = []
