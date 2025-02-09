# pylint: disable=line-too-long
"""

TODO: Docs


"""  # pylint: enable=line-too-long

import logging
import re
from itertools import combinations
from math import floor
from random import choice, choices, randint, random, sample, randrange
from sys import exit as sys_exit
from typing import List, Tuple

import pygame
import ujson
from pygame_gui.core import ObjectID

logger = logging.getLogger(__name__)
from scripts.game_structure import image_cache

from scripts.cat.history import History
from scripts.cat.names import names
from scripts.cat.pelts import Pelt
from scripts.cat.sprites import sprites
from scripts.game_structure.game_essentials import game
import scripts.game_structure.screen_settings  # must be done like this to get updates when we change screen size etc



# ---------------------------------------------------------------------------- #
#                               Getting Cats                                   #
# ---------------------------------------------------------------------------- #


def get_alive_clan_queens(living_cats):
    living_kits = [
        cat
        for cat in living_cats
        if not (cat.dead or cat.outside) and cat.status in ["kitten", "newborn"]
    ]

    queen_dict = {}
    for cat in living_kits.copy():
        parents = cat.get_parents()
        # Fetch parent object, only alive and not outside.
        parents = [
            cat.fetch_cat(i)
            for i in parents
            if cat.fetch_cat(i)
            and not (cat.fetch_cat(i).dead or cat.fetch_cat(i).outside)
        ]
        if not parents:
            continue

        if (
            len(parents) == 1
            or len(parents) > 2
            or all(i.gender == "male" for i in parents)
            or parents[0].gender == "female"
        ):
            if parents[0].ID in queen_dict:
                queen_dict[parents[0].ID].append(cat)
                living_kits.remove(cat)
            else:
                queen_dict[parents[0].ID] = [cat]
                living_kits.remove(cat)
        elif len(parents) == 2:
            if parents[1].ID in queen_dict:
                queen_dict[parents[1].ID].append(cat)
                living_kits.remove(cat)
            else:
                queen_dict[parents[1].ID] = [cat]
                living_kits.remove(cat)
    return queen_dict, living_kits


def get_alive_status_cats(
    Cat, get_status: list, working: bool = False, sort: bool = False
) -> list:
    """
    returns a list of cat objects for all living cats of get_status in Clan
    :param Cat Cat: Cat class
    :param list get_status: list of statuses searching for
    :param bool working: default False, set to True if you would like the list to only include working cats
    :param bool sort: default False, set to True if you would like list sorted by descending moon age
    """

    alive_cats = [
        i
        for i in Cat.all_cats.values()
        if i.status in get_status and not i.dead and not i.outside
    ]

    if working:
        alive_cats = [i for i in alive_cats if not i.not_working()]

    if sort:
        alive_cats = sorted(alive_cats, key=lambda cat: cat.moons, reverse=True)

    return alive_cats


def get_living_cat_count(Cat):
    """
    Returns the int of all living cats, both in and out of the Clan
    :param Cat: Cat class
    """
    count = 0
    for the_cat in Cat.all_cats.values():
        if the_cat.dead:
            continue
        count += 1
    return count


def get_living_clan_cat_count(Cat):
    """
    Returns the int of all living cats within the Clan
    :param Cat: Cat class
    """
    count = 0
    for the_cat in Cat.all_cats.values():
        if the_cat.dead or the_cat.exiled or the_cat.outside:
            continue
        count += 1
    return count


def get_cats_same_age(Cat, cat, age_range=10):
    """
    Look for all cats in the Clan and returns a list of cats which are in the same age range as the given cat.
    :param Cat: Cat class
    :param cat: the given cat
    :param int age_range: The allowed age difference between the two cats, default 10
    """
    cats = []
    for inter_cat in Cat.all_cats.values():
        if inter_cat.dead or inter_cat.outside or inter_cat.exiled:
            continue
        if inter_cat.ID == cat.ID:
            continue

        if inter_cat.ID not in cat.relationships:
            cat.create_one_relationship(inter_cat)
            if cat.ID not in inter_cat.relationships:
                inter_cat.create_one_relationship(cat)
            continue

        if (
            inter_cat.moons <= cat.moons + age_range
            and inter_cat.moons <= cat.moons - age_range
        ):
            cats.append(inter_cat)

    return cats


def get_free_possible_mates(cat):
    """Returns a list of available cats, which are possible mates for the given cat."""
    cats = []
    for inter_cat in cat.all_cats.values():
        if inter_cat.dead or inter_cat.outside or inter_cat.exiled:
            continue
        if inter_cat.ID == cat.ID:
            continue

        if inter_cat.ID not in cat.relationships:
            cat.create_one_relationship(inter_cat)
            if cat.ID not in inter_cat.relationships:
                inter_cat.create_one_relationship(cat)
            continue

        if inter_cat.is_potential_mate(cat, for_love_interest=True):
            cats.append(inter_cat)
    return cats


def get_random_moon_cat(
    Cat, main_cat, parent_child_modifier=True, mentor_app_modifier=True
):
    """
    returns a random cat for use in moon events
    :param Cat: Cat class
    :param main_cat: cat object of main cat in event
    :param parent_child_modifier: increase the chance of the random cat being a
    parent of the main cat. Default True
    :param mentor_app_modifier: increase the chance of the random cat being a mentor or
    app of the main cat. Default True
    """
    random_cat = None

    # grab list of possible random cats
    possible_r_c = list(
        filter(
            lambda c: not c.dead
            and not c.exiled
            and not c.outside
            and (c.ID != main_cat.ID),
            Cat.all_cats.values(),
        )
    )

    if possible_r_c:
        random_cat = choice(possible_r_c)
        if parent_child_modifier and not int(random() * 3):
            possible_parents = []
            if main_cat.parent1:
                if Cat.fetch_cat(main_cat.parent1) in possible_r_c:
                    possible_parents.append(main_cat.parent1)
            if main_cat.parent2:
                if Cat.fetch_cat(main_cat.parent2) in possible_r_c:
                    possible_parents.append(main_cat.parent2)
            if main_cat.adoptive_parents:
                for parent in main_cat.adoptive_parents:
                    if Cat.fetch_cat(parent) in possible_r_c:
                        possible_parents.append(parent)
            if possible_parents:
                random_cat = Cat.fetch_cat(choice(possible_parents))
        if mentor_app_modifier:
            if (
                main_cat.status
                in ["apprentice", "mediator apprentice", "medicine cat apprentice"]
                and main_cat.mentor
                and not int(random() * 3)
            ):
                random_cat = Cat.fetch_cat(main_cat.mentor)
            elif main_cat.apprentice and not int(random() * 3):
                random_cat = Cat.fetch_cat(choice(main_cat.apprentice))

    if isinstance(random_cat, str):
        print(f"WARNING: random cat was {random_cat} instead of cat object")
        random_cat = Cat.fetch_cat(random_cat)
    return random_cat


def get_warring_clan():
    """
    returns enemy clan if a war is currently ongoing
    """
    enemy_clan = None
    if game.clan.war.get("at_war", False):
        for other_clan in game.clan.all_clans:
            if other_clan.name == game.clan.war["enemy"]:
                enemy_clan = other_clan

    return enemy_clan


# ---------------------------------------------------------------------------- #
#                          Handling Outside Factors                            #
# ---------------------------------------------------------------------------- #


def get_current_season():
    """
    function to handle the math for finding the Clan's current season
    :return: the Clan's current season
    """

    if game.config["lock_season"]:
        game.clan.current_season = game.clan.starting_season
        return game.clan.starting_season

    modifiers = {"Newleaf": 0, "Greenleaf": 3, "Leaf-fall": 6, "Leaf-bare": 9}
    index = game.clan.age % 12 + modifiers[game.clan.starting_season]

    if index > 11:
        index = index - 12

    game.clan.current_season = game.clan.seasons[index]

    return game.clan.current_season


def change_clan_reputation(difference):
    """
    will change the Clan's reputation with outsider cats according to the difference parameter.
    """
    game.clan.reputation += difference


def change_clan_relations(other_clan, difference):
    """
    will change the Clan's relation with other clans according to the difference parameter.
    """
    # grab the clan that has been indicated
    other_clan = other_clan
    # grab the relation value for that clan
    y = game.clan.all_clans.index(other_clan)
    clan_relations = int(game.clan.all_clans[y].relations)
    # change the value
    clan_relations += difference
    # making sure it doesn't exceed the bounds
    if clan_relations > 30:
        clan_relations = 30
    elif clan_relations < 0:
        clan_relations = 0
    # setting it in the Clan save
    game.clan.all_clans[y].relations = clan_relations


def create_new_cat_block(
    Cat, Relationship, event, in_event_cats: dict, i: int, attribute_list: List[str]
) -> list:
    """
    Creates a single new_cat block and then generates and returns the cats within the block
    :param Cat Cat: always pass Cat class
    :param Relationship Relationship: always pass Relationship class
    :param event: always pass the event class
    :param dict in_event_cats: dict containing involved cats' abbreviations as keys and cat objects as values
    :param int i: index of the cat block
    :param list[str] attribute_list: attribute list contained within the block
    """

    thought = "Is looking around the camp with wonder"
    new_cats = None

    # gather bio parents
    parent1 = None
    parent2 = None
    for tag in attribute_list:
        match = re.match(r"parent:([,0-9]+)", tag)
        if not match:
            continue

        parent_indexes = match.group(1).split(",")
        if not parent_indexes:
            continue

        parent_indexes = [int(index) for index in parent_indexes]
        for index in parent_indexes:
            if index >= i:
                continue

            if parent1 is None:
                parent1 = event.new_cats[index][0]
            else:
                parent2 = event.new_cats[index][0]
        break

    # gather mates
    give_mates = []
    for tag in attribute_list:
        match = re.match(r"mate:([_,0-9a-zA-Z]+)", tag)
        if not match:
            continue

        mate_indexes = match.group(1).split(",")

        # TODO: make this less ugly
        for index in mate_indexes:
            if index in in_event_cats:
                if in_event_cats[index] in [
                    "apprentice",
                    "medicine cat apprentice",
                    "mediator apprentice",
                ]:
                    print("Can't give apprentices mates")
                    continue

                give_mates.append(in_event_cats[index])

            try:
                index = int(index)
            except ValueError:
                print(f"mate-index not correct: {index}")
                continue

            if index >= i:
                continue

            give_mates.extend(event.new_cats[index])

    # determine gender
    if "male" in attribute_list:
        gender = "male"
    elif "female" in attribute_list:
        gender = "female"
    elif (
        "can_birth" in attribute_list and not game.clan.clan_settings["same sex birth"]
    ):
        gender = "female"
    else:
        gender = None

    # will the cat get a new name?
    if "new_name" in attribute_list:
        new_name = True
    elif "old_name" in attribute_list:
        new_name = False
    else:
        new_name = choice([True, False])

    # STATUS - must be handled before backstories
    status = None
    for _tag in attribute_list:
        match = re.match(r"status:(.+)", _tag)
        if not match:
            continue

        if match.group(1) in [
            "newborn",
            "kitten",
            "elder",
            "apprentice",
            "warrior",
            "mediator apprentice",
            "mediator",
            "medicine cat apprentice",
            "medicine cat",
        ]:
            status = match.group(1)
            break

    # SET AGE
    age = None
    for _tag in attribute_list:
        match = re.match(r"age:(.+)", _tag)
        if not match:
            continue

        if match.group(1) in Cat.age_moons:
            age = randint(
                Cat.age_moons[match.group(1)][0], Cat.age_moons[match.group(1)][1]
            )
            break

        # Set same as first mate
        if match.group(1) == "mate" and give_mates:
            age = randint(
                Cat.age_moons[give_mates[0].age][0], Cat.age_moons[give_mates[0].age][1]
            )
            break

        if match.group(1) == "has_kits":
            age = randint(19, 120)
            break

    if status and not age:
        if status in ["apprentice", "mediator apprentice", "medicine cat apprentice"]:
            age = randint(
                Cat.age_moons["adolescent"][0], Cat.age_moons["adolescent"][1]
            )
        elif status in ["warrior", "mediator", "medicine cat"]:
            age = randint(
                Cat.age_moons["young adult"][0], Cat.age_moons["senior adult"][1]
            )
        elif status == "elder":
            age = randint(Cat.age_moons["senior"][0], Cat.age_moons["senior"][1])

    if "kittypet" in attribute_list:
        cat_type = "kittypet"
    elif "rogue" in attribute_list:
        cat_type = "rogue"
    elif "loner" in attribute_list:
        cat_type = "loner"
    elif "clancat" in attribute_list:
        cat_type = "former Clancat"
    else:
        cat_type = choice(["kittypet", "loner", "former Clancat"])

    # LITTER
    litter = False
    if "litter" in attribute_list:
        litter = True
        if status not in ["kitten", "newborn"]:
            status = "kitten"

    # CHOOSE DEFAULT BACKSTORY BASED ON CAT TYPE, STATUS
    if status in ("kitten", "newborn"):
        chosen_backstory = choice(
            BACKSTORIES["backstory_categories"]["abandoned_backstories"]
        )
    elif status == "medicine cat" and cat_type == "former Clancat":
        chosen_backstory = choice(["medicine_cat", "disgraced1"])
    elif status == "medicine cat":
        chosen_backstory = choice(["wandering_healer1", "wandering_healer2"])
    else:
        if cat_type == "former Clancat":
            x = "former_clancat"
        else:
            x = cat_type
        chosen_backstory = choice(
            BACKSTORIES["backstory_categories"].get(f"{x}_backstories", ["outsider1"])
        )

    # OPTION TO OVERRIDE DEFAULT BACKSTORY
    bs_override = False
    stor = []
    for _tag in attribute_list:
        match = re.match(r"backstory:(.+)", _tag)
        if match:
            stor = [
                x for x in match.group(1).split(",") if x in BACKSTORIES["backstories"]
            ]
            if not stor:
                bs_override = True
                continue
            chosen_backstory = choice(stor)
            break

    # KITTEN THOUGHT
    if status in ["kitten", "newborn"]:
        thought = "Is snuggled safe in the nursery"

    # MEETING - DETERMINE IF THIS IS AN OUTSIDE CAT
    outside = False
    if "meeting" in attribute_list:
        outside = True
        status = cat_type
        new_name = False
        thought = "Is wondering about those new cats"

    # IS THE CAT DEAD?
    alive = True
    if "dead" in attribute_list:
        alive = False
        thought = "Explores a new, starry world"

    # check if we can use an existing cat here
    chosen_cat = None
    if "exists" in attribute_list:
        existing_outsiders = [
            i for i in Cat.all_cats.values() if i.outside and not i.dead
        ]
        possible_outsiders = []
        for cat in existing_outsiders:
            if stor and cat.backstory not in stor:
                continue
            if cat_type != cat.status:
                continue
            if gender and gender != cat.gender:
                continue
            if age and age not in Cat.age_moons[cat.age]:
                continue
            possible_outsiders.append(cat)

        if possible_outsiders:
            chosen_cat = choice(possible_outsiders)
            game.clan.add_to_clan(chosen_cat)
            chosen_cat.status = status
            chosen_cat.outside = outside
            if not alive:
                chosen_cat.die()

            if new_name:
                name = f"{chosen_cat.name.prefix}"
                spaces = name.count(" ")
                if choice([1, 2]) == 1 and spaces > 0:  # adding suffix to OG name
                    # make a list of the words within the name, then add the OG name back in the list
                    words = name.split(" ")
                    words.append(name)
                    new_prefix = choice(words)  # pick new prefix from that list
                    name = new_prefix
                    chosen_cat.name.prefix = name
                    chosen_cat.name.give_suffix(
                        pelt=chosen_cat.pelt,
                        biome=game.clan.biome,
                        tortiepattern=chosen_cat.pelt.tortiepattern,
                    )
                else:  # completely new name
                    chosen_cat.name.give_prefix(
                        eyes=chosen_cat.pelt.eye_colour,
                        colour=chosen_cat.pelt.colour,
                        biome=game.clan.biome,
                    )
                    chosen_cat.name.give_suffix(
                        pelt=chosen_cat.pelt.colour,
                        biome=game.clan.biome,
                        tortiepattern=chosen_cat.pelt.tortiepattern,
                    )

            new_cats = [chosen_cat]

    # Now we generate the new cat
    if not chosen_cat:
        new_cats = create_new_cat(
            Cat,
            new_name=new_name,
            loner=cat_type in ["loner", "rogue"],
            kittypet=cat_type == "kittypet",
            other_clan=cat_type == "former Clancat",
            kit=False if litter else status in ["kitten", "newborn"],
            # this is for singular kits, litters need this to be false
            litter=litter,
            backstory=chosen_backstory,
            status=status,
            age=age,
            gender=gender,
            thought=thought,
            alive=alive,
            outside=outside,
            parent1=parent1.ID if parent1 else None,
            parent2=parent2.ID if parent2 else None,
        )

        # NEXT
        # add relations to bio parents, if needed
        # add relations to cats generated within the same block, as they are littermates
        # add mates
        # THIS DOES NOT ADD RELATIONS TO CATS IN THE EVENT, those are added within the relationships block of the event

        for n_c in new_cats:
            # SET MATES
            for inter_cat in give_mates:
                if n_c == inter_cat or n_c.ID in inter_cat.mate:
                    continue

                # this is some duplicate work, since this triggers inheritance re-calcs
                # TODO: optimize
                n_c.set_mate(inter_cat)

            # LITTERMATES
            for inter_cat in new_cats:
                if n_c == inter_cat:
                    continue

                y = randrange(0, 20)
                start_relation = Relationship(n_c, inter_cat, False, True)
                start_relation.platonic_like += 30 + y
                start_relation.comfortable = 10 + y
                start_relation.admiration = 15 + y
                start_relation.trust = 10 + y
                n_c.relationships[inter_cat.ID] = start_relation

            # BIO PARENTS
            for par in (parent1, parent2):
                if not par:
                    continue

                y = randrange(0, 20)
                start_relation = Relationship(par, n_c, False, True)
                start_relation.platonic_like += 30 + y
                start_relation.comfortable = 10 + y
                start_relation.admiration = 15 + y
                start_relation.trust = 10 + y
                par.relationships[n_c.ID] = start_relation

                y = randrange(0, 20)
                start_relation = Relationship(n_c, par, False, True)
                start_relation.platonic_like += 30 + y
                start_relation.comfortable = 10 + y
                start_relation.admiration = 15 + y
                start_relation.trust = 10 + y
                n_c.relationships[par.ID] = start_relation

            # UPDATE INHERITANCE
            n_c.create_inheritance_new_cat()

    return new_cats


def get_other_clan(clan_name):
    """
    returns the clan object of given clan name
    """
    for clan in game.clan.all_clans:
        if clan.name == clan_name:
            return clan


def create_new_cat(
    Cat,
    new_name: bool = False,
    loner: bool = False,
    kittypet: bool = False,
    kit: bool = False,
    litter: bool = False,
    other_clan: bool = None,
    backstory: bool = None,
    status: str = None,
    age: int = None,
    gender: str = None,
    thought: str = "Is looking around the camp with wonder",
    alive: bool = True,
    outside: bool = False,
    parent1: str = None,
    parent2: str = None,
) -> list:
    """
    This function creates new cats and then returns a list of those cats
    :param Cat Cat: pass the Cat class
    :params Relationship Relationship: pass the Relationship class
    :param bool new_name: set True if cat(s) is a loner/rogue receiving a new Clan name - default: False
    :param bool loner: set True if cat(s) is a loner or rogue - default: False
    :param bool kittypet: set True if cat(s) is a kittypet - default: False
    :param bool kit: set True if the cat is a lone kitten - default: False
    :param bool litter: set True if a litter of kittens needs to be generated - default: False
    :param bool other_clan: if new cat(s) are from a neighboring clan, set true
    :param bool backstory: a list of possible backstories.json for the new cat(s) - default: None
    :param str status: set as the rank you want the new cat to have - default: None (will cause a random status to be picked)
    :param int age: set the age of the new cat(s) - default: None (will be random or if kit/litter is true, will be kitten.
    :param str gender: set the gender (BIRTH SEX) of the cat - default: None (will be random)
    :param str thought: if you need to give a custom "welcome" thought, set it here
    :param bool alive: set this as False to generate the cat as already dead - default: True (alive)
    :param bool outside: set this as True to generate the cat as an outsider instead of as part of the Clan - default: False (Clan cat)
    :param str parent1: Cat ID to set as the biological parent1
    :param str parent2: Cat ID object to set as the biological parert2
    """
    # TODO: it would be nice to rewrite this to be less bool-centric
    accessory = None
    if isinstance(backstory, list):
        backstory = choice(backstory)

    if backstory in (
        BACKSTORIES["backstory_categories"]["former_clancat_backstories"]
        or BACKSTORIES["backstory_categories"]["otherclan_categories"]
    ):
        other_clan = True

    created_cats = []

    if not litter:
        number_of_cats = 1
    else:
        number_of_cats = choices([2, 3, 4, 5], [5, 4, 1, 1], k=1)[0]

    if not isinstance(age, int):
        if status == "newborn":
            age = 0
        elif litter or kit:
            age = randint(1, 5)
        elif status in ("apprentice", "medicine cat apprentice", "mediator apprentice"):
            age = randint(6, 11)
        elif status == "warrior":
            age = randint(23, 120)
        elif status == "medicine cat":
            age = randint(23, 140)
        elif status == "elder":
            age = randint(120, 130)
        else:
            age = randint(6, 120)

    # setting status
    if not status:
        if age == 0:
            status = "newborn"
        elif age < 6:
            status = "kitten"
        elif 6 <= age <= 11:
            status = "apprentice"
        elif age >= 12:
            status = "warrior"
        elif age >= 120:
            status = "elder"

    # cat creation and naming time
    for index in range(number_of_cats):
        # setting gender
        if not gender:
            _gender = choice(["female", "male"])
        else:
            _gender = gender

        # other Clan cats, apps, and kittens (kittens and apps get indoctrinated lmao no old names for them)
        if other_clan or kit or litter or age < 12 and not (loner or kittypet):
            new_cat = Cat(
                moons=age,
                status=status,
                gender=_gender,
                backstory=backstory,
                parent1=parent1,
                parent2=parent2,
            )
        else:
            # grab starting names and accs for loners/kittypets
            if kittypet:
                name = choice(names.names_dict["loner_names"])
                if choice([1, 2]) == 1:
                    accessory = choice(Pelt.collars)
            elif (
                loner and choice([1, 2]) == 1
            ):  # try to give name from full loner name list
                name = choice(names.names_dict["loner_names"])
            else:
                name = choice(
                    names.names_dict["normal_prefixes"]
                )  # otherwise give name from prefix list (more nature-y names)

            # now we make the cats
            if new_name:  # these cats get new names
                if choice([1, 2]) == 1:  # adding suffix to OG name
                    spaces = name.count(" ")
                    if spaces > 0:
                        # make a list of the words within the name, then add the OG name back in the list
                        words = name.split(" ")
                        words.append(name)
                        new_prefix = choice(words)  # pick new prefix from that list
                        name = new_prefix
                    new_cat = Cat(
                        moons=age,
                        prefix=name,
                        status=status,
                        gender=_gender,
                        backstory=backstory,
                        parent1=parent1,
                        parent2=parent2,
                    )
                else:  # completely new name
                    new_cat = Cat(
                        moons=age,
                        status=status,
                        gender=_gender,
                        backstory=backstory,
                        parent1=parent1,
                        parent2=parent2,
                    )
            # these cats keep their old names
            else:
                new_cat = Cat(
                    moons=age,
                    prefix=name,
                    suffix="",
                    status=status,
                    gender=_gender,
                    backstory=backstory,
                    parent1=parent1,
                    parent2=parent2,
                )

        # give em a collar if they got one
        if accessory:
            new_cat.pelt.accessory = accessory
            new_cat.pelt.accessory_color = choice(new_cat.pelt.twoleg_acc_colors)
            new_cat.pelt.accessory_color2 = choice(new_cat.pelt.twoleg_acc_colors)
        if new_cat.pelt.accessory == "STUDDEDCOLLAR":
            new_cat.pelt.accessory_color2 = choice(new_cat.pelt.metal_colors)
        elif new_cat.pelt.accessory == "BELLCOLLAR":
            new_cat.pelt.accessory_color2 = choice(new_cat.pelt.metal_colors)



        # give apprentice aged cat a mentor
        if new_cat.age == "adolescent":
            new_cat.update_mentor()

        # Remove disabling scars, if they generated.
        not_allowed = [
            "NOPAW",
            "NOTAIL",
            "HALFTAIL",
            "NOEAR",
            "BOTHBLIND",
            "RIGHTBLIND",
            "LEFTBLIND",
            "BRIGHTHEART",
            "NOLEFTEAR",
            "NORIGHTEAR",
            "MANLEG",
        ]
        for scar in new_cat.pelt.scars:
            if scar in not_allowed:
                new_cat.pelt.scars.remove(scar)

        # chance to give the new cat a permanent condition, higher chance for found kits and litters
        if kit or litter:
            chance = int(
                game.config["cat_generation"]["base_permanent_condition"] / 11.25
            )
        else:
            chance = game.config["cat_generation"]["base_permanent_condition"] + 10
        if not int(random() * chance):
            possible_conditions = []
            for condition in PERMANENT:
                if (kit or litter) and PERMANENT[condition]["congenital"] not in [
                    "always",
                    "sometimes",
                ]:
                    continue
                # next part ensures that a kit won't get a condition that takes too long to reveal
                age = new_cat.moons
                leeway = 5 - (PERMANENT[condition]["moons_until"] + 1)
                if age > leeway:
                    continue
                possible_conditions.append(condition)

            if possible_conditions:
                chosen_condition = choice(possible_conditions)
                born_with = False
                if PERMANENT[chosen_condition]["congenital"] in [
                    "always",
                    "sometimes",
                ]:
                    born_with = True

                    new_cat.get_permanent_condition(chosen_condition, born_with)
                    if (
                        new_cat.permanent_condition[chosen_condition]["moons_until"]
                        == 0
                    ):
                        new_cat.permanent_condition[chosen_condition][
                            "moons_until"
                        ] = -2

                # assign scars
                if chosen_condition in ["lost a leg", "born without a leg"]:
                    new_cat.pelt.scars.append("NOPAW")
                elif chosen_condition in ["lost their tail", "born without a tail"]:
                    new_cat.pelt.scars.append("NOTAIL")

        if outside:
            new_cat.outside = True
        if not alive:
            new_cat.die()

        # newbie thought
        new_cat.thought = thought

        # and they exist now
        created_cats.append(new_cat)
        game.clan.add_cat(new_cat)
        history = History()
        history.add_beginning(new_cat)

        # create relationships
        new_cat.create_relationships_new_cat()
        # Note - we always update inheritance after the cats are generated, to
        # allow us to add parents.
        # new_cat.create_inheritance_new_cat()

    return created_cats


# ---------------------------------------------------------------------------- #
#                             Cat Relationships                                #
# ---------------------------------------------------------------------------- #


def get_highest_romantic_relation(
    relationships, exclude_mate=False, potential_mate=False
):
    """Returns the relationship with the highest romantic value."""
    max_love_value = 0
    current_max_relationship = None
    for rel in relationships:
        if rel.romantic_love < 0:
            continue
        if exclude_mate and rel.cat_from.ID in rel.cat_to.mate:
            continue
        if potential_mate and not rel.cat_to.is_potential_mate(
            rel.cat_from, for_love_interest=True
        ):
            continue
        if rel.romantic_love > max_love_value:
            current_max_relationship = rel
            max_love_value = rel.romantic_love

    return current_max_relationship


def check_relationship_value(cat_from, cat_to, rel_value=None):
    """
    returns the value of the rel_value param given
    :param cat_from: the cat who is having the feelings
    :param cat_to: the cat that the feelings are directed towards
    :param rel_value: the relationship value that you're looking for,
    options are: romantic, platonic, dislike, admiration, comfortable, jealousy, trust
    """
    if cat_to.ID in cat_from.relationships:
        relationship = cat_from.relationships[cat_to.ID]
    else:
        relationship = cat_from.create_one_relationship(cat_to)

    if rel_value == "romantic":
        return relationship.romantic_love
    elif rel_value == "platonic":
        return relationship.platonic_like
    elif rel_value == "dislike":
        return relationship.dislike
    elif rel_value == "admiration":
        return relationship.admiration
    elif rel_value == "comfortable":
        return relationship.comfortable
    elif rel_value == "jealousy":
        return relationship.jealousy
    elif rel_value == "trust":
        return relationship.trust


def get_personality_compatibility(cat1, cat2):
    """Returns:
    True - if personalities have a positive compatibility
    False - if personalities have a negative compatibility
    None - if personalities have a neutral compatibility
    """
    personality1 = cat1.personality.trait
    personality2 = cat2.personality.trait

    if personality1 == personality2:
        if personality1 is None:
            return None
        return True

    lawfulness_diff = abs(cat1.personality.lawfulness - cat2.personality.lawfulness)
    sociability_diff = abs(cat1.personality.sociability - cat2.personality.sociability)
    aggression_diff = abs(cat1.personality.aggression - cat2.personality.aggression)
    stability_diff = abs(cat1.personality.stability - cat2.personality.stability)
    list_of_differences = [
        lawfulness_diff,
        sociability_diff,
        aggression_diff,
        stability_diff,
    ]

    running_total = 0
    for x in list_of_differences:
        if x <= 4:
            running_total += 1
        elif x >= 6:
            running_total -= 1

    if running_total >= 2:
        return True
    if running_total <= -2:
        return False

    return None


def get_cats_of_romantic_interest(cat):
    """Returns a list of cats, those cats are love interest of the given cat"""
    cats = []
    for inter_cat in cat.all_cats.values():
        if inter_cat.dead or inter_cat.outside or inter_cat.exiled:
            continue
        if inter_cat.ID == cat.ID:
            continue

        if inter_cat.ID not in cat.relationships:
            cat.create_one_relationship(inter_cat)
            if cat.ID not in inter_cat.relationships:
                inter_cat.create_one_relationship(cat)
            continue

        # Extra check to ensure they are potential mates
        if (
            inter_cat.is_potential_mate(cat, for_love_interest=True)
            and cat.relationships[inter_cat.ID].romantic_love > 0
        ):
            cats.append(inter_cat)
    return cats


def get_amount_of_cats_with_relation_value_towards(cat, value, all_cats):
    """
    Looks how many cats have the certain value
    :param cat: cat in question
    :param value: value which has to be reached
    :param all_cats: list of cats which has to be checked
    """

    # collect all true or false if the value is reached for the cat or not
    # later count or sum can be used to get the amount of cats
    # this will be handled like this, because it is easier / shorter to check
    relation_dict = {
        "romantic_love": [],
        "platonic_like": [],
        "dislike": [],
        "admiration": [],
        "comfortable": [],
        "jealousy": [],
        "trust": [],
    }

    for inter_cat in all_cats:
        if cat.ID in inter_cat.relationships:
            relation = inter_cat.relationships[cat.ID]
        else:
            continue

        relation_dict["romantic_love"].append(relation.romantic_love >= value)
        relation_dict["platonic_like"].append(relation.platonic_like >= value)
        relation_dict["dislike"].append(relation.dislike >= value)
        relation_dict["admiration"].append(relation.admiration >= value)
        relation_dict["comfortable"].append(relation.comfortable >= value)
        relation_dict["jealousy"].append(relation.jealousy >= value)
        relation_dict["trust"].append(relation.trust >= value)

    return_dict = {
        "romantic_love": sum(relation_dict["romantic_love"]),
        "platonic_like": sum(relation_dict["platonic_like"]),
        "dislike": sum(relation_dict["dislike"]),
        "admiration": sum(relation_dict["admiration"]),
        "comfortable": sum(relation_dict["comfortable"]),
        "jealousy": sum(relation_dict["jealousy"]),
        "trust": sum(relation_dict["trust"]),
    }

    return return_dict


def filter_relationship_type(
    group: list, filter_types: List[str], event_id: str = None, patrol_leader=None
):
    """
    filters for specific types of relationships between groups of cat objects, returns bool
    :param list[Cat] group: the group of cats to be tested (make sure they're in the correct order (i.e. if testing for
    parent/child, the cat being tested as parent must be index 0)
    :param list[str] filter_types: the relationship types to check for. possible types: "siblings", "mates",
    "mates_with_pl" (PATROL ONLY), "not_mates", "parent/child", "child/parent", "mentor/app", "app/mentor",
    (following tags check if value is over given int) "romantic_int", "platonic_int", "dislike_int", "comfortable_int",
    "jealousy_int", "trust_int"
    :param str event_id: if the event has an ID, include it here
    :param Cat patrol_leader: if you are testing a patrol, ensure you include the self.patrol_leader here
    """
    # keeping this list here just for quick reference of what tags are handled here
    possible_rel_types = [
        "siblings",
        "mates",
        "mates_with_pl",
        "not_mates",
        "parent/child",
        "child/parent",
        "mentor/app",
        "app/mentor",
    ]

    possible_value_types = [
        "romantic",
        "platonic",
        "dislike",
        "comfortable",
        "jealousy",
        "trust",
        "admiration",
    ]

    if "siblings" in filter_types:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        siblings = [test_cat.is_sibling(inter_cat) for inter_cat in testing_cats]
        if not all(siblings):
            return False

    if "mates" in filter_types:
        # first test if more than one cat
        if len(group) == 1:
            return False

        # then if cats don't have the needed number of mates
        if not all(len(i.mate) >= (len(group) - 1) for i in group):
            return False

        # Now the expensive test.  We have to see if everone is mates with each other
        # Hopefully the cheaper tests mean this is only needed on events with a small number of cats
        for x in combinations(group, 2):
            if x[0].ID not in x[1].mate:
                return False

    # check if all cats are mates with p_l (they do not have to be mates with each other)
    if "mates_with_pl" in filter_types:
        # First test if there is more than one cat
        if len(group) == 1:
            return False

        # Check each cat to see if it is mates with the patrol leader
        for cat in group:
            if cat.ID == patrol_leader.ID:
                continue
            if cat.ID not in patrol_leader.mate:
                return False

    # Check if all cats are not mates
    if "not_mates" in filter_types:
        # opposite of mate check
        for x in combinations(group, 2):
            if x[0].ID in x[1].mate:
                return False

    # Check if the cats are in a parent/child relationship
    if "parent/child" in filter_types:
        if patrol_leader:
            if patrol_leader in group:
                group.remove(patrol_leader)
            group.insert(0, patrol_leader)
        # It should be exactly two cats for a "parent/child" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[0].is_parent(group[1]):
            return False

    if "child/parent" in filter_types:
        if patrol_leader:
            if patrol_leader in group:
                group.remove(patrol_leader)
            group.insert(0, patrol_leader)
        # It should be exactly two cats for a "parent/child" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[1].is_parent(group[0]):
            return False

    if "mentor/app" in filter_types:
        if patrol_leader:
            if patrol_leader in group:
                group.remove(patrol_leader)
            group.insert(0, patrol_leader)
        # It should be exactly two cats for a "parent/child" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[1].ID in group[0].apprentice:
            return False

    if "app/mentor" in filter_types:
        if patrol_leader:
            if patrol_leader in group:
                group.remove(patrol_leader)
            group.insert(0, patrol_leader)
        # It should be exactly two cats for a "parent/child" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[0].ID in group[1].apprentice:
            return False

    # Filtering relationship values
    break_loop = False
    for v_type in possible_value_types:
        # first get all tags for current value types
        tags = [constraint for constraint in filter_types if v_type in constraint]

        # If there is not a tag for the current value type, check next one
        if len(tags) == 0:
            continue

            # there should be only one value constraint for each value type
        elif len(tags) > 1:
            print(
                f"ERROR: event {event_id} has multiple relationship constraints for the value {v_type}."
            )
            break_loop = True
            break

        # try to extract the value/threshold from the text
        try:
            threshold = int(tags[0].split("_")[1])
        except:
            print(
                f"ERROR: event {event_id} with the relationship constraint for the value does not {v_type} follow the formatting guidelines."
            )
            break_loop = True
            break

        if threshold > 100:
            print(
                f"ERROR: event {event_id} has a relationship constraint for the value {v_type}, which is higher than the max value of a relationship."
            )
            break_loop = True
            break

        if threshold <= 0:
            print(
                f"ERROR: event {event_id} has a relationship constraint for the value {v_type}, which is lower than the min value of a relationship or 0."
            )
            break_loop = True
            break

        # each cat has to have relationships with this relationship value above the threshold
        fulfilled = True
        for inter_cat in group:
            rel_above_threshold = []
            group_ids = [cat.ID for cat in group]
            relevant_relationships = list(
                filter(
                    lambda rel: rel.cat_to.ID in group_ids
                    and rel.cat_to.ID != inter_cat.ID,
                    list(inter_cat.relationships.values()),
                )
            )

            # get the relationships depending on the current value type + threshold
            if v_type == "romantic":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.romantic_love >= threshold
                ]
            elif v_type == "platonic":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.platonic_like >= threshold
                ]
            elif v_type == "dislike":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.dislike >= threshold
                ]
            elif v_type == "comfortable":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.comfortable >= threshold
                ]
            elif v_type == "jealousy":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.jealousy >= threshold
                ]
            elif v_type == "trust":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.trust >= threshold
                ]
            elif v_type == "admiration":
                rel_above_threshold = [
                    i for i in relevant_relationships if i.admiration >= threshold
                ]

            # if the lengths are not equal, one cat has not the relationship value which is needed to another cat of
            # the event
            if len(rel_above_threshold) + 1 != len(group):
                fulfilled = False
                break

        if not fulfilled:
            break_loop = True
            break

    # if break is used in the loop, the condition are not fulfilled
    # and this event should not be added to the filtered list
    if break_loop:
        return False

    return True


def gather_cat_objects(
    Cat, abbr_list: List[str], event, stat_cat=None, extra_cat=None
) -> list:
    """
    gathers cat objects from list of abbreviations used within an event format block
    :param Cat Cat: Cat class
    :param list[str] abbr_list: The list of abbreviations, supports "m_c", "r_c", "p_l", "s_c", "app1", "app2", "clan",
    "some_clan", "patrol", "multi", "n_c{index}"
    :param event: the controlling class of the event (e.g. Patrol, HandleShortEvents), default None
    :param Cat stat_cat: if passing the Patrol class, must include stat_cat separately
    :param Cat extra_cat: if not passing an event class, include the single affected cat object here. If you are not
    passing a full event class, then be aware that you can only include "m_c" as a cat abbreviation in your rel block.
    The other cat abbreviations will not work.
    :return: list of cat objects
    """
    out_set = set()

    for abbr in abbr_list:
        if abbr == "m_c":
            if extra_cat:
                out_set.add(extra_cat)
            else:
                out_set.add(event.main_cat)
        if abbr == "r_c":
            out_set.add(event.random_cat)
        elif abbr == "p_l":
            out_set.add(event.patrol_leader)
        elif abbr == "s_c":
            out_set.add(stat_cat)
        elif abbr == "app1" and len(event.patrol_apprentices) >= 1:
            out_set.add(event.patrol_apprentices[0])
        elif abbr == "app2" and len(event.patrol_apprentices) >= 2:
            out_set.add(event.patrol_apprentices[1])
        elif abbr == "clan":
            out_set.update(
                [x for x in Cat.all_cats_list if not (x.dead or x.outside or x.exiled)]
            )
        elif abbr == "some_clan":  # 1 / 8 of clan cats are affected
            clan_cats = [
                x for x in Cat.all_cats_list if not (x.dead or x.outside or x.exiled)
            ]
            out_set.update(
                sample(clan_cats, randint(1, max(1, round(len(clan_cats) / 8))))
            )
        elif abbr == "patrol":
            out_set.update(event.patrol_cats)
        elif abbr == "multi":
            cat_num = randint(1, max(1, len(event.patrol_cats) - 1))
            out_set.update(sample(event.patrol_cats, cat_num))
        elif re.match(r"n_c:[0-9]+", abbr):
            index = re.match(r"n_c:([0-9]+)", abbr).group(1)
            index = int(index)
            if index < len(event.new_cats):
                out_set.update(event.new_cats[index])

    return list(out_set)


def unpack_rel_block(
    Cat, relationship_effects: List[dict], event=None, stat_cat=None, extra_cat=None
):
    """
    Unpacks the info from the relationship effect block used in patrol and moon events, then adjusts rel values
    accordingly.

    :param Cat Cat: Cat class
    :param list[dict] relationship_effects: the relationship effect block
    :param event: the controlling class of the event (e.g. Patrol, HandleShortEvents), default None
    :param Cat stat_cat: if passing the Patrol class, must include stat_cat separately
    :param Cat extra_cat: if not passing an event class, include the single affected cat object here. If you are not passing a full event class, then be aware that you can only include "m_c" as a cat abbreviation in your rel block.  The other cat abbreviations will not work.
    """
    possible_values = (
        "romantic",
        "platonic",
        "dislike",
        "comfort",
        "jealous",
        "trust",
        "respect",
    )

    for block in relationship_effects:
        cats_from = block.get("cats_from", [])
        cats_to = block.get("cats_to", [])
        amount = block.get("amount")
        values = [x for x in block.get("values", ()) if x in possible_values]

        # Gather actual cat objects:
        cats_from_ob = gather_cat_objects(Cat, cats_from, event, stat_cat, extra_cat)
        cats_to_ob = gather_cat_objects(Cat, cats_to, event, stat_cat, extra_cat)

        # Remove any "None" that might have snuck in
        if None in cats_from_ob:
            cats_from_ob.remove(None)
        if None in cats_to_ob:
            cats_to_ob.remove(None)

        # Check to see if value block
        if not (cats_to_ob and cats_from_ob and values and isinstance(amount, int)):
            print(f"Relationship block incorrectly formatted: {block}")
            continue

        positive = False

        # grabbing values
        romantic_love = 0
        platonic_like = 0
        dislike = 0
        comfortable = 0
        jealousy = 0
        admiration = 0
        trust = 0
        if "romantic" in values:
            romantic_love = amount
            if amount > 0:
                positive = True
        if "platonic" in values:
            platonic_like = amount
            if amount > 0:
                positive = True
        if "dislike" in values:
            dislike = amount
            if amount < 0:
                positive = True
        if "comfort" in values:
            comfortable = amount
            if amount > 0:
                positive = True
        if "jealous" in values:
            jealousy = amount
            if amount < 0:
                positive = True
        if "trust" in values:
            trust = amount
            if amount > 0:
                positive = True
        if "respect" in values:
            admiration = amount
            if amount > 0:
                positive = True

        if positive:
            effect = f" (positive effect)"
        else:
            effect = f" (negative effect)"

        # Get log
        log1 = None
        log2 = None
        if block.get("log"):
            log = block.get("log")
            if isinstance(log, str):
                log1 = log
            elif isinstance(log, list):
                if len(log) >= 2:
                    log1 = log[0]
                    log2 = log[1]
                elif len(log) == 1:
                    log1 = log[0]
            else:
                print(f"something is wrong with relationship log: {log}")

        if not log1:
            if hasattr(event, "text"):
                try:
                    log1 = event.text + effect
                except AttributeError:
                    print(
                        f"WARNING: event changed relationships but did not create a relationship log"
                    )
            else:
                log1 = "These cats recently interacted." + effect
        if not log2:
            if hasattr(event, "text"):
                try:
                    log2 = event.text + effect
                except AttributeError:
                    print(
                        f"WARNING: event changed relationships but did not create a relationship log"
                    )
            else:
                log2 = f"These cats recently interacted." + effect

        change_relationship_values(
            cats_to_ob,
            cats_from_ob,
            romantic_love,
            platonic_like,
            dislike,
            admiration,
            comfortable,
            jealousy,
            trust,
            log=log1,
        )

        if block.get("mutual"):
            change_relationship_values(
                cats_from_ob,
                cats_to_ob,
                romantic_love,
                platonic_like,
                dislike,
                admiration,
                comfortable,
                jealousy,
                trust,
                log=log2,
            )


def change_relationship_values(
    cats_to: list,
    cats_from: list,
    romantic_love: int = 0,
    platonic_like: int = 0,
    dislike: int = 0,
    admiration: int = 0,
    comfortable: int = 0,
    jealousy: int = 0,
    trust: int = 0,
    auto_romance: bool = False,
    log: str = None,
):
    """
    changes relationship values according to the parameters.

    :param list[Cat] cats_from: list of cat objects whose rel values will be affected
    (e.g. cat_from loses trust in cat_to)
    :param list[Cat] cats_to: list of cats objects who are the target of that rel value
    (e.g. cat_from loses trust in cat_to)
    :param int romantic_love: amount to change romantic, default 0
    :param int platonic_like: amount to change platonic, default 0
    :param int dislike: amount to change dislike, default 0
    :param int admiration: amount to change admiration (respect), default 0
    :param int comfortable: amount to change comfort, default 0
    :param int jealousy: amount to change jealousy, default 0
    :param int trust: amount to change trust, default 0
    :param bool auto_romance: if the cat_from already has romantic value with cat_to, then the platonic_like param value
    will also be applied to romantic, default False
    :param str log: the string to append to the relationship log of cats involved
    """

    # This is just for test prints - DON'T DELETE - you can use this to test if relationships are changing
    """changed = False
    if romantic_love == 0 and platonic_like == 0 and dislike == 0 and admiration == 0 and \
            comfortable == 0 and jealousy == 0 and trust == 0:
        changed = False
    else:
        changed = True"""

    # pick out the correct cats
    for single_cat_from in cats_from:
        for single_cat_to in cats_to:
            # make sure we aren't trying to change a cat's relationship with themself
            if single_cat_from == single_cat_to:
                continue

            # if the cats don't know each other, start a new relationship
            if single_cat_to.ID not in single_cat_from.relationships:
                single_cat_from.create_one_relationship(single_cat_to)

            rel = single_cat_from.relationships[single_cat_to.ID]

            # here we just double-check that the cats are allowed to be romantic with each other
            if (
                single_cat_from.is_potential_mate(single_cat_to, for_love_interest=True)
                or single_cat_to.ID in single_cat_from.mate
            ):
                # if cat already has romantic feelings then automatically increase romantic feelings
                # when platonic feelings would increase
                if rel.romantic_love > 0 and auto_romance:
                    romantic_love = platonic_like

                # now gain the romance
                rel.romantic_love += romantic_love

            # gain other rel values
            rel.platonic_like += platonic_like
            rel.dislike += dislike
            rel.admiration += admiration
            rel.comfortable += comfortable
            rel.jealousy += jealousy
            rel.trust += trust

            # for testing purposes - DON'T DELETE - you can use this to test if relationships are changing
            """
            print(str(single_cat_from.name) + " gained relationship with " + str(rel.cat_to.name) + ": " +
                  "Romantic: " + str(romantic_love) +
                  " /Platonic: " + str(platonic_like) +
                  " /Dislike: " + str(dislike) +
                  " /Respect: " + str(admiration) +
                  " /Comfort: " + str(comfortable) +
                  " /Jealousy: " + str(jealousy) +
                  " /Trust: " + str(trust)) if changed else print("No relationship change")"""

            if log and isinstance(log, str):
                if single_cat_to.moons <= 1:
                    log_text = (
                        log
                        + f"- {single_cat_to.name} was {single_cat_to.moons} moon old"
                    )
                    if log_text not in rel.log:
                        rel.log.append(log_text)
                else:
                    log_text = (
                        log
                        + f"- {single_cat_to.name} was {single_cat_to.moons} moons old"
                    )
                    if log_text not in rel.log:
                        rel.log.append(log_text)


# ---------------------------------------------------------------------------- #
#                               Text Adjust                                    #
# ---------------------------------------------------------------------------- #


def get_leader_life_notice() -> str:
    """
    Returns a string specifying how many lives the leader has left or notifying of the leader's full death
    """
    text = ""

    lives = game.clan.leader_lives

    if lives > 0:
        text = f"The leader has {int(lives)} lives left."
    elif lives <= 0:
        if game.clan.instructor.df is False:
            text = "The leader has no lives left and has travelled to StarClan."
        else:
            text = "The leader has no lives left and has travelled to the Dark Forest."

    return text


def get_other_clan_relation(relation):
    """
    converts int value into string relation and returns string: "hostile", "neutral", or "ally"
    :param relation: the other_clan.relations value
    """

    if int(relation) >= 17:
        return "ally"
    elif 7 < int(relation) < 17:
        return "neutral"
    elif int(relation) <= 7:
        return "hostile"


def pronoun_repl(m, cat_pronouns_dict, raise_exception=False):
    """Helper function for add_pronouns. If raise_exception is
    False, any error in pronoun formatting will not raise an
    exception, and will use a simple replacement "error" """

    # Add protection about the "insert" sometimes used
    if m.group(0) == "{insert}":
        return m.group(0)

    inner_details = m.group(1).split("/")

    try:
        d = cat_pronouns_dict[inner_details[1]][1]
        if inner_details[0].upper() == "PRONOUN":
            pro = d[inner_details[2]]
            if inner_details[-1] == "CAP":
                pro = pro.capitalize()
            return pro
        elif inner_details[0].upper() == "VERB":
            return inner_details[d["conju"] + 1]

        if raise_exception:
            raise KeyError(
                f"Pronoun tag: {m.group(1)} is not properly"
                "indicated as a PRONOUN or VERB tag."
            )

        print("Failed to find pronoun:", m.group(1))
        return "error1"
    except (KeyError, IndexError) as e:
        if raise_exception:
            raise

        logger.exception("Failed to find pronoun: " + m.group(1))
        print("Failed to find pronoun:", m.group(1))
        return "error2"


def name_repl(m, cat_dict):
    """Name replacement"""
    return cat_dict[m.group(0)][0]


def process_text(text, cat_dict, raise_exception=False):
    """Add the correct name and pronouns into a string."""
    adjust_text = re.sub(
        r"\{(.*?)\}", lambda x: pronoun_repl(x, cat_dict, raise_exception), text
    )

    name_patterns = [r"(?<!\{)" + re.escape(l) + r"(?!\})" for l in cat_dict]
    adjust_text = re.sub(
        "|".join(name_patterns), lambda x: name_repl(x, cat_dict), adjust_text
    )
    return adjust_text


def adjust_list_text(list_of_items) -> str:
    """
    returns the list in correct grammar format (i.e. item1, item2, item3 and item4)
    this works with any number of items
    :param list_of_items: the list of items you want converted
    :return: the new string
    """
    if len(list_of_items) == 1:
        insert = f"{list_of_items[0]}"
    elif len(list_of_items) == 2:
        insert = f"{list_of_items[0]} and {list_of_items[1]}"
    else:
        item_line = ", ".join(list_of_items[:-1])
        insert = f"{item_line}, and {list_of_items[-1]}"

    return insert


def adjust_prey_abbr(patrol_text):
    """
    checks for prey abbreviations and returns adjusted text
    """
    for abbr in PREY_LISTS["abbreviations"]:
        if abbr in patrol_text:
            chosen_list = PREY_LISTS["abbreviations"].get(abbr)
            chosen_list = PREY_LISTS[chosen_list]
            prey = choice(chosen_list)
            patrol_text = patrol_text.replace(abbr, prey)

    return patrol_text


def get_special_snippet_list(
    chosen_list, amount, sense_groups=None, return_string=True
):
    """
    function to grab items from various lists in snippet_collections.json
    list options are:
    -prophecy_list - sense_groups = sight, sound, smell, emotional, touch
    -omen_list - sense_groups = sight, sound, smell, emotional, touch
    -clair_list  - sense_groups = sound, smell, emotional, touch, taste
    -dream_list (this list doesn't have sense_groups)
    -story_list (this list doesn't have sense_groups)
    :param chosen_list: pick which list you want to grab from
    :param amount: the amount of items you want the returned list to contain
    :param sense_groups: list which senses you want the snippets to correspond with:
     "touch", "sight", "emotional", "sound", "smell" are the options. Default is None, if left as this then all senses
     will be included (if the list doesn't have sense categories, then leave as None)
    :param return_string: if True then the function will format the snippet list with appropriate commas and 'ands'.
    This will work with any number of items. If set to True, then the function will return a string instead of a list.
    (i.e. ["hate", "fear", "dread"] becomes "hate, fear, and dread") - Default is True
    :return: a list of the chosen items from chosen_list or a formatted string if format is True
    """
    biome = game.clan.biome.casefold()

    # these lists don't get sense specific snippets, so is handled first
    if chosen_list in ["dream_list", "story_list"]:
        if (
            chosen_list == "story_list"
        ):  # story list has some biome specific things to collect
            snippets = SNIPPETS[chosen_list]["general"]
            snippets.extend(SNIPPETS[chosen_list][biome])
        elif (
            chosen_list == "clair_list"
        ):  # the clair list also pulls from the dream list
            snippets = SNIPPETS[chosen_list]
            snippets.extend(SNIPPETS["dream_list"])
        else:  # the dream list just gets the one
            snippets = SNIPPETS[chosen_list]

    else:
        # if no sense groups were specified, use all of them
        if not sense_groups:
            if chosen_list == "clair_list":
                sense_groups = ["taste", "sound", "smell", "emotional", "touch"]
            else:
                sense_groups = ["sight", "sound", "smell", "emotional", "touch"]

        # find the correct lists and compile them
        snippets = []
        for sense in sense_groups:
            snippet_group = SNIPPETS[chosen_list][sense]
            snippets.extend(snippet_group["general"])
            snippets.extend(snippet_group[biome])

    # now choose a unique snippet from each snip list
    unique_snippets = []
    for snip_list in snippets:
        unique_snippets.append(choice(snip_list))

    # pick out our final snippets
    final_snippets = sample(unique_snippets, k=amount)

    if return_string:
        text = adjust_list_text(final_snippets)
        return text
    else:
        return final_snippets


def find_special_list_types(text):
    """
    purely to identify which senses are being called for by a snippet abbreviation
    returns adjusted text, sense list, list type, and cat_tag
    """
    senses = []
    list_text = None
    list_type = None
    words = text.split(" ")
    for bit in words:
        if "_list" in bit:
            list_text = bit
            # just getting rid of pesky punctuation
            list_text = list_text.replace(".", "")
            list_text = list_text.replace(",", "")
            break

    if not list_text:
        return text, None, None, None

    parts_of_tag = list_text.split("/")

    try:
        cat_tag = parts_of_tag[1]
    except IndexError:
        cat_tag = None

    if "omen_list" in list_text:
        list_type = "omen_list"
    elif "prophecy_list" in list_text:
        list_type = "prophecy_list"
    elif "dream_list" in list_text:
        list_type = "dream_list"
    elif "clair_list" in list_text:
        list_type = "clair_list"
    elif "story_list" in list_text:
        list_type = "story_list"

    if "_sight" in list_text:
        senses.append("sight")
    if "_sound" in list_text:
        senses.append("sound")
    if "_smell" in list_text:
        senses.append("smell")
    if "_emotional" in list_text:
        senses.append("emotional")
    if "_touch" in list_text:
        senses.append("touch")
    if "_taste" in list_text:
        senses.append("taste")

    text = text.replace(list_text, list_type)

    return text, senses, list_type, cat_tag


def history_text_adjust(text, other_clan_name, clan, other_cat_rc=None):
    """
    we want to handle history text on its own because it needs to preserve the pronoun tags and cat abbreviations.
    this is so that future pronoun changes or name changes will continue to be reflected in history
    """
    vowels = ["A", "E", "I", "O", "U"]

    if "o_c_n" in text:
        pos = 0
        for x in range(text.count("o_c_n")):
            if "o_c_n" in text:
                for y in vowels:
                    if str(other_clan_name).startswith(y):
                        modify = text.split()
                        if "o_c_n" in modify:
                            pos = modify.index("o_c_n")
                        if "o_c_n's" in modify:
                            pos = modify.index("o_c_n's")
                        if "o_c_n." in modify:
                            pos = modify.index("o_c_n.")
                        if modify[pos - 1] == "a":
                            modify.remove("a")
                            modify.insert(pos - 1, "an")
                        text = " ".join(modify)
                        break

        text = text.replace("o_c_n", str(other_clan_name))

    if "c_n" in text:
        text = text.replace("c_n", clan.name)
    if "r_c" in text and other_cat_rc:
        text = selective_replace(text, "r_c", str(other_cat_rc.name))
    return text


def selective_replace(text, pattern, replacement):
    i = 0
    while i < len(text):
        index = text.find(pattern, i)
        if index == -1:
            break
        start_brace = text.rfind("{", 0, index)
        end_brace = text.find("}", index)
        if start_brace != -1 and end_brace != -1 and start_brace < index < end_brace:
            i = index + len(pattern)
        else:
            text = text[:index] + replacement + text[index + len(pattern) :]
            i = index + len(replacement)

    return text


def ongoing_event_text_adjust(Cat, text, clan=None, other_clan_name=None):
    """
    This function is for adjusting the text of ongoing events
    :param Cat: the cat class
    :param text: the text to be adjusted
    :param clan: the name of the clan
    :param other_clan_name: the other Clan's name if another Clan is involved
    """
    cat_dict = {}
    if "lead_name" in text:
        kitty = Cat.fetch_cat(game.clan.leader)
        cat_dict["lead_name"] = (str(kitty.name), choice(kitty.pronouns))
    if "dep_name" in text:
        kitty = Cat.fetch_cat(game.clan.deputy)
        cat_dict["dep_name"] = (str(kitty.name), choice(kitty.pronouns))
    if "med_name" in text:
        kitty = choice(get_alive_status_cats(Cat, ["medicine cat"], working=True))
        cat_dict["med_name"] = (str(kitty.name), choice(kitty.pronouns))

    if cat_dict:
        text = process_text(text, cat_dict)

    if other_clan_name:
        text = text.replace("o_c_n", other_clan_name)
    if clan:
        clan_name = str(clan.name)
    else:
        if game.clan is None:
            clan_name = game.switches["clan_list"][0]
        else:
            clan_name = str(game.clan.name)

    text = text.replace("c_n", clan_name + "Clan")

    return text


def event_text_adjust(
    Cat,
    text,
    *,
    patrol_leader=None,
    main_cat=None,
    random_cat=None,
    stat_cat=None,
    victim_cat=None,
    patrol_cats: list = None,
    patrol_apprentices: list = None,
    new_cats: list = None,
    multi_cats: list = None,
    clan=None,
    other_clan=None,
    chosen_herb: str = None,
):
    """
    handles finding abbreviations in the text and replacing them appropriately, returns the adjusted text
    :param Cat Cat: always pass the Cat class
    :param str text: the text being adjusted
    :param Cat patrol_leader: Cat object for patrol_leader (p_l), if present
    :param Cat main_cat: Cat object for main_cat (m_c), if present
    :param Cat random_cat: Cat object for random_cat (r_c), if present
    :param Cat stat_cat: Cat object for stat_cat (s_c), if present
    :param Cat victim_cat: Cat object for victim_cat (mur_c), if present
    :param list[Cat] patrol_cats: List of Cat objects for cats in patrol, if present
    :param list[Cat] patrol_apprentices: List of Cat objects for patrol_apprentices (app#), if present
    :param list[Cat] new_cats: List of Cat objects for new_cats (n_c:index), if present
    :param list[Cat] multi_cats: List of Cat objects for multi_cat (multi_cat), if present
    :param Clan clan: pass game.clan
    :param OtherClan other_clan: OtherClan object for other_clan (o_c_n), if present
    :param str chosen_herb: string of chosen_herb (chosen_herb), if present
    """
    vowels = ["A", "E", "I", "O", "U"]

    if not text:
        text = "This should not appear, report as a bug please! Tried to adjust the text, but no text was provided."
        print("WARNING: Tried to adjust text, but no text was provided.")

    replace_dict = {}

    # special lists - this needs to happen first for pronoun tag reasons
    text, senses, list_type, cat_tag = find_special_list_types(text)
    if list_type:
        sign_list = get_special_snippet_list(
            list_type, amount=randint(1, 3), sense_groups=senses
        )
        text = text.replace(list_type, str(sign_list))
        if cat_tag:
            text = text.replace("cat_tag", cat_tag)

    # main_cat
    if "m_c" in text:
        if main_cat:
            replace_dict["m_c"] = (str(main_cat.name), choice(main_cat.pronouns))

    # patrol_lead
    if "p_l" in text:
        if patrol_leader:
            replace_dict["p_l"] = (
                str(patrol_leader.name),
                choice(patrol_leader.pronouns),
            )

    # random_cat
    if "r_c" in text:
        if random_cat:
            replace_dict["r_c"] = (str(random_cat.name), get_pronouns(random_cat))

    # stat cat
    if "s_c" in text:
        if stat_cat:
            replace_dict["s_c"] = (str(stat_cat.name), get_pronouns(stat_cat))

    # other_cats
    if patrol_cats:
        other_cats = [
            i
            for i in patrol_cats
            if i not in [patrol_leader, random_cat, patrol_apprentices]
        ]
        other_cat_abbr = ["o_c1", "o_c2", "o_c3", "o_c4"]
        for i, abbr in enumerate(other_cat_abbr):
            if abbr not in text:
                continue
            if len(other_cats) > i:
                replace_dict[abbr] = (
                    str(other_cats[i].name),
                    choice(other_cats[i].pronouns),
                )

    # patrol_apprentices
    app_abbr = ["app1", "app2", "app3", "app4", "app5", "app6"]
    for i, abbr in enumerate(app_abbr):
        if abbr not in text:
            continue
        if len(patrol_apprentices) > i:
            replace_dict[abbr] = (
                str(patrol_apprentices[i].name),
                choice(patrol_apprentices[i].pronouns),
            )

    # new_cats (include pre version)
    if "n_c" in text:
        for i, cat_list in enumerate(new_cats):
            if len(new_cats) > 1:
                pronoun = Cat.default_pronouns[0]  # They/them for multiple cats
            else:
                pronoun = choice(cat_list[0].pronouns)

            replace_dict[f"n_c:{i}"] = (str(cat_list[0].name), pronoun)
            replace_dict[f"n_c_pre:{i}"] = (str(cat_list[0].name.prefix), pronoun)

    # mur_c (murdered cat for reveals)
    if "mur_c" in text:
        replace_dict["mur_c"] = (str(victim_cat.name), get_pronouns(victim_cat))

    # lead_name
    if "lead_name" in text:
        leader = Cat.fetch_cat(game.clan.leader)
        replace_dict["lead_name"] = (str(leader.name), choice(leader.pronouns))

    # dep_name
    if "dep_name" in text:
        deputy = Cat.fetch_cat(game.clan.deputy)
        replace_dict["dep_name"] = (str(deputy.name), choice(deputy.pronouns))

    # med_name
    if "med_name" in text:
        med = choice(get_alive_status_cats(Cat, ["medicine cat"], working=True))
        replace_dict["med_name"] = (str(med.name), choice(med.pronouns))

    # assign all names and pronouns
    if replace_dict:
        text = process_text(text, replace_dict)

    # multi_cat
    if "multi_cat" in text:
        name_list = []
        for _cat in multi_cats:
            name_list.append(str(_cat.name))
        list_text = adjust_list_text(name_list)
        text = text.replace("multi_cat", list_text)

    # other_clan_name
    if "o_c_n" in text:
        other_clan_name = other_clan.name
        pos = 0
        for x in range(text.count("o_c_n")):
            if "o_c_n" in text:
                for y in vowels:
                    if str(other_clan_name).startswith(y):
                        modify = text.split()
                        if "o_c_n" in modify:
                            pos = modify.index("o_c_n")
                        if "o_c_n's" in modify:
                            pos = modify.index("o_c_n's")
                        if "o_c_n." in modify:
                            pos = modify.index("o_c_n.")
                        if modify[pos - 1] == "a":
                            modify.remove("a")
                            modify.insert(pos - 1, "an")
                        text = " ".join(modify)
                        break

        text = text.replace("o_c_n", str(other_clan_name) + "Clan")

    # clan_name
    if "c_n" in text:
        try:
            clan_name = clan.name
        except AttributeError:
            clan_name = game.switches["clan_list"][0]

        pos = 0
        for x in range(text.count("c_n")):
            if "c_n" in text:
                for y in vowels:
                    if str(clan_name).startswith(y):
                        modify = text.split()
                        if "c_n" in modify:
                            pos = modify.index("c_n")
                        if "c_n's" in modify:
                            pos = modify.index("c_n's")
                        if "c_n." in modify:
                            pos = modify.index("c_n.")
                        if modify[pos - 1] == "a":
                            modify.remove("a")
                            modify.insert(pos - 1, "an")
                        text = " ".join(modify)
                        break

        text = text.replace("c_n", str(clan_name) + "Clan")

    # prey lists
    text = adjust_prey_abbr(text)



    # acc_plural (only works for main_cat's acc)
    if "acc_plural" in text:
        text = text.replace(
            "acc_plural", str(ACC_DISPLAY[main_cat.pelt.accessory]["plural"])
        )

    # acc_singular (only works for main_cat's acc)
    if "acc_singular" in text:
        text = text.replace(
            "acc_singular", str(ACC_DISPLAY[main_cat.pelt.accessory]["singular"])
        )

    if "given_herb" in text:
        if "_" in chosen_herb:
            chosen_herb = chosen_herb.replace("_", " ")
        text = text.replace("given_herb", str(chosen_herb))

    return text


def leader_ceremony_text_adjust(
    Cat,
    text,
    leader,
    life_giver=None,
    virtue=None,
    extra_lives=None,
):
    """
    used to adjust the text for leader ceremonies
    """
    replace_dict = {
        "m_c_star": (str(leader.name.prefix + "star"), choice(leader.pronouns)),
        "m_c": (str(leader.name.prefix + leader.name.suffix), choice(leader.pronouns)),
    }

    if life_giver:
        replace_dict["r_c"] = (
            str(Cat.fetch_cat(life_giver).name),
            choice(Cat.fetch_cat(life_giver).pronouns),
        )

    text = process_text(text, replace_dict)

    if virtue:
        virtue = process_text(virtue, replace_dict)
        text = text.replace("[virtue]", virtue)

    if extra_lives:
        text = text.replace("[life_num]", str(extra_lives))

    text = text.replace("c_n", str(game.clan.name) + "Clan")

    return text


def ceremony_text_adjust(
    Cat,
    text,
    cat,
    old_name=None,
    dead_mentor=None,
    mentor=None,
    previous_alive_mentor=None,
    random_honor=None,
    living_parents=(),
    dead_parents=(),
):
    clanname = str(game.clan.name + "Clan")

    random_honor = random_honor
    random_living_parent = None
    random_dead_parent = None

    adjust_text = text

    cat_dict = {
        "m_c": (
            (str(cat.name), choice(cat.pronouns)) if cat else ("cat_placeholder", None)
        ),
        "(mentor)": (
            (str(mentor.name), choice(mentor.pronouns))
            if mentor
            else ("mentor_placeholder", None)
        ),
        "(deadmentor)": (
            (str(dead_mentor.name), get_pronouns(dead_mentor))
            if dead_mentor
            else ("dead_mentor_name", None)
        ),
        "(previous_mentor)": (
            (str(previous_alive_mentor.name), choice(previous_alive_mentor.pronouns))
            if previous_alive_mentor
            else ("previous_mentor_name", None)
        ),
        "l_n": (
            (str(game.clan.leader.name), choice(game.clan.leader.pronouns))
            if game.clan.leader
            else ("leader_name", None)
        ),
        "c_n": (clanname, None),
    }

    if old_name:
        cat_dict["(old_name)"] = (old_name, None)

    if random_honor:
        cat_dict["r_h"] = (random_honor, None)

    if "p1" in adjust_text and "p2" in adjust_text and len(living_parents) >= 2:
        cat_dict["p1"] = (
            str(living_parents[0].name),
            choice(living_parents[0].pronouns),
        )
        cat_dict["p2"] = (
            str(living_parents[1].name),
            choice(living_parents[1].pronouns),
        )
    elif living_parents:
        random_living_parent = choice(living_parents)
        cat_dict["p1"] = (
            str(random_living_parent.name),
            choice(random_living_parent.pronouns),
        )
        cat_dict["p2"] = (
            str(random_living_parent.name),
            choice(random_living_parent.pronouns),
        )

    if (
        "dead_par1" in adjust_text
        and "dead_par2" in adjust_text
        and len(dead_parents) >= 2
    ):
        cat_dict["dead_par1"] = (
            str(dead_parents[0].name),
            get_pronouns(dead_parents[0]),
        )
        cat_dict["dead_par2"] = (
            str(dead_parents[1].name),
            get_pronouns(dead_parents[1]),
        )
    elif dead_parents:
        random_dead_parent = choice(dead_parents)
        cat_dict["dead_par1"] = (
            str(random_dead_parent.name),
            get_pronouns(random_dead_parent),
        )
        cat_dict["dead_par2"] = (
            str(random_dead_parent.name),
            get_pronouns(random_dead_parent),
        )

    adjust_text = process_text(adjust_text, cat_dict)

    return adjust_text, random_living_parent, random_dead_parent


def get_pronouns(Cat):
    """Get a cat's pronoun even if the cat has faded to prevent crashes (use gender-neutral pronouns when the cat has faded)"""
    if Cat.pronouns == []:
        return {
            "subject": "they",
            "object": "them",
            "poss": "their",
            "inposs": "theirs",
            "self": "themself",
            "conju": 1,
        }
    else:
        return choice(Cat.pronouns)


def shorten_text_to_fit(
    name, length_limit, font_size=None, font_type="resources/fonts/NotoSans-Medium.ttf"
):
    length_limit = length_limit * scripts.game_structure.screen_settings.screen_scale
    if font_size is None:
        font_size = 15
    font_size = floor(font_size * scripts.game_structure.screen_settings.screen_scale)

    if font_type == "clangen":
        font_type = "resources/fonts/clangen.ttf"
    # Create the font object
    font = pygame.font.Font(font_type, font_size)

    # Add dynamic name lengths by checking the actual width of the text
    total_width = 0
    short_name = ""
    ellipsis_width = font.size("...")[0]
    for index, character in enumerate(name):
        char_width = font.size(character)[0]

        # Check if the current character is the last one and its width is less than or equal to ellipsis_width
        if index == len(name) - 1 and char_width <= ellipsis_width:
            short_name += character
        else:
            total_width += char_width
            if total_width + ellipsis_width > length_limit:
                break
            short_name += character

    # If the name was truncated, add "..."
    if len(short_name) < len(name):
        short_name += "..."

    return short_name


# ---------------------------------------------------------------------------- #
#                                    Sprites                                   #
# ---------------------------------------------------------------------------- #


def ui_scale(rect: pygame.Rect):
    """
    Scales a pygame.Rect appropriately for the UI scaling currently in use.
    :param rect: a pygame.Rect
    :return: the same pygame.Rect, scaled for the current UI.
    """
    # offset can be negative to allow for correct anchoring
    rect[0] = floor(rect[0] * scripts.game_structure.screen_settings.screen_scale)
    rect[1] = floor(rect[1] * scripts.game_structure.screen_settings.screen_scale)
    # if the dimensions are negative, it's dynamically scaled, ignore
    rect[2] = (
        floor(rect[2] * scripts.game_structure.screen_settings.screen_scale)
        if rect[2] > 0
        else rect[2]
    )
    rect[3] = (
        floor(rect[3] * scripts.game_structure.screen_settings.screen_scale)
        if rect[3] > 0
        else rect[3]
    )

    return rect


def ui_scale_dimensions(dim: Tuple[int, int]):
    """
    Use to scale the dimensions of an item - WILL IGNORE NEGATIVE VALUES
    :param dim: The dimensions to scale
    :return: The scaled dimensions
    """
    return (
        floor(dim[0] * scripts.game_structure.screen_settings.screen_scale)
        if dim[0] > 0
        else dim[0],
        floor(dim[1] * scripts.game_structure.screen_settings.screen_scale)
        if dim[1] > 0
        else dim[1],
    )


def ui_scale_offset(coords: Tuple[int, int]):
    """
    Use to scale the offset of an item (i.e. the first 2 values of a pygame.Rect).
    Not to be confused with ui_scale_blit.
    :param coords: The coordinates to scale
    :return: The scaled coordinates
    """
    return (
        floor(coords[0] * scripts.game_structure.screen_settings.screen_scale),
        floor(coords[1] * scripts.game_structure.screen_settings.screen_scale),
    )


def ui_scale_value(val: int):
    """
    Use to scale a single value according to the UI scale. If you need this one,
    you're probably doing something unusual. Try to avoid where possible.
    :param val: The value to scale
    :return: The scaled value
    """
    return floor(val * scripts.game_structure.screen_settings.screen_scale)


def ui_scale_blit(coords: Tuple[int, int]):
    """
    Use to scale WHERE to blit an item, not the SIZE of it. (0, 0) is the top left corner of the pygame_gui managed window,
    this adds the offset from fullscreen etc. to make it blit in the right place. Not to be confused with ui_scale_offset.
    :param coords: The coordinates to blit to
    :return: The scaled, correctly offset coordinates to blit to.
    """
    return floor(
        coords[0] * scripts.game_structure.screen_settings.screen_scale
        + scripts.game_structure.screen_settings.offset[0]
    ), floor(
        coords[1] * scripts.game_structure.screen_settings.screen_scale
        + scripts.game_structure.screen_settings.offset[1]
    )


def update_sprite(cat):
    # First, check if the cat is faded.
    if cat.faded:
        # Don't update the sprite if the cat is faded.
        return

    # apply
    cat.sprite = generate_sprite(cat)
    # update class dictionary
    cat.all_cats[cat.ID] = cat


def clan_symbol_sprite(clan, return_string=False, force_light=False):
    """
    returns the clan symbol for the given clan_name, if no symbol exists then random symbol is chosen
    :param clan: the clan object
    :param return_string: default False, set True if the sprite name string is required rather than the sprite image
    :param force_light: Set true if you want this sprite to override the dark/light mode changes with the light sprite
    """
    clan_name = clan.name
    if clan.chosen_symbol:
        if return_string:
            return clan.chosen_symbol
        else:
            if game.settings["dark mode"] and not force_light:
                return sprites.dark_mode_symbol(sprites.sprites[clan.chosen_symbol])
            else:
                return sprites.sprites[clan.chosen_symbol]
    else:
        possible_sprites = []
        for sprite in sprites.clan_symbols:
            name = sprite.strip("1234567890")
            if f"symbol{clan_name.upper()}" == name:
                possible_sprites.append(sprite)
        if return_string:  # returns the str of the symbol
            if possible_sprites:
                return choice(possible_sprites)
            else:
                # give random symbol if no matching symbol exists
                print(
                    f"WARNING: attempted to return symbol string, but there's no clan symbol for {clan_name.upper()}.  Random symbol string returned."
                )
                return f"{choice(sprites.clan_symbols)}"

        # returns the actual sprite of the symbol
        if possible_sprites:
            if game.settings["dark mode"] and not force_light:
                return sprites.dark_mode_symbol(
                    sprites.sprites[choice(possible_sprites)]
                )
            else:
                return sprites.sprites[choice(possible_sprites)]
        else:
            # give random symbol if no matching symbol exists
            print(
                f"WARNING: attempted to return symbol sprite, but there's no clan symbol for {clan_name.upper()}.  Random symbol sprite returned."
            )
            return sprites.dark_mode_symbol(
                sprites.sprites[f"{choice(sprites.clan_symbols)}"]
            )


def generate_sprite(
    cat,
    life_state=None,
    scars_hidden=False,
    acc_hidden=False,
    always_living=False,
    no_not_working=False,
) -> pygame.Surface:
    """
    Generates the sprite for a cat, with optional arguments that will override certain things.

    :param life_state: sets the age life_stage of the cat, overriding the one set by its age. Set to string.
    :param scars_hidden: If True, doesn't display the cat's scars. If False, display cat scars.
    :param acc_hidden: If True, hide the accessory. If false, show the accessory.
    :param always_living: If True, always show the cat with living lineart
    :param no_not_working: If true, never use the not_working lineart.
                    If false, use the cat.not_working() to determine the no_working art.
    """

    if life_state is not None:
        age = life_state
    else:
        age = cat.age

    if always_living:
        dead = False
    else:
        dead = cat.dead

    # setting the cat_sprite (bc this makes things much easier)
    cat_sprite = str(0)
    if (
        not no_not_working
        and cat.not_working()
        and age != "newborn"
        and game.config["cat_sprites"]["sick_sprites"]
    ):
        if age == "elder" and not game.config["fun"]["all_cats_are_newborn"]:
            age = "senior"
        if age == "young adult" and not game.config["fun"]["all_cats_are_newborn"]:
            age = "adult"
        if age == "senior adult" and not game.config["fun"]["all_cats_are_newborn"]:
            age = "adult"
        if cat.pelt.length == "long":
            if age == "kitten":
                cat_sprite = str(49)
            if age == "adolescent":
                cat_sprite = str(51)
            if age == "adult":
                cat_sprite = str(53)
            if age == "senior":
                cat_sprite = str(55)
        else:
            if age == "kitten":
                cat_sprite = str(48)
            if age == "adolescent":
                cat_sprite = str(50)
            if age == "adult":
                cat_sprite = str(52)
            if age == "senior":
                cat_sprite = str(54)

    elif cat.pelt.paralyzed and age != "newborn":
        if cat.pelt.length == "long":
            if age == "kitten":
                cat_sprite = str(41)
            if age == "adolescent":
                cat_sprite = str(43)
            if age == "adult":
                cat_sprite = str(45)
            if age == "senior":
                cat_sprite = str(47)
        else:
            if age == "kitten":
                cat_sprite = str(40)
            if age == "adolescent":
                cat_sprite = str(42)
            if age == "adult":
                cat_sprite = str(44)
            if age == "senior":
                cat_sprite = str(46)
    else:
        if age == "elder" and not game.config["fun"]["all_cats_are_newborn"]:
            age = "senior"

        if game.config["fun"]["all_cats_are_newborn"]:
            cat_sprite = str(cat.pelt.cat_sprites["newborn"])
        else:
            cat_sprite = str(cat.pelt.cat_sprites[age])

    new_sprite = pygame.Surface((sprites.size, sprites.size), pygame.HWSURFACE | pygame.SRCALPHA)

    # generating the sprite
    try:
        # 0unders/highlight, 1base, 2mid, 3dark, 4shade, 5line
        color_dict = {
            "WHITE": ["#fff9ee", "#fff9ee", "#fff3de", "#fff3de", "#e0cdac", "#a2957e"],
            "SNOW WHITE": ["#fafcff", "#fafcff", "#f1f7ff", "#f1f7ff", "#cad3e0", "#8d98a6"],
            "GRAY": ["#f1ebe3", "#cec8be", "#a9a7a2", "#8d8d8d", "#828282", "#474747"],
            "SLATE": ["#e5e5e5", "#bfc0c4", "#989aa0", "#70727c", "#474747", "#3b3d4c"],
            "DARK GRAY": ["#a29b92", "#786e63", "#5b544c", "#413c39", "#474747", "#1a1512"],
            "DARK SLATE": ["#959499", "#56555a", "#49484d", "#2b292c", "#201e21", "#070508"],
            "PALE BLUE": ["#d7dde3", "#b5bbc0", "#a2adb8", "#909ca7", "#6f8496", "#4c6073"],
            "BLUE": ["#d0d8e3", "#8e9aa8", "#79899b", "#5a6878", "#485666", "#1d3147"],
            "PALE LILAC": ["#eee1d7", "#c2afa2", "#a0928a", "#655d57", "#574639", "#302014"],
            "LILAC": ["#e5dbd0", "#9f9596", "#7a6e78", "#51464e", "#42373f", "#1f141c"],
            "SILVER": ["#f2f1f0", "#bbb8b5", "#7d7d7c", "#1c1b19", "#000000", "#000000"],
            "BLACK": ["#3b3d3a", "#212526", "#141a1e", "#0b0f12", "#000000", "#000000"],
            "SOOT BLACK": ["#44474f", "#32353e", "#1a1a22", "#101018", "#000000", "#000000"],
            "OBSIDIAN": ["#1c1b19", "#1c1b19", "#12100d", "#12100d", "#000000", "#000000"],
            "GHOST": ["#2c2c2c", "#1c1b19", "#1c1b19", "#12100d", "#000000", "#000000"],
            "PALE FIRE": ["#ffd37d", "#ffa041", "#e5673c", "#903027", "#7f281f", "#480c06"],
            "FIRE": ["#f1b875", "#ec8b19", "#d75a09", "#bd3604", "#a62400", "#780100"],
            "DARK FIRE": ["#ffa041", "#c63e10", "#ae351d", "#841b11", "#780100", "#450000"],
            "PALE GINGER": ["#ffe8cc", "#eeaf8e", "#e18e70", "#c15832", "#b24b26", "#872603"],
            "GINGER": ["#ecb088", "#c85928", "#ac3205", "#891400", "#7a0800", "#540000"],
            "DARK GINGER": ["#d78859", "#992c10", "#861800", "#7a0a00", "#400000", "#2e0000"],
            "PALE GOLD": ["#f9dcb4", "#f9c999", "#f0b883", "#e09e60", "#d68f4b", "#a36021"],
            "YELLOW": ["#fcd9a2", "#fdb772", "#ec9a4a", "#d88533", "#c97828", "#964b01"],
            "GOLD": ["#eabb8a", "#d7934d", "#bd6d35", "#ad530d", "#974302", "#752600"],
            "BRONZE": ["#fcbd87", "#eb772e", "#ca540a", "#ae4500", "#9b3700", "#751800"],
            "ROSE": ["#f1e3d7", "#e1bdaf", "#d6a594", "#c15832", "#a65031", "#802d0f"],
            "LIGHT CREAM": ["#faede0", "#f1d5ba", "#ecc8a4", "#e2b791", "#d6a273", "#99683b"],
            "CREAM": ["#fae1c6", "#f1c89f", "#e8b78b", "#dda775", "#d09865", "#875323"],
            "DARK CREAM": ["#eed1b4", "#e1ae75", "#d2995a", "#bd7b39", "#aa6827", "#713e0b"],
            "PALE BROWN": ["#d7cbc6", "#aa9991", "#9b897b", "#7d6559", "#6e564a", "#473125"],
            "ALMOND": ["#e8cdbd", "#bfa088", "#a6856d", "#896956", "#70513e", "#422411"],
            "ACORN": ["#dfb28b", "#c78350", "#ab632d", "#924b12", "#823c05", "#5e1c00"],
            "LIGHT BROWN": ["#d6b496", "#c49570", "#b27f56", "#996235", "#8a5327", "#5c2800"],
            "BROWN": ["#b78b6f", "#986747", "#78492d", "#603419", "#54280e", "#260000"],
            "DARK BROWN": ["#755640", "#593923", "#482a16", "#2c1c12", "#1f140d", "#000000"],
            "PALE CINNAMON": ["#e0af8a", "#c17041", "#a64c1e", "#882f0c", "#751c00", "#4c0000"],
            "CINNAMON": ["#d6966c", "#a54e2c", "#903615", "#7f2309", "#6e1500", "#3b0000"],
            "SABLE": ["#d08b55", "#9e623c", "#784626", "#623214", "#562809", "#2a0500"],
            "DARK SABLE": ["#c87b3f", "#8e4f29", "#633013", "#4b1c01", "#3a1200", "#200300"],
            "BIRCH": ["#f4e4d3", "#e3c8b7", "#cea98e", "#a0693a", "#905a2d", "#5b3311"],
            "PALE LAVENDER": ["#e3ccc7", "#c0a7a3", "#b29894", "#907675", "#806665", "#59403f"],
            "LAVENDER": ["#dec2b6", "#b89388", "#9a7872", "#82605e", "#6e4c4a", "#4c2b29"],
            "DARK LAVENDER": ["#dfd0c7", "#a5928d", "#897273", "#5e484a", "#523c3e", "#301b1d"],
            "DARK ORANGE": ["#e2cfba", "#b0671c", "#904301", "#3b2724", "#301c19", "#261110"],
            "DARK GOLD": ["#f7f5f1", "#f2c777", "#e99818", "#533e3d", "#473231", "#261110"],
            "COFFEE": ["#fbebdb", "#dfb892", "#a7664c", "#75312d", "#4b120e", "#310000"],
            "PALE EMBER": ["#ffd29b", "#ffaf7c", "#e87957", "#ac3a18", "#7a271e", "#511823"],
            "SANDY": ["#f5d7a9", "#e5b082", "#d0986d", "#ac6540", "#593830", "#2e1a1a"],
            "EMBER": ["#f6d6b2", "#eb9d5f", "#ce5d28", "#8c2b28", "#432323", "#250e0e"],
            "HEATHER BLUE": ["#fbe9fa", "#ccc3de", "#adadd8", "#7e85ae", "#686e8b", "#42475e"],
            "COCOA": ["#c7a59b", "#87655e", "#5b3b37", "#402222", "#1d0b0d", "#000000"],
            "WARM HONEY": ["#f4e1b1", "#eab76e", "#de8030", "#bd4f03", "#9a2e01", "#670200"],
            "CHOCOLATE": ["#f9d5b7", "#c19381", "#ad8172", "#3b231a", "#27120a", "#000000"],
            "SIENNA": ["#dbb798", "#d19a79", "#bf6745", "#ac4c34", "#a0392a", "#600300"],
            "GRANITE": ["#c6b8c0", "#a1949b", "#897c83", "#4e3c4c", "#31202f", "#040003"],
            "BLUE GRAY": ["#b7b8aa", "#7c8b90", "#5f737a", "#3e5963", "#223941", "#061217"],
            "SANDSTONE": ["#c79271", "#b4805f", "#9e745c", "#8b7263", "#5a4e46", "#35251a"],
            "BLUE GINGER": ["#d8c4bd", "#b4b0bf", "#8a828d", "#d4836b", "#a95b44", "#673628"],
            "GRAY GINGER": ["#cac2bf", "#9fa0a4", "#818286", "#b07e73", "#af6f56", "#6a3d2c"],
            "SILVER GINGER": ["#eae2dd", "#b3aba8", "#a29a96", "#c67f59", "#a46149", "#7a371f"],
            "SLATE GINGER": ["#a6a89b", "#64634e", "#404638", "#272e1e", "#801e01", "#4b0000"],
            "OAK": ["#e4d9cf", "#b9937f", "#a87a66", "#8c5f4f", "#2e2336", "#150d1b"],
            "COLD SILVER": ["#f7f5f6", "#e3e1e4", "#b3a5b6", "#7a6c7d", "#393543", "#25212f"],
            "BLUE SILVER": ["#e3f2ff", "#a8abcd", "#707392", "#47405a", "#282633", "#181924"],
            "MAUVE": ["#f5cebf", "#d99c87", "#b57269", "#985856", "#68393f", "#422833"],
            "LIGHT EMBER": ["#fff4ee", "#fed2a5", "#f4955f", "#bb4e27", "#951500", "#710000"],
            "CINDER": ["#e8e2d4", "#a89189", "#675352", "#493a37", "#312622", "#140c09"],
            "JADE": ["#d2d5ca", "#8a958f", "#65706a", "#29322d", "#1c1e1b", "#000000"],
            "DARK CHERRY": ["#a76350", "#7f341f", "#6d2c18", "#501706", "#381102", "#1e0000"],
            "ASH": ["#fdfcfa", "#fcf5ed", "#e1d7cb", "#967472", "#6c4a41", "#563732"],
            "PALE HONEY": ["#f5f5eb", "#f8e3ce", "#e1bc88", "#d69a66", "#b07943", "#7a4b1d"],
            "DARK HONEY": ["#e8c176", "#d47c18", "#b6600d", "#9c4307", "#782b01", "#4d0c00"],
            "CEDAR": ["#fff0d7", "#ffd8b1", "#e4b081", "#a66957", "#163138", "#091b20"]

        }

        # SPRITE GENERATION
        # thank you Kori ;-;
        base_name = None
        base_color = None
        tortie_base = None
        tortie_color = None
        base_tint = None

        # SETTING UP EACH PIECE
        base_pelt = None
        mid_pelt = None
        highlight_pelt = None
        dark_pelt = None
        line_pelt = None
        unders_pelt = None
        shade_pelt = None



        # Hello! I'm sorry

        if cat.pelt.name not in ['Tortie', 'Calico']:
            base_name = str(cat.pelt.name).upper()
            base_color = str(cat.pelt.colour).upper()
        else:
            base_name = str(cat.pelt.tortiebase).upper()
            base_color = str(cat.pelt.colour).upper()
            tortie_base = str(cat.pelt.tortiepattern).upper()
            tortie_color = str(cat.pelt.tortiecolour).upper()

        if base_name:
            base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            base_tint.fill(color_dict[base_color][1])
            base_pelt = sprites.sprites['baseSOLID' + cat_sprite].copy().convert_alpha()
            base_pelt.blit(base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            unders_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            unders_tint.fill(color_dict[base_color][0])
            unders_pelt = sprites.sprites['under' + base_name + cat_sprite].copy().convert_alpha()
            unders_pelt.blit(unders_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            mid_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            mid_tint.fill(color_dict[base_color][2])
            mid_pelt = sprites.sprites['mid' + base_name + cat_sprite].copy().convert_alpha()
            mid_pelt.blit(mid_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            dark_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            dark_tint.fill(color_dict[base_color][3])
            dark_pelt = sprites.sprites['dark' + base_name + cat_sprite].copy().convert_alpha()
            dark_pelt.blit(dark_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            shade_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            shade_tint.fill(color_dict[base_color][4])
            shade_pelt = sprites.sprites['shade' + base_name + cat_sprite].copy().convert_alpha()
            shade_pelt.blit(shade_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            highlight_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            highlight_tint.fill(color_dict[base_color][0])
            highlight_pelt = sprites.sprites['highlight' + base_name + cat_sprite].copy().convert_alpha()
            highlight_pelt.blit(highlight_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            line_tint.fill(color_dict[base_color][5])
            line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
            line_pelt.blit(line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


        # repeat for torties
        if tortie_base:
            tortie_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_base_tint.fill(color_dict[tortie_color][1])
            tortie_base_pelt = sprites.sprites['baseSOLID' + cat_sprite].copy().convert_alpha()
            tortie_base_pelt.blit(tortie_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_unders_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_unders_tint.fill(color_dict[tortie_color][0])
            tortie_unders_pelt = sprites.sprites['under' + tortie_base + cat_sprite].copy().convert_alpha()
            tortie_unders_pelt.blit(tortie_unders_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_mid_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_mid_tint.fill(color_dict[tortie_color][2])
            tortie_mid_pelt = sprites.sprites['mid' + tortie_base + cat_sprite].copy().convert_alpha()
            tortie_mid_pelt.blit(tortie_mid_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_dark_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_dark_tint.fill(color_dict[tortie_color][3])
            tortie_dark_pelt = sprites.sprites['dark' + tortie_base + cat_sprite].copy().convert_alpha()
            tortie_dark_pelt.blit(tortie_dark_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_shade_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_shade_tint.fill(color_dict[tortie_color][4])
            tortie_shade_pelt = sprites.sprites['shade' + tortie_base + cat_sprite].copy().convert_alpha()
            tortie_shade_pelt.blit(tortie_shade_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_highlight_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_highlight_tint.fill(color_dict[tortie_color][0])
            tortie_highlight_pelt = sprites.sprites['highlight' + tortie_base + cat_sprite].copy().convert_alpha()
            tortie_highlight_pelt.blit(tortie_highlight_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        if tortie_base:
            tortie_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_line_tint.fill(color_dict[tortie_color][5])
            tortie_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
            tortie_line_pelt.blit(tortie_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


        # Now we must make the jam

        if base_name:
            new_sprite.blit(base_pelt, (0, 0))
            new_sprite.blit(unders_pelt, (0, 0))
            new_sprite.blit(mid_pelt, (0, 0))
            new_sprite.blit(dark_pelt, (0, 0))
            new_sprite.blit(shade_pelt, (0, 0))
            new_sprite.blit(highlight_pelt, (0, 0))
            new_sprite.blit(line_pelt, (0, 0))

        if tortie_base:
            patches = sprites.sprites["baseSOLID" + cat_sprite].copy().convert_alpha()
            patches.blit(tortie_base_pelt, (0, 0))
            patches.blit(tortie_unders_pelt, (0, 0))
            patches.blit(tortie_mid_pelt, (0, 0))
            patches.blit(tortie_dark_pelt, (0, 0))
            patches.blit(tortie_shade_pelt, (0, 0))
            patches.blit(tortie_highlight_pelt, (0, 0))
            patches.blit(tortie_line_pelt, (0, 0))
            patches.blit(sprites.sprites["tortiemask" + cat.pelt.pattern + cat_sprite], (0, 0),
                         special_flags=pygame.BLEND_RGBA_MULT)
            new_sprite.blit(patches, (0, 0))

        # TINTS
        if (
            cat.pelt.tint != "none"
            and cat.pelt.tint in sprites.cat_tints["tint_colours"]
        ):
            # Multiply with alpha does not work as you would expect - it just lowers the alpha of the
            # entire surface. To get around this, we first blit the tint onto a white background to dull it,
            # then blit the surface onto the sprite with pygame.BLEND_RGB_MULT
            tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tint.fill(tuple(sprites.cat_tints["tint_colours"][cat.pelt.tint]))
            new_sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if (
            cat.pelt.tint != "none"
            and cat.pelt.tint in sprites.cat_tints["dilute_tint_colours"]
        ):
            tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tint.fill(tuple(sprites.cat_tints["dilute_tint_colours"][cat.pelt.tint]))
            new_sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


        # draw white patches
        if cat.pelt.white_patches is not None:
            white_patches = sprites.sprites[
                "white" + cat.pelt.white_patches + cat_sprite
            ].copy()

            # Apply tint to white patches.
            if (
                cat.pelt.white_patches_tint != "none"
                and cat.pelt.white_patches_tint
                in sprites.white_patches_tints["tint_colours"]
            ):
                tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tint.fill(
                    tuple(
                        sprites.white_patches_tints["tint_colours"][
                            cat.pelt.white_patches_tint
                        ]
                    )
                )
                white_patches.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            new_sprite.blit(white_patches, (0, 0))

        # draw vit & points

        if cat.pelt.points:
            points = sprites.sprites["white" + cat.pelt.points + cat_sprite].copy()
            if (
                cat.pelt.white_patches_tint != "none"
                and cat.pelt.white_patches_tint
                in sprites.white_patches_tints["tint_colours"]
            ):
                tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tint.fill(
                    tuple(
                        sprites.white_patches_tints["tint_colours"][
                            cat.pelt.white_patches_tint
                        ]
                    )
                )
                points.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            new_sprite.blit(points, (0, 0))

        if cat.pelt.vitiligo:
            new_sprite.blit(
                sprites.sprites["white" + cat.pelt.vitiligo + cat_sprite], (0, 0)
            )

        # draw eyes
        # base0, mid1, top2, shade3
        eyecolor_dict = {
            "YELLOW": ["#fffde3", "#ceb94c", "#9e8033", "#90631d"],
            "AMBER": ["#f2e085", "#c77d40", "#a14a1e", "#903203"],
            "HAZEL": ["#f2e085", "#aeb670", "#665e2e", "#544c1c"],
            "PALE GREEN": ["#dde895", "#77ab5d", "#356735", "#214f21"],
            "GREEN": ["#b5ecad", "#569669", "#20473d", "#06271f"],
            "BLUE": ["#adeef0", "#6ab1d4", "#2f4f9c", "#052573"],
            "DARK BLUE": ["#afc7f3", "#4d5190", "#261b3b", "#170e27"],
            "GREY": ["#c9c9c9", "#8f8f8f", "#3f3f3f", "#2e2e2e"],
            "CYAN": ["#d9f3ef", "#8cbdbd", "#549c9c", "#347d7d"],
            "EMERALD": ["#fef696", "#4ddfa2", "#279582", "#006c58"],
            "HEATHER BLUE": ["#b8b7ed", "#7875ba", "#3c3a86", "#1d1c62"],
            "SUN-LIT ICE": ["#fff9ac", "#6eb7d7", "#213d8a", "#0c2773"],
            "COPPER": ["#fff9ac", "#c75212", "#8a1e02", "#710200"],
            "SAGE": ["#fff9ac", "#6a8f7b", "#255039", "#1b3f2c"],
            "BRIGHT BLUE": ["#fff8d5", "#57c0d0", "#125a80", "#00375e"],
            "PALE BLUE": ["#e5f5f8", "#acdfe8", "#6e9dad", "#4b7e90"],
            "LAVENDER": ["#fff9ac", "#7b78bd", "#3c3a86", "#22206a"],
            "DARK GREY": ["#f1e3c0", "#47485a", "#131719", "#060808"],
            "PALE YELLOW": ["#f6eecb", "#f2dd7d", "#eb9f1d", "#c66200"],
            "GOLD": ["#f6eecb", "#efb931", "#a95d03", "#903400"],
            "LIME": ["#fef8ac", "#969c27", "#343507", "#222200"],
            "HAZELNUT": ["#f2bf85", "#974911", "#4b1100", "#380000"],
            "DARK AMBER": ["#f1b995", "#ef4c3f", "#790200", "#600000"],
            "SLATE": ["#bdc9e7", "#6b789b", "#303951", "#21293c"],
            "RUBY": ["#f8d0af", "#dd631d", "#b10e0e", "#900000"],
            "LILAC": ["#f6e6bf", "#ec8eae", "#5566f1", "#6235d7"],
            "LIGHT GREY": ["#f3f8fa", "#c8d5db", "#7791a0", "#567384"],
            "PINK": ["#f2e7e7", "#f7c0d6", "#9c415b", "#84243f"],
            "DARK HAZEL": ["#f9e7df", "#767e5b", "#442f21", "#311f13"],
            "CHOCOLATE": ["#bf9c8a", "#422b20", "#0c0502", "#000000"],
            "PURPLE": ["#dbdbfa", "#bc75f9", "#535eeb", "#00218a"],
            "SUNSET": ["#f6cbd8", "#ff0051", "#790043", "#05002e"],
            "CARAMEL": ["#fbf8f2", "#deb888", "#b76f44", "#904518"],
            "AUTUMN": ["#eedcb6", "#fa915c", "#b16c49", "#7a3f21"],
            "MAGENTA": ["#ffeec1", "#ff5779", "#813b4b", "#4f2430"],
            "SUMMER": ["#fdf0bd", "#fbb341", "#1c674d", "#01412b"],
            "SEASIDE": ["#f6ebc6", "#f87e4d", "#0e7fa6", "#1c1e5e"],
            "MIDNIGHT": ["#b6ddec", "#0d588a", "#59295b", "#210755"],
            "WINTER": ["#faf4ee", "#93adc6", "#3686b6", "#49346a"],
            "ECLIPSE": ["#f3e2ac", "#a44321", "#530e1e", "#061427"],
            "CRIMSON": ["#f3e2d2", "#d23535", "#880000", "#4d0000"],
            "SPRING": ["#fdfcea", "#c9e7be", "#6bc8a1", "#4c846c"],
            "ICE": ["#f4f5f9", "#d7e3fa", "#a8c5ff", "#78a2fb"],
            "FOREST": ["#f5ecc0", "#88a446", "#346635", "#1e4132"],
            "COFFEE": ["#ffefca", "#9a6052", "#4b2e33", "#2c1115"],
            "BRIGHT GREEN": ["#ccf3a3", "#8dec85", "#1de377", "#00993c"],
            "MOCHA": ["#f5ebe4", "#c6a484", "#6d5d54", "#433d38"],
            "SEA GREEN": ["#d6f1c2", "#8ae5b8", "#1ac4a4", "#00878b"],
            "DOVE": ["#f2fbbb", "#f0e8a3", "#1d6e8c", "#abcf5e"],
            "CANDY": ["#d6f7ff", "#a8eeff", "#49c9e9", "#e997ed"],
            "HIBISCUS": ["#fedfbd", "#e94ec9", "#b90e52", "#680b08"],
            "HONEY": ["#ffedc7", "#ffd47a", "#ec9332", "#b54312"],
            "PIXIE": ["#ffe0fb", "#ffc2f7", "#37aeeb", "#0987c8"],
            "OLIVE": ["#dce5c8", "#76ab73", "#538650", "#355634"],
            "STARLIGHT": ["#d5e1fc", "#4472cf", "#ffffff", "#19439a"],
            "BARK": ["#e5cbb3", "#563f29", "#33271c", "#33271c"],
            "COLD PURPLE": ["#d4f0fe", "#b078c3", "#793a65", "#461c40"],
            "WARM GREEN": ["#d8c971", "#555c08", "#554e08", "#554508"],
            "SUNRISE": ["#ecad8e", "#e36a6f", "#705b7c", "#365071"],
            "WARM HAZEL": ["#f0aa54", "#a27450", "#9e572b", "#64622f"],
            "COLD FIRE": ["#eaf4fd", "#c8e3fd", "#e18c89", "#e18c89"],
            "EMBER": ["#f9e156", "#f9b656", "#bd3b1b", "#860e00"],
            "RUST": ["#6f8586", "#576b6d", "#855031", "#425757"],
            "LEMON": ["#f9f8f4", "#faeed7", "#ffe2a8", "#fbd178"],

        }

        eye_base = None
        eye_mid = None
        eye_top = None
        eye_shade = None
        hc_eye_base = None
        hc_eye_mid = None
        hc_eye_top = None
        hc_eye_shade = None


        eye_color = str(cat.pelt.eye_colour).upper()
        eye_color2 = str(cat.pelt.eye_colour2).upper()

        eye_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        eye_base_tint.fill(eyecolor_dict[eye_color][0])
        eye_base = sprites.sprites['eyebase' + cat_sprite].copy().convert_alpha()
        eye_base.blit(eye_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        eye_mid_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        eye_mid_tint.fill(eyecolor_dict[eye_color][1])
        eye_mid = sprites.sprites['eyemid' + cat_sprite].copy().convert_alpha()
        eye_mid.blit(eye_mid_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        eye_top_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        eye_top_tint.fill(eyecolor_dict[eye_color][2])
        eye_top = sprites.sprites['eyetop' + cat_sprite].copy().convert_alpha()
        eye_top.blit(eye_top_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        eye_shade_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        eye_shade_tint.fill(eyecolor_dict[eye_color][3])
        eye_shade = sprites.sprites['eyeshade' + cat_sprite].copy().convert_alpha()
        eye_shade.blit(eye_shade_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        if cat.pelt.eye_colour2 != None:
            hc_eye_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            hc_eye_base_tint.fill(eyecolor_dict[eye_color2][0])
            hc_eye_base = sprites.sprites['eyebase' + cat_sprite].copy().convert_alpha()
            hc_eye_base.blit(hc_eye_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            hc_eye_mid_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            hc_eye_mid_tint.fill(eyecolor_dict[eye_color2][1])
            hc_eye_mid = sprites.sprites['eyemid' + cat_sprite].copy().convert_alpha()
            hc_eye_mid.blit(hc_eye_mid_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            hc_eye_top_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            hc_eye_top_tint.fill(eyecolor_dict[eye_color2][2])
            hc_eye_top = sprites.sprites['eyetop' + cat_sprite].copy().convert_alpha()
            hc_eye_top.blit(hc_eye_top_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            hc_eye_shade_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            hc_eye_shade_tint.fill(eyecolor_dict[eye_color2][3])
            hc_eye_shade = sprites.sprites['eyeshade' + cat_sprite].copy().convert_alpha()
            hc_eye_shade.blit(hc_eye_shade_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        new_sprite.blit(eye_base, (0, 0))
        new_sprite.blit(eye_mid, (0, 0))
        new_sprite.blit(eye_top, (0, 0))
        new_sprite.blit(eye_shade, (0, 0))

        if cat.pelt.eye_colour2 != None:
            second_eye = sprites.sprites['eyebase' + cat_sprite].copy().convert_alpha()
            second_eye.blit(hc_eye_base, (0, 0))
            second_eye.blit(hc_eye_mid, (0, 0))
            second_eye.blit(hc_eye_top, (0, 0))
            second_eye.blit(hc_eye_shade, (0, 0))
            second_eye.blit(sprites.sprites["eyes2" + cat.pelt.eye_pattern + cat_sprite], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            new_sprite.blit(second_eye, (0, 0))

        new_sprite.blit(sprites.sprites["eyelight" + cat_sprite], (0, 0))

        #scars1
        if not scars_hidden:
            for scar in cat.pelt.scars:
                if scar in cat.pelt.scars1:
                    new_sprite.blit(
                        sprites.sprites["scars" + scar + cat_sprite], (0, 0)
                    )
                if scar in cat.pelt.scars3:
                    new_sprite.blit(
                        sprites.sprites["scars" + scar + cat_sprite], (0, 0)
                    )

        # draw line art
       # if game.settings["shaders"] and not dead:
        #    new_sprite.blit(
        #        sprites.sprites["shaders" + cat_sprite],
        #        (0, 0),
        #        special_flags=pygame.BLEND_RGB_MULT,
        #    )
         #   new_sprite.blit(sprites.sprites["lighting" + cat_sprite], (0, 0))

        lineart_dict = {
            "BLACK": ["#000000"],
            "RED": ["#410000"],
            "BLUE": ["#94C7E3"]
        }

        if not dead:
            if game.config["moss"]["black_lineart"]:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLACK"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
        elif cat.df:
            if game.config["moss"]["black_lineart"]:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLACK"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
            else:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["RED"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
            new_sprite.blit(sprites.sprites["lineartdf" + cat_sprite], (0, 0))
        elif dead:
            if game.config["moss"]["black_lineart"]:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLACK"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
            else:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLUE"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
            new_sprite.blit(sprites.sprites["lineartdead" + cat_sprite], (0, 0))
        # draw skin and scars2
        blendmode = pygame.BLEND_RGBA_MIN

        skincolor_dict = {
            "BLACK": ["#312923"],
            "RED": ["#bf5338"],
            "PINK": ["#f9c0b8"],
            "DARKBROWN": ["#523219"],
            "BROWN": ["#5f3e24"],
            "LIGHTBROWN": ["#7d6146"],
            "DARK": ["#201e1b"],
            "DARKGREY": ["#464340"],
            "GREY": ["#8a8581"],
            "DARKSALMON": ["#9a5a44"],
            "SALMON": ["#da9c7b"],
            "PEACH": ["#ffc7a8"],
            "DARKBLUE": ["#545a5e"],
            "BLUE": ["#3a4e57"],
            "LIGHTBLUE": ["#5f676b"]
        }

        skin_color = str(cat.pelt.skin_color).upper()
        skin_name = str(cat.pelt.skin).upper()
        skin_base = None

        skin_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        skin_base_tint.fill(skincolor_dict[skin_color][0])
        skin_base = sprites.sprites['skin' + skin_name + cat_sprite].copy().convert_alpha()
        skin_base.blit(skin_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        new_sprite.blit(skin_base, (0, 0))



        if not scars_hidden:
            for scar in cat.pelt.scars:
                if scar in cat.pelt.scars2:
                    new_sprite.blit(
                        sprites.sprites["scars" + scar + cat_sprite],
                        (0, 0),
                        special_flags=blendmode,
                    )
                    new_sprite.blit(
                        sprites.sprites["scarscolor" + scar + cat_sprite], (0, 0)
                    )

        # im sure i won't regret this later
        acolor_dict = {
            "BLACK": ["#3c3c3c"],
            "WHITE": ["#dbdbdb"],
            "RED": ["#c11a21"],
            "DARK ORANGE": ["#de3c02"],
            "ORANGE": ["#eb8b12"],
            "YELLOW": ["#f9ba32"],
            "PALE YELLOW": ["#ebd664"],
            "CYAN": ["#76cdbf"],
            "LIGHT BLUE": ["#8fceea"],
            "BLUE": ["#5386d9"],
            "DARK BLUE": ["#31416d"],
            "PURPLE": ["#744b9c"],
            "LIGHT PURPLE": ["#7669cd"],
            "LILAC": ["#9d90cb"],
            "PINK": ["#fb8580"],
            "GREEN": ["#5e7f35"],
            "LIGHT GREEN": ["#7ba568"],
            "BRIGHT GREEN": ["#48a352"],
            "DARK GREEN": ["#446718"],
            "DARK BROWN": ["#944723"],
            "BRONZE": ["#b57f37"],
            "BROWN": ["#9f7600"],
            "LIGHT BROWN": ["#a48c68"],
            "BRIGHT PURPLE": ["#621575"],
            "HOT PINK": ["#eb77af"],
            "GOLD": ["#f9ba32"],
            "SILVER": ["#d2cdc4"],
            "LIME": ["#aed41c"],
            "NEON PURPLE": ["#ac2ccd"],
            "DEFAULT": ["#000000"]
        }

        ac = str(cat.pelt.accessory_color).upper()
        ac2 = str(cat.pelt.accessory_color2).upper()
        ap = str(cat.pelt.accessory_pattern).upper()
        ap2 = str(cat.pelt.accessory_pattern2).upper()

        if not acc_hidden:
            if cat.pelt.accessory in cat.pelt.simple_acc:
                new_sprite.blit(sprites.sprites["acc" + cat.pelt.accessory + cat_sprite], (0, 0),)
            if cat.pelt.accessory == "COWBOY HAT":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "BANDANA" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                bandana = sprites.sprites['accbase' + "BANDANA" + cat_sprite].copy().convert_alpha()
                bandana.blit(ac_pelt, (0, 0))
                bandana.blit(ap_pelt, (0, 0))
                bandana.blit(sprites.sprites['accbase' + "BANDANA" + cat_sprite], (0, 0),
                             special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(bandana, (0, 0))
                new_sprite.blit(sprites.sprites["acccollars" + "COWBOY HAT" + cat_sprite], (0, 0), )
            if cat.pelt.accessory == "LEATHERCOLLAR":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                collar = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                collar.blit(ac_pelt, (0, 0))
                collar.blit(ap_pelt, (0, 0))
                collar.blit(sprites.sprites['accbase' + "COLLAR" + cat_sprite], (0, 0),
                            special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(collar, (0, 0))

            if cat.pelt.accessory == "FANGCOLLAR":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                fang = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                fang.blit(ac_pelt, (0,0))
                fang.blit(ap_pelt, (0, 0))
                fang.blit(sprites.sprites['accbase' + "COLLAR" + cat_sprite], (0, 0),special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(fang, (0, 0))
                new_sprite.blit(sprites.sprites['acccollars' + "FANG" + cat_sprite], (0, 0), )


            if cat.pelt.accessory == "BELLCOLLAR":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ac2_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac2_tint.fill(acolor_dict[ac2][0])
                ac2_pelt = sprites.sprites['acccollars' + "BELL" + cat_sprite].copy().convert_alpha()
                ac2_pelt.blit(ac2_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                collar = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                collar.blit(ac_pelt, (0, 0))
                collar.blit(ap_pelt, (0, 0))
                collar.blit(sprites.sprites['accbase' + "COLLAR" + cat_sprite], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(collar, (0, 0))
                new_sprite.blit(ac2_pelt, (0, 0))

            if cat.pelt.accessory == "STUDDEDCOLLAR":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ac2_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac2_tint.fill(acolor_dict[ac2][0])
                ac2_pelt = sprites.sprites['acccollars' + "STUDDED" + cat_sprite].copy().convert_alpha()
                ac2_pelt.blit(ac2_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                collar = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                collar.blit(ac_pelt, (0, 0))
                collar.blit(ap_pelt, (0, 0))
                collar.blit(sprites.sprites['accbase' + "COLLAR" + cat_sprite], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(collar, (0, 0))
                new_sprite.blit(ac2_pelt, (0, 0))

            if cat.pelt.accessory == "BOWCOLLAR":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ac2_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac2_tint.fill(acolor_dict[ac2][0])
                ac2_pelt = sprites.sprites['acccollars' + "BOW" + cat_sprite].copy().convert_alpha()
                ac2_pelt.blit(ac2_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap2_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern2 + cat_sprite].copy().convert_alpha()
                ap2_pelt.blit(ap2_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                collar = sprites.sprites['accbase' + "COLLAR" + cat_sprite].copy().convert_alpha()
                collar.blit(ac_pelt, (0, 0))
                collar.blit(ap_pelt, (0, 0))
                collar.blit(sprites.sprites['accbase' + "COLLAR" + cat_sprite], (0, 0),
                            special_flags=pygame.BLEND_RGBA_MULT)

                bow = sprites.sprites['acccollars' + "BOW" + cat_sprite].copy().convert_alpha()
                bow.blit(ac2_pelt, (0, 0))
                bow.blit(ap2_pelt, (0, 0))
                bow.blit(sprites.sprites['acccollars' + "BOW" + cat_sprite], (0, 0),
                            special_flags=pygame.BLEND_RGBA_MULT)

                new_sprite.blit(collar, (0, 0))
                new_sprite.blit(bow, (0, 0))

            if cat.pelt.accessory == "BANDANA":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                bandana = sprites.sprites['accbase' + "BANDANA" + cat_sprite].copy().convert_alpha()
                bandana.blit(ac_pelt, (0, 0))
                bandana.blit(ap_pelt, (0, 0))
                bandana.blit(sprites.sprites['accbase' + "BANDANA" + cat_sprite], (0, 0),
                            special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(bandana, (0, 0))

            if cat.pelt.accessory == "HARNESS":
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ap_pelt = sprites.sprites['accpattern' + cat.pelt.accessory_pattern + cat_sprite].copy().convert_alpha()
                ap_pelt.blit(ap_pelt, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                harness = sprites.sprites['accbase' + "HARNESS" + cat_sprite].copy().convert_alpha()
                harness.blit(ac_pelt, (0, 0))
                harness.blit(ap_pelt, (0, 0))
                harness.blit(sprites.sprites['accbase' + "HARNESS" + cat_sprite], (0, 0),
                             special_flags=pygame.BLEND_RGBA_MULT)
                new_sprite.blit(harness, (0, 0))

            if cat.pelt.accessory in cat.pelt.leafbase_acc:
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ac2_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac2_tint.fill(acolor_dict[ac2][0])
                ac2_pelt = sprites.sprites['accadd' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac2_pelt.blit(ac2_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                leaf = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                leaf.blit(ac_pelt, (0, 0))
                bulb = sprites.sprites['accadd' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                bulb.blit(ac2_pelt, (0, 0))

                new_sprite.blit(leaf, (0, 0))
                new_sprite.blit(bulb, (0, 0))
            if cat.pelt.accessory in cat.pelt.doubleflower_acc:
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                ac2_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac2_tint.fill(acolor_dict[ac2][0])
                ac2_pelt = sprites.sprites['accadd' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac2_pelt.blit(ac2_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                leaf = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                leaf.blit(ac_pelt, (0, 0))
                bulb = sprites.sprites['accadd' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                bulb.blit(ac2_pelt, (0, 0))

                new_sprite.blit(leaf, (0, 0))
                new_sprite.blit(bulb, (0, 0))

            if cat.pelt.accessory in cat.pelt.onecolor_nopattern_acc:
                ac_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                ac_tint.fill(acolor_dict[ac][0])
                ac_pelt = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                ac_pelt.blit(ac_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                acc = sprites.sprites['accbase' + cat.pelt.accessory + cat_sprite].copy().convert_alpha()
                acc.blit(ac_pelt, (0, 0))
                new_sprite.blit(acc, (0, 0))

            if cat.pelt.accessory in ["DAISY", "MOTH", "FEATHER", "CRYSTAL"]:
                new_sprite.blit(sprites.sprites['accadd' + cat.pelt.accessory + cat_sprite], (0, 0))






        # Apply fading fog
        if (
            cat.pelt.opacity <= 97
            and not cat.prevent_fading
            and game.clan.clan_settings["fading"]
            and dead
        ):
            stage = "0"
            if 80 >= cat.pelt.opacity > 45:
                # Stage 1
                stage = "1"
            elif cat.pelt.opacity <= 45:
                # Stage 2
                stage = "2"

            new_sprite.blit(
                sprites.sprites["fademask" + stage + cat_sprite],
                (0, 0),
                special_flags=pygame.BLEND_RGBA_MULT,
            )

            if cat.df:
                temp = sprites.sprites["fadedf" + stage + cat_sprite].copy()
                temp.blit(new_sprite, (0, 0))
                new_sprite = temp
            else:
                temp = sprites.sprites["fadestarclan" + stage + cat_sprite].copy()
                temp.blit(new_sprite, (0, 0))
                new_sprite = temp

        # reverse, if assigned so
        if cat.pelt.reverse:
            new_sprite = pygame.transform.flip(new_sprite, True, False)

    except (TypeError, KeyError):
        logger.exception("Failed to load sprite")

        # Placeholder image
        new_sprite = image_cache.load_image(
            f"sprites/error_placeholder.png"
        ).convert_alpha()

    return new_sprite


def apply_opacity(surface, opacity):
    for x in range(surface.get_width()):
        for y in range(surface.get_height()):
            pixel = list(surface.get_at((x, y)))
            pixel[3] = int(pixel[3] * opacity / 100)
            surface.set_at((x, y), tuple(pixel))
    return surface


# ---------------------------------------------------------------------------- #
#                                     OTHER                                    #
# ---------------------------------------------------------------------------- #


def chunks(L, n):
    return [L[x : x + n] for x in range(0, len(L), n)]


def is_iterable(y):
    try:
        0 in y
    except TypeError:
        return False


def get_text_box_theme(theme_name=None):
    """Updates the name of the theme based on dark or light mode"""
    if game.settings["dark mode"]:
        return ObjectID("#dark", theme_name)
    else:
        return theme_name


def quit(savesettings=False, clearevents=False):
    """
    Quits the game, avoids a bunch of repeated lines
    """
    if savesettings:
        game.save_settings(None)
    if clearevents:
        game.cur_events_list.clear()
    game.rpc.close_rpc.set()
    game.rpc.update_rpc.set()
    pygame.display.quit()
    pygame.quit()
    if game.rpc.is_alive():
        game.rpc.join(1)
    sys_exit()


with open(f"resources/dicts/conditions/permanent_conditions.json", "r") as read_file:
    PERMANENT = ujson.loads(read_file.read())

with open(f"resources/dicts/acc_display.json", "r") as read_file:
    ACC_DISPLAY = ujson.loads(read_file.read())

with open(f"resources/dicts/snippet_collections.json", "r") as read_file:
    SNIPPETS = ujson.loads(read_file.read())

with open(f"resources/dicts/prey_text_replacements.json", "r") as read_file:
    PREY_LISTS = ujson.loads(read_file.read())

with open(f"resources/dicts/backstories.json", "r") as read_file:
    BACKSTORIES = ujson.loads(read_file.read())
