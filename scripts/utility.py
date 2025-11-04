# pylint: disable=line-too-long
"""

TODO: Docs


"""  # pylint: enable=line-too-long

import logging
import os
import re
import traceback
from itertools import combinations
from math import floor
from random import choice, choices, randint, random, sample, randrange, getrandbits
from sys import exit as sys_exit
from typing import List, Tuple, TYPE_CHECKING, Type, Union, Optional

import i18n
import pygame
import ujson
from pygame_gui.core import ObjectID

from scripts.cat_relations.enums import RelType, RelTier, rel_type_tiers
from scripts.clan_package.settings import get_clan_setting
from scripts.game_structure.game.settings import game_settings_save, game_setting_get
from scripts.game_structure.game.switches import switch_get_value, Switch
from scripts.game_structure.localization import (
    load_lang_resource,
    determine_plural_pronouns,
    get_lang_config,
)

logger = logging.getLogger(__name__)
from scripts.game_structure import image_cache, localization, constants
from scripts.cat.enums import CatAge, CatRank, CatSocial, CatGroup, CatStanding
from scripts.cat.names import names
from scripts.cat.sprites import sprites
from scripts.game_structure import game
import scripts.game_structure.screen_settings  # must be done like this to get updates when we change screen size etc

if TYPE_CHECKING:
    from scripts.cat.cats import Cat



# ---------------------------------------------------------------------------- #
#                               Getting Cats                                   #
# ---------------------------------------------------------------------------- #


def get_alive_clan_queens(living_cats):
    living_kits = [
        cat
        for cat in living_cats
        if cat.status.alive_in_player_clan and cat.status.rank.is_baby()
    ]

    queen_dict = {}
    for cat in living_kits.copy():
        parents = cat.get_parents()
        # Fetch parent object, only alive and not outside.
        parents = [
            cat.fetch_cat(i)
            for i in parents
            if cat.fetch_cat(i) and cat.fetch_cat(i).status.alive_in_player_clan
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


def find_alive_cats_with_rank(
    Cat: Union["Cat", Type["Cat"]],
    ranks: list,
    working: bool = False,
    sort: bool = False,
) -> list:
    """
    returns a list of cat objects for all living cats with a listed rank in Clan
    :param Cat Cat: Cat class
    :param list ranks: list of ranks to search for
    :param bool working: default False, set to True if you would like the list to only include working cats
    :param bool sort: default False, set to True if you would like list sorted by descending moon age
    """

    alive_cats = [
        i
        for i in Cat.all_cats.values()
        if i.status.rank in ranks and i.status.alive_in_player_clan
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
        if not the_cat.status.alive_in_player_clan:
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
        if not inter_cat.status.alive_in_player_clan:
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
        if not inter_cat.status.alive_in_player_clan:
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


def get_warring_clan():
    """
    returns enemy clan if a war is currently ongoing
    """
    enemy_clan = None
    if game.clan.war.get("at_war", False):
        for other_clan in game.clan.all_other_clans:
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

    if constants.CONFIG["lock_season"]:
        game.clan.current_season = game.clan.starting_season
        return game.clan.starting_season

    modifiers = {"Newleaf": 0, "Greenleaf": 3, "Leaf-fall": 6, "Leaf-bare": 9}
    index = game.clan.age % 12 + modifiers[game.clan.starting_season]

    if index > 11:
        index = index - 12

    game.clan.current_season = constants.SEASON_CALENDAR[index]

    return game.clan.current_season


def change_clan_reputation(difference):
    """
    will change the Clan's reputation with outsider cats according to the difference parameter.
    """
    game.clan.reputation += difference
    if game.clan.reputation < 0:
        game.clan.reputation = 0  # clamp to 0
    elif game.clan.reputation > 100:
        game.clan.reputation = 100  # clamp to 100


def change_clan_relations(other_clan, difference):
    """
    will change the Clan's relation with other clans according to the difference parameter.
    """
    # grab the clan that has been indicated
    other_clan = other_clan
    # grab the relation value for that clan
    y = game.clan.all_other_clans.index(other_clan)
    clan_relations = int(game.clan.all_other_clans[y].relations)
    # change the value
    clan_relations += difference
    # making sure it doesn't exceed the bounds
    if clan_relations > 30:
        clan_relations = 30
    elif clan_relations < 0:
        clan_relations = 0
    # setting it in the Clan save
    game.clan.all_other_clans[y].relations = clan_relations


def create_new_cat_block(
    Cat: Optional["Cat"],
    Relationship,
    event,
    in_event_cats: dict,
    i: int,
    attribute_list: List[str],
    other_clan=None,
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

    thought = i18n.t("hardcoded.thought_new_cat")
    new_cats = None

    # gather parents
    parent1 = None
    parent2 = None
    adoptive_parents = []
    for tag in attribute_list:
        parent_match = re.match(r"parent:([,0-9]+)", tag)
        adoptive_match = re.match(r"adoptive:(.+)", tag)
        if not parent_match and not adoptive_match:
            continue

        parent_indexes = parent_match.group(1).split(",") if parent_match else []
        adoptive_indexes = adoptive_match.group(1).split(",") if adoptive_match else []
        if not parent_indexes and not adoptive_indexes:
            continue

        parent_indexes = [int(index) for index in parent_indexes]
        for index in parent_indexes:
            if index >= i:
                continue

            if parent1 is None:
                parent1 = event.new_cats[index][0]
            else:
                parent2 = event.new_cats[index][0]

        adoptive_indexes = [
            int(index) if index.isdigit() else index for index in adoptive_indexes
        ]
        for index in adoptive_indexes:
            if in_event_cats[index].ID not in adoptive_parents:
                adoptive_parents.append(in_event_cats[index].ID)
                adoptive_parents.extend(in_event_cats[index].mate)

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
                if in_event_cats[index].status.rank.is_any_apprentice_rank():
                    print("Can't give apprentices mates")
                    continue

                give_mates.append(in_event_cats[index])

    # determine gender
    if "male" in attribute_list:
        gender = "male"
    elif "female" in attribute_list:
        gender = "female"
    elif "can_birth" in attribute_list and not get_clan_setting("same sex birth"):
        gender = "female"
    else:
        gender = None

    # will the cat get a new name?
    if "new_name" in attribute_list:
        new_name = True
    elif "old_name" in attribute_list:
        new_name = False
    else:
        new_name = bool(getrandbits(1))

    # RANK - must be handled before backstories
    rank = None
    for _tag in attribute_list:
        match = re.match(r"status:(.+)", _tag)
        if not match:
            continue

        if match.group(1) in [
            CatRank.NEWBORN,
            CatRank.KITTEN,
            CatRank.ELDER,
            CatRank.APPRENTICE,
            CatRank.WARRIOR,
            CatRank.MEDIATOR_APPRENTICE,
            CatRank.MEDIATOR,
            CatRank.MEDICINE_APPRENTICE,
            CatRank.MEDICINE_CAT,
        ]:
            rank = match.group(1)
            break

    # SET AGE
    age = None
    for _tag in attribute_list:
        match = re.match(r"age:(.+)", _tag)
        if not match:
            continue

        if match.group(1) in Cat.age_moons:
            min_age, max_age = Cat.age_moons[CatAge(match.group(1))]
            age = randint(min_age, max_age)
            break

        # Set same as first mate
        if match.group(1) == "mate" and give_mates:
            min_age, max_age = Cat.age_moons[give_mates[0].age]
            age = randint(min_age, max_age)
            break

        if match.group(1) == "has_kits":
            age = randint(19, 120)
            break

    if rank and not age:
        if rank in [
            CatRank.APPRENTICE,
            CatRank.MEDIATOR_APPRENTICE,
            CatRank.MEDICINE_APPRENTICE,
        ]:
            age = randint(
                Cat.age_moons[CatAge.ADOLESCENT][0],
                Cat.age_moons[CatAge.ADOLESCENT][1],
            )
        elif rank in [CatRank.WARRIOR, CatRank.MEDIATOR, CatRank.MEDICINE_CAT]:
            age = randint(
                Cat.age_moons["young adult"][0], Cat.age_moons["senior adult"][1]
            )
        elif rank == CatRank.ELDER:
            age = randint(Cat.age_moons["senior"][0], Cat.age_moons["senior"][1])

    cat_group = None

    if "kittypet" in attribute_list:
        cat_social = CatSocial.KITTYPET
    elif "rogue" in attribute_list:
        cat_social = CatSocial.ROGUE
    elif "loner" in attribute_list:
        cat_social = CatSocial.LONER
    elif "clancat" in attribute_list or "former Clancat" in attribute_list:
        cat_social = CatSocial.CLANCAT
        if other_clan:
            cat_group = other_clan.group_ID
        else:
            cat_group = choice([x.group_ID for x in game.clan.all_other_clans])
    else:
        cat_social = choice([CatSocial.KITTYPET, CatSocial.LONER, "former Clancat"])

    # LITTER
    litter = False
    if "litter" in attribute_list:
        litter = True
        if rank not in (CatRank.KITTEN, CatRank.NEWBORN):
            rank = CatRank.KITTEN

    # CHOOSE DEFAULT BACKSTORY BASED ON CAT TYPE, STATUS
    if rank in (CatRank.KITTEN, CatRank.NEWBORN):
        chosen_backstory = choice(
            BACKSTORIES["backstory_categories"]["abandoned_backstories"]
        )
    elif rank == CatRank.MEDICINE_CAT and cat_social == CatSocial.CLANCAT:
        chosen_backstory = choice(["medicine_cat", "disgraced1"])
    elif rank == CatRank.MEDICINE_CAT:
        chosen_backstory = choice(["wandering_healer1", "wandering_healer2"])
    else:
        if cat_social == CatSocial.CLANCAT:
            x = "former_clancat"
        else:
            x = cat_social
        chosen_backstory = choice(
            BACKSTORIES["backstory_categories"].get(f"{x}_backstories", ["outsider1"])
        )

    # OPTION TO OVERRIDE DEFAULT BACKSTORY
    bs_override = False
    stor = []
    for _tag in attribute_list:
        match = re.match(r"backstory:(.+)", _tag)
        if match:
            bs_list = [x for x in re.split(r", ?", match.group(1))]
            stor = []
            for story in bs_list:
                if story in set(
                    [
                        backstory
                        for backstory_block in BACKSTORIES[
                            "backstory_categories"
                        ].values()
                        for backstory in backstory_block
                    ]
                ):
                    stor.append(story)
                elif story in BACKSTORIES["backstory_categories"]:
                    stor.extend(BACKSTORIES["backstory_categories"][story])
            bs_override = True
            break
    if bs_override:
        chosen_backstory = choice(stor)
        if chosen_backstory in (
            BACKSTORIES["backstory_categories"]["baby_clancat_backstories"]
            + BACKSTORIES["backstory_categories"]["former_clancat_backstories"]
        ):
            cat_social = CatSocial.CLANCAT
        elif chosen_backstory in (
            BACKSTORIES["backstory_categories"]["baby_loner_backstories"]
            + BACKSTORIES["backstory_categories"]["loner_backstories"]
        ):
            cat_social = CatSocial.LONER
        elif chosen_backstory in (
            BACKSTORIES["backstory_categories"]["baby_kittypet_backstories"]
            + BACKSTORIES["backstory_categories"]["kittypet_backstories"]
        ):
            cat_social = CatSocial.KITTYPET
        elif (
            chosen_backstory in BACKSTORIES["backstory_categories"]["rogue_backstories"]
        ):
            cat_social = CatSocial.ROGUE

    # KITTEN THOUGHT
    if rank in (CatRank.KITTEN, CatRank.NEWBORN):
        thought = i18n.t("hardcoded.thought_new_kitten")

    # MEETING - DETERMINE IF THIS IS AN OUTSIDE CAT
    outside = False
    if "meeting" in attribute_list:
        outside = True
        rank = None
        new_name = False
        thought = i18n.t("hardcoded.thought_meeting")
        if age is not None and age <= 6 and not bs_override:
            chosen_backstory = "outsider1"

    # IS THE CAT DEAD?
    alive = True
    if "dead" in attribute_list:
        alive = False
        thought = i18n.t("hardcoded.thought_new_dead")

    # check if we can use an existing cat here
    chosen_cat: Optional["Cat"] = None
    if "exists" in attribute_list:
        existing_outsiders = [
            i for i in Cat.all_cats.values() if i.status.is_outsider and not i.dead
        ]
        possible_outsiders = []
        for cat in existing_outsiders:
            if stor and cat.backstory not in stor:
                continue
            if cat_social != cat.status.social:
                continue
            if gender and gender != cat.gender:
                continue
            if age and age not in Cat.age_moons[cat.age]:
                continue
            possible_outsiders.append(cat)

        if possible_outsiders:
            chosen_cat = choice(possible_outsiders)
            if not alive:
                chosen_cat.die()
            elif not outside:
                if not rank:
                    rank = chosen_cat.status.get_rank_from_age(chosen_cat.age)
                chosen_cat.add_to_clan()
                if chosen_cat.status.rank != rank:
                    chosen_cat.rank_change(new_rank=CatRank(rank), resort=True)
            elif outside:
                # updates so that the clan is marked as knowing of this cat
                current_standing = chosen_cat.status.get_standing_with_group(
                    CatGroup.PLAYER_CLAN_ID
                )
                if (
                    CatStanding.KNOWN not in current_standing
                    and CatStanding.EXILED not in current_standing
                ):
                    chosen_cat.status.change_standing(CatStanding.KNOWN)

            if new_name:
                name = f"{chosen_cat.name.prefix}"
                spaces = name.count(" ")
                if bool(getrandbits(1)):
                    if spaces > 0:  # adding suffix to OG name
                        # make a list of the words within the name, then add the OG name back in the list
                        words = name.split(" ")
                        words.append(name)
                        new_prefix = choice(words)  # pick new prefix from that list
                        name = new_prefix
                    chosen_cat.name.prefix = name
                    chosen_cat.name.give_suffix(
                        pelt=chosen_cat.pelt,
                        biome=game.clan.biome,
                        tortie_pattern=chosen_cat.pelt.tortie_pattern,
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
                        tortie_pattern=chosen_cat.pelt.tortie_pattern,
                    )

            new_cats = [chosen_cat]

    # Now we generate the new cat
    if not chosen_cat:
        new_cats = create_new_cat(
            Cat,
            new_name=new_name,
            kit=False if litter else rank in (CatRank.KITTEN, CatRank.NEWBORN),
            # this is for singular kits, litters need this to be false
            litter=litter,
            backstory=chosen_backstory,
            rank=rank,
            original_social=cat_social,
            original_group=cat_group,
            moons=age,
            gender=gender,
            thought=thought,
            alive=alive,
            outside=outside,
            parent1=parent1.ID if parent1 else None,
            parent2=parent2.ID if parent2 else None,
            adoptive_parents=adoptive_parents if adoptive_parents else None,
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
                start_relation.like += 40 + y
                start_relation.comfort = 40 + y
                start_relation.respect = 10 + y
                start_relation.trust = 30 + y
                n_c.relationships[inter_cat.ID] = start_relation

            # BIO PARENTS
            for par in (parent1, parent2):
                if not par:
                    continue

                y = randrange(0, 20)
                start_relation = Relationship(par, n_c, False, True)
                start_relation.like += 60 + y
                start_relation.comfort = 40 + y
                start_relation.respect = 30 + y
                start_relation.trust = 30 + y
                par.relationships[n_c.ID] = start_relation

                y = randrange(0, 20)
                start_relation = Relationship(n_c, par, False, True)
                start_relation.like += 40 + y
                start_relation.comfort = 70 + y
                start_relation.respect = 30 + y
                start_relation.trust = 60 + y
                n_c.relationships[par.ID] = start_relation

            # ADOPTIVE PARENTS
            for par in adoptive_parents:
                if not par:
                    continue

                par = Cat.fetch_cat(par)

                y = randrange(0, 20)
                start_relation = Relationship(par, n_c, False, True)
                start_relation.like += 60 + y
                start_relation.comfort = 40 + y
                start_relation.respect = 30 + y
                start_relation.trust = 30 + y
                par.relationships[n_c.ID] = start_relation

                y = randrange(0, 20)
                start_relation = Relationship(n_c, par, False, True)
                start_relation.like += 40 + y
                start_relation.comfort = 70 + y
                start_relation.respect = 30 + y
                start_relation.trust = 60 + y
                n_c.relationships[par.ID] = start_relation

            # UPDATE INHERITANCE
            n_c.create_inheritance_new_cat()

    return new_cats


def get_other_clan(clan_name):
    """
    returns the clan object of given clan name
    """
    for clan in game.clan.all_other_clans:
        if clan.name == clan_name:
            return clan


def create_new_cat(
    Cat: Union["Cat", Type["Cat"]],
    new_name: bool = False,
    kit: bool = False,
    litter: bool = False,
    backstory: bool = None,
    rank: Optional[CatRank] = None,
    original_social: CatSocial = CatSocial.CLANCAT,
    original_group: CatGroup = None,
    moons: int = None,
    gender: str = None,
    thought: str = None,
    alive: bool = True,
    outside: bool = False,
    parent1: str = None,
    parent2: str = None,
    adoptive_parents: list = None,
) -> list:
    """
    This function creates new cats and then returns a list of those cats
    :param Cat Cat: pass the Cat class
    :params Relationship Relationship: pass the Relationship class
    :param bool new_name: set True if cat(s) is a loner/rogue receiving a new Clan name - default: False
    :param bool kit: set True if the cat is a lone kitten - default: False
    :param bool litter: set True if a litter of kittens needs to be generated - default: False
    :param bool backstory: a list of possible backstories.json for the new cat(s) - default: None
    :param rank: set as the rank you want the new cat to have - default: None (will cause a random status to be picked)
    :param original_social: set as the cat's old social - default: None (cat will not be given any past social, it will
    appear that they have always been a clancat)
    :param original_group: set as the cat's old group - default: None (cat will not be given any past group)
    :param bool outside: set this as True to generate the cat as an outsider instead of as part of the Clan - default: False (Clan cat)
    :param int moons: set the age of the new cat(s) - default: None (will be random or if kit/litter is true, will be kitten.
    :param str gender: set the gender (BIRTH SEX) of the cat - default: None (will be random)
    :param str thought: if you need to give a custom "welcome" thought, set it here
    :param bool alive: set this as False to generate the cat as already dead - default: True (alive)
    :param str parent1: Cat ID to set as the biological parent1
    :param str parent2: Cat ID to set as the biological parent2
    :param list adoptive_parents: Cat IDs to set as adoptive parents
    """

    if thought is None:
        thought = i18n.t("hardcoded.thought_new_cat")

    if isinstance(backstory, list):
        backstory = choice(backstory)

    if (
        backstory
        in (
            BACKSTORIES["backstory_categories"]["former_clancat_backstories"]
            + BACKSTORIES["backstory_categories"]["baby_clancat_backstories"]
        )
        or original_social == "former Clancat"
    ) and not original_group:
        original_group = choice([x.group_ID for x in game.clan.all_other_clans])

    created_cats = []

    if not litter:
        number_of_cats = 1
    else:
        number_of_cats = choices([2, 3, 4, 5], [5, 4, 1, 1], k=1)[0]

    if not isinstance(moons, int):
        if rank == CatRank.NEWBORN:
            moons = 0
        elif litter or kit:
            moons = randint(1, 5)
        elif rank in (
            CatRank.APPRENTICE,
            CatRank.MEDICINE_APPRENTICE,
            CatRank.MEDIATOR_APPRENTICE,
        ):
            moons = randint(6, 11)
        elif rank == CatRank.WARRIOR:
            moons = randint(23, 120)
        elif rank == CatRank.MEDICINE_CAT:
            moons = randint(23, 140)
        elif rank == CatRank.ELDER:
            moons = randint(120, 130)
        else:
            moons = randint(6, 120)

    # setting rank
    if not rank and not outside:
        if moons == 0:
            rank = CatRank.NEWBORN
        elif moons < 6:
            rank = CatRank.KITTEN
        elif 6 <= moons <= 11:
            rank = CatRank.APPRENTICE
        elif moons >= 120:
            rank = CatRank.ELDER
        else:
            rank = CatRank.WARRIOR

    # need to get actual age enum
    age = CatAge.SENIOR
    for key_age in Cat.age_moons.keys():
        if moons in range(Cat.age_moons[key_age][0], Cat.age_moons[key_age][1] + 1):
            age: CatAge = key_age
            break

    # cat creation and naming time
    for index in range(number_of_cats):
        # setting gender
        if not gender:
            _gender = choice(["female", "male"])
        else:
            _gender = gender

        # first we generate the cat as though they are not part of the clan yet
        new_cat = Cat(
            moons=moons,
            status_dict={
                "social": original_social,
                "age": age,
                "group_ID": original_group,
            },
            gender=_gender,
            backstory=backstory,
            parent1=parent1,
            parent2=parent2,
            adoptive_parents=adoptive_parents if adoptive_parents else [],
        )
        # this simulates a "history" as whomever they used to be
        new_cat.status.change_current_moons_as(moons)

        # now we actually add them to the clan, if they should be joining
        if not outside and alive:
            new_cat.add_to_clan()
            # check if cat is the correct rank
            if new_cat.status.rank != rank:
                new_cat.status._change_rank(CatRank(rank))
            # give apprentice aged cat a mentor
            if new_cat.status.rank.is_any_apprentice_rank():
                new_cat.update_mentor()
                # ensuring that any cats joining as an apprentice will display the correct skills
                new_cat.skills.primary.interest_only = True
                if new_cat.skills.secondary:
                    new_cat.skills.secondary.interest_only = True

        # NAMES and accs
        # clancat adults should have already generated with a clan-ish name, thus they skip all of this re-naming
        # little babies will take a clancat name, we love indoctrination
        if (kit or litter or moons < 12) and original_group != CatGroup.OTHER_CLAN:
            # babies change name, in case their initial name isn't clan-ish
            new_cat.change_name()
        elif original_group != CatGroup.OTHER_CLAN:
            # give kittypets a kittypet name
            if original_social == CatSocial.KITTYPET:
                name = choice(names.names_dict["loner_names"])
                # check if the kittypets come with a pretty acc
                if bool(getrandbits(1)):
                    # TODO: refactor this entire function to remove this call amongst other things
                    from scripts.cat.accessory import Accessory

                    new_cat.pelt.accessory.append(Accessory.create_random_for_slot('neck'))

            # try to give name from full loner name list
            elif original_social in (CatSocial.LONER, CatSocial.ROGUE) and bool(
                getrandbits(1)
            ):
                name = choice(names.names_dict["loner_names"])
            # otherwise give name from prefix list (more nature-y names)
            else:
                name = choice(names.names_dict["normal_prefixes"])

                # now, if this cat should take a new clan name, we give them such
            if new_name:
                # check if adding suffix to OG name
                if bool(getrandbits(1)):
                    spaces = name.count(" ")
                    if spaces > 0:
                        # make a list of the words within the name, then add the OG name back in the list
                        words = name.split(" ")
                        words.append(name)
                        new_prefix = choice(words)  # pick new prefix from that list
                        new_cat.change_name(new_prefix=new_prefix)
                # else, take a whole new name
                else:
                    new_cat.change_name()
            # else, let them keep their old name
            else:
                new_cat.change_name(new_prefix=name, new_suffix="")

        # Remove disabling scars, if they generated.
        # these are removed bc the cat won't have the associated perm condition
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
                constants.CONFIG["cat_generation"]["base_permanent_condition"] / 11.25
            )
        else:
            chance = constants.CONFIG["cat_generation"]["base_permanent_condition"] + 10
        if not int(random() * chance):
            possible_conditions = []
            for condition in PERMANENT:
                if (kit or litter) and PERMANENT[condition]["congenital"] not in [
                    "always",
                    "sometimes",
                ]:
                    continue
                # next part ensures that a kit won't get a condition that takes too long to reveal
                moons = new_cat.moons
                leeway = 5 - (PERMANENT[condition]["moons_until"] + 1)
                if moons > leeway:
                    continue
                possible_conditions.append(condition)

            if possible_conditions:
                chosen_condition = choice(possible_conditions)
                if PERMANENT[chosen_condition]["congenital"] in [
                    "always",
                    "sometimes",
                ]:
                    new_cat.get_permanent_condition(chosen_condition, True)
                    if (
                        new_cat.permanent_condition[chosen_condition]["moons_until"]
                        == 0
                    ):
                        new_cat.permanent_condition[chosen_condition][
                            "moons_until"
                        ] = -2

                # assign scars
                if chosen_condition in ("lost a leg", "born without a leg"):
                    new_cat.pelt.scars.append("NOPAW")
                elif chosen_condition in ("lost their tail", "born without a tail"):
                    new_cat.pelt.scars.append("NOTAIL")

        # KILL >:D only if we're sposed to tho
        if not alive:
            new_cat.die()

        # newbie thought
        new_cat.thought = thought

        # and they exist now
        created_cats.append(new_cat)
        game.clan.add_cat(new_cat)
        new_cat.history.add_beginning()

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
        if rel.romance < 0:
            continue
        if exclude_mate and rel.cat_from.ID in rel.cat_to.mate:
            continue
        if potential_mate and not rel.cat_to.is_potential_mate(
            rel.cat_from, for_love_interest=True
        ):
            continue
        if rel.romance > max_love_value:
            current_max_relationship = rel
            max_love_value = rel.romance

    return current_max_relationship


def check_relationship_value(cat_from, cat_to, rel_value=None):
    """
    returns the value of the rel_value param given
    :param cat_from: the cat who is having the feelings
    :param cat_to: the cat that the feelings are directed towards
    :param rel_value: the relationship value that you're looking for,
    options are: romance, like, respect, comfort, trust
    """
    if cat_to.ID in cat_from.relationships:
        relationship = cat_from.relationships[cat_to.ID]
    else:
        relationship = cat_from.create_one_relationship(cat_to)

    if rel_value == RelType.ROMANCE:
        return relationship.romance
    elif rel_value == RelType.LIKE:
        return relationship.like
    elif rel_value == RelType.RESPECT:
        return relationship.respect
    elif rel_value == RelType.COMFORT:
        return relationship.comfort
    elif rel_value == RelType.TRUST:
        return relationship.trust

    return None


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
        if not inter_cat.status.alive_in_player_clan:
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
            and cat.relationships[inter_cat.ID].romance > 0
        ):
            cats.append(inter_cat)
    return cats


def get_num_of_cats_with_relation_amount_towards(cat, amount, all_cats):
    """
    Looks how many cats have the certain value
    :param cat: cat in question
    :param amount: amount of relationship value which has to be reached
    :param all_cats: list of cats which has to be checked
    """

    # collect all true or false if the value is reached for the cat or not
    # later count or sum can be used to get the amount of cats
    # this will be handled like this, because it is easier / shorter to check

    relation_dict = {v: [] for v in [*RelType]}

    for inter_cat in all_cats:
        if cat.ID in inter_cat.relationships:
            relation = inter_cat.relationships[cat.ID]
        else:
            continue

        for value in [*RelType]:
            if amount > 0:
                relation_dict[value].append(
                    relation.get_amount_of_type(value) >= amount
                )
            elif amount < 0:
                relation_dict[value].append(
                    relation.get_amount_of_type(value) <= amount
                )

    return_dict = {v: sum(relation_dict[v]) for v in [*RelType]}

    return return_dict


def filter_relationship_type(
    group: list, filter_types: List[str], event_id: str = None, patrol_leader=None
):
    """
    filters for specific types of relationships between groups of cat objects, returns bool
    :param group: the group of cats to be tested (make sure they're in the correct order (i.e. if testing for
    parent/child, the cat being tested as parent must be index 0)
    :param filter_types: the relationship types to check for.
    :param event_id: if the event has an ID, include it here
    :param patrol_leader: if you are testing a patrol, ensure you include the self.patrol_leader here
    """
    if not filter_types:
        return True

    filter_list = filter_types.copy()

    # keeping this list here just for quick reference of what tags are handled here
    all_possible_tags = [
        "siblings",
        "not_siblings",
        "littermates",
        "not_littermates",
        "mates",
        "mates_with_pl",
        "not_mates",
        "parent/child",
        "not_parent",
        "child/parent",
        "not_child",
        "mentor/app",
        "not_mentor",
        "app/mentor",
        "not_app",
    ]
    for tier_list in rel_type_tiers.values():
        all_possible_tags.extend(tier_list)
        all_possible_tags.extend([f"{l}_only" for l in tier_list])
    if not set(filter_list).issubset(set(all_possible_tags)):
        print(
            f"WARNING: {[tag for tag in filter_list if tag not in all_possible_tags]} is not a valid relationship_status tag!"
        )

    if patrol_leader:
        if patrol_leader in group:
            group.remove(patrol_leader)
        group.insert(0, patrol_leader)

    if "siblings" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if not all([test_cat.is_sibling(inter_cat) for inter_cat in testing_cats]):
            return False
        filter_list.remove("siblings")

    if "not_siblings" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([test_cat.is_sibling(inter_cat) for inter_cat in testing_cats]):
            return False
        filter_list.remove("not_siblings")

    if "littermates" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if not all([test_cat.is_littermate(inter_cat) for inter_cat in testing_cats]):
            return False
        filter_list.remove("littermates")

    if "not_littermates" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([test_cat.is_littermate(inter_cat) for inter_cat in testing_cats]):
            return False

        filter_list.remove("not_littermates")

    if "mates" in filter_list:
        # first test if more than one cat
        if len(group) == 1:
            return False

        # then if cats don't have the needed number of mates
        if not all(len(i.mate) >= (len(group) - 1) for i in group):
            return False

        # Now the expensive test.  We have to see if everyone is mates with each other
        # Hopefully the cheaper tests mean this is only needed on events with a small number of cats
        for x in combinations(group, 2):
            if x[0].ID not in x[1].mate:
                return False
        filter_list.remove("mates")

    # check if all cats are mates with p_l (they do not have to be mates with each other)
    if "mates_with_pl" in filter_list:
        # First test if there is more than one cat
        if len(group) == 1:
            return False

        # Check each cat to see if it is mates with the patrol leader
        for cat in group:
            if cat.ID == patrol_leader.ID:
                continue
            if cat.ID not in patrol_leader.mate:
                return False
        filter_list.remove("mates_with_pl")

    # Check if all cats are not mates
    if "not_mates" in filter_list:
        # opposite of mate check
        for x in combinations(group, 2):
            if x[0].ID in x[1].mate:
                return False
        filter_list.remove("not_mates")

    # Check if the cats are in a parent/child relationship
    if "parent/child" in filter_list:
        # It should be exactly two cats for a "parent/child" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[0].is_parent(group[1]):
            return False
        filter_list.remove("parent/child")

    if "not_parent" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([test_cat.is_parent(inter_cat) for inter_cat in testing_cats]):
            return False
        filter_list.remove("not_parent")

    if "child/parent" in filter_list:
        # It should be exactly two cats for a "child/parent" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[1].is_parent(group[0]):
            return False
        filter_list.remove("child/parent")

    if "not_child" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([inter_cat.is_parent(test_cat) for inter_cat in testing_cats]):
            return False
        filter_list.remove("not_child")

    if "mentor/app" in filter_list:
        # It should be exactly two cats for a "mentor/app" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[1].ID in group[0].apprentice:
            return False
        filter_list.remove("mentor/app")

    if "not_mentor" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([inter_cat in test_cat.apprentice for inter_cat in testing_cats]):
            return False
        filter_list.remove("not_mentor")

    if "app/mentor" in filter_list:
        # It should be exactly two cats for a "app/mentor" event
        if len(group) != 2:
            return False
        # test for parentage
        if not group[0].ID in group[1].apprentice:
            return False
        filter_list.remove("app/mentor")

    if "not_app" in filter_list:
        test_cat = group[0]
        testing_cats = [cat for cat in group if cat.ID != test_cat.ID]

        if any([inter_cat in test_cat.mentor for inter_cat in testing_cats]):
            return False
        filter_list.remove("not_app")

    # Filtering relationship values
    # each cat has to have relationships toward each other matching every level tag
    for tier in filter_list:
        for inter_cat in group:
            if len(group) == 2 and inter_cat == group[1]:
                # if this is a two cat group, then we only look for the first cat's rel toward the second cat.
                # groups > 2 will require that all cats feel the same way toward each other.
                continue
            group_ids = [cat.ID for cat in group]

            relevant_relationships = [
                rel
                for rel in inter_cat.relationships.values()
                if rel.cat_to.ID in group_ids and rel.cat_to.ID != inter_cat.ID
            ]

            # list of every cat's tier list
            group_lists: list[RelTier] = [
                rel.get_reltype_tiers() for rel in relevant_relationships
            ]

            # now test each list to see if the required tag is inside
            for tier_list in group_lists:
                # just a quick check to see if we can avoid all the extra hullabaloo
                if tier in tier_list:
                    continue

                # if it's limited to *just* the given tier
                if "_only" in tier:
                    tier.replace("_only", "")
                    if tier not in tier_list:
                        return False
                # otherwise we allow both the given tier and any greater tiers
                else:
                    # finding the matching tier enum
                    rel_tier: RelTier = RelTier(tier)

                    # find the matching rel_type enum
                    rel_type: Optional[RelType] = None
                    for rel_type in rel_type_tiers:
                        if rel_tier in rel_type_tiers[rel_type]:
                            rel_type = rel_type
                            break
                    if not rel_type:
                        continue

                    # get the tier's index within the rel_types's list
                    index = rel_type_tiers[rel_type].index(rel_tier)
                    allowed_levels = []
                    # if it's a pos tier, we allow that index and higher
                    if rel_tier.is_any_pos:
                        allowed_levels = rel_type_tiers[rel_type][index:]
                    # if it's a neg tier, we allow that index and lower
                    elif rel_tier.is_any_neg:
                        allowed_levels = rel_type_tiers[rel_type][0:index]

                    discard = True
                    for l in tier_list:
                        if l in allowed_levels:
                            discard = False
                            break
                    if discard:
                        return False

    return True


def gather_cat_objects(
    Cat, abbr_list: List[str], event, stat_cat=None, extra_cat=None
) -> list:
    """
    gathers cat objects from list of abbreviations used within an event format block
    :param Cat Cat: Cat class
    :param list[str] abbr_list: The list of abbreviations
    :param event: the controlling class of the event (e.g. Patrol, HandleShortEvents), default None
    :param Cat stat_cat: if passing the Patrol class, must include stat_cat separately
    :param Cat extra_cat: if not passing an event class, include the single affected cat object here. If you are not
    passing a full event class, then be aware that you can only include "m_c" as a cat abbreviation in your rel block.
    The other cat abbreviations will not work.
    :return: list of cat objects
    """

    clan_cats = [x for x in Cat.all_cats_list if x.status.alive_in_player_clan]
    out_set = set()

    for abbr in abbr_list:
        if abbr == "m_c":
            if extra_cat:
                out_set.add(extra_cat)
            else:
                out_set.add(event.main_cat)
        elif abbr == "r_c":
            out_set.add(event.random_cat)
        elif re.match(r"n_c:[0-9]+", abbr):
            index = re.match(r"n_c:([0-9]+)", abbr).group(1)
            index = int(index)
            if index < len(event.new_cats):
                out_set.update(event.new_cats[index])
        # PATROL SPECIFIC
        elif abbr == "p_l":
            out_set.add(event.patrol_leader)
        elif abbr == "s_c":
            out_set.add(stat_cat)
        elif abbr == "app1" and len(event.patrol_apprentices) >= 1:
            out_set.add(event.patrol_apprentices[0])
        elif abbr == "app2" and len(event.patrol_apprentices) >= 2:
            out_set.add(event.patrol_apprentices[1])
        elif abbr == "app3" and len(event.patrol_apprentices) >= 3:
            out_set.add(event.patrol_apprentices[2])
        elif abbr == "app4" and len(event.patrol_apprentices) >= 4:
            out_set.add(event.patrol_apprentices[3])
        elif abbr == "app5" and len(event.patrol_apprentices) >= 5:
            out_set.add(event.patrol_apprentices[4])
        elif abbr == "app6" and len(event.patrol_apprentices) >= 6:
            out_set.add(event.patrol_apprentices[5])
        elif abbr == "patrol":
            out_set.update(event.patrol_cats)
        elif abbr == "multi":
            cat_num = randint(1, max(1, len(event.patrol_cats) - 1))
            out_set.update(sample(event.patrol_cats, cat_num))
        # OVERALL CLAN CATS
        elif abbr == "clan":
            out_set.update(clan_cats)
        elif abbr == "some_clan":  # 1 / 8 of clan cats are affected
            out_set.update(
                sample(clan_cats, randint(1, max(1, round(len(clan_cats) / 8))))
            )
        # FACET CATS IN CLAN
        elif abbr == "high_social":
            out_set = {c for c in out_set if c.personality.sociability > 8}
        elif abbr == "low_social":
            out_set = {c for c in out_set if c.personality.sociability <= 8}
        elif abbr == "high_lawful":
            out_set = {c for c in out_set if c.personality.lawfulness > 8}
        elif abbr == "low_lawful":
            out_set = {c for c in out_set if c.personality.lawfulness <= 8}
        elif abbr == "high_stable":
            out_set = {c for c in out_set if c.personality.stability > 8}
        elif abbr == "low_stable":
            out_set = {c for c in out_set if c.personality.stability <= 8}
        elif abbr == "high_aggress":
            out_set = {c for c in out_set if c.personality.aggression > 8}
        elif abbr == "low_aggress":
            out_set = {c for c in out_set if c.personality.aggression <= 8}

        else:
            print(f"WARNING: Unsupported abbreviation {abbr}")

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
    possible_values = [*RelType]

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
        value_changes = {}

        for val in [*RelType]:
            if val in values:
                value_changes[val] = amount
                if amount > 0:
                    positive = True

        if positive:
            effect = i18n.t("relationships.positive_postscript")
        else:
            effect = i18n.t("relationships.negative_postscript")

        # Get log
        to_log = None
        from_log = None
        if "log" in block:
            to_log = block["log"].get("cats_to") + effect
            from_log = block["log"].get("cats_from") + effect
            if not to_log and not from_log:
                print(f"something is wrong with relationship log: {block['log']}")

        change_relationship_values(
            cats_to_ob,
            cats_from_ob,
            **value_changes,
            log=from_log,
        )

        if block.get("mutual"):
            change_relationship_values(
                cats_from_ob,
                cats_to_ob,
                **value_changes,
                log=to_log,
            )


def change_relationship_values(
    cats_to: list,
    cats_from: list,
    romance: int = 0,
    like: int = 0,
    respect: int = 0,
    comfort: int = 0,
    trust: int = 0,
    log: str = None,
):
    """
    changes relationship values according to the parameters.

    :param list[Cat] cats_from: list of cat objects whose rel values will be affected
    (e.g. cat_from loses trust in cat_to)
    :param list[Cat] cats_to: list of cats objects who are the target of that rel value
    (e.g. cat_from loses trust in cat_to)
    :param int romance: amount to change romantic, default 0
    :param int like: amount to change platonic, default 0
    :param int respect: amount to change admiration (respect), default 0
    :param int comfort: amount to change comfort, default 0
    :param int trust: amount to change trust, default 0
    :param str log: the string to append to the relationship log of cats involved
    """

    # This is just for test prints - DON'T DELETE - you can use this to test if relationships are changing
    """changed = False
    if romance == 0 and like == 0 and respect == 0 and \
            comfort == 0 and trust == 0:
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
                # now gain the romance
                rel.romance += romance

            # gain other rel values
            rel.like += like
            rel.respect += respect
            rel.comfort += comfort
            rel.trust += trust

            # for testing purposes - DON'T DELETE - you can use this to test if relationships are changing
            """
            print(str(single_cat_from.name) + " gained relationship with " + str(rel.cat_to.name) + ": " +
                  "Romance: " + str(romance) +
                  " /Like: " + str(like) +
                  " /Respect: " + str(respect) +
                  " /Comfort: " + str(comfort) +
                  " /Trust: " + str(trust)) if changed else print("No relationship change")"""

            if log and isinstance(log, str):
                log_text = log + i18n.t(
                    "relationships.age_postscript",
                    name=str(single_cat_to.name),
                    count=single_cat_to.moons,
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
    if game.clan.instructor.status.group == CatGroup.DARK_FOREST:
        return i18n.t("cat.history.leader_lives_left_df", count=game.clan.leader_lives)
    return i18n.t("cat.history.leader_lives_left_sc", count=game.clan.leader_lives)


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
    """
    Helper function for add_pronouns.
    :param m: Snippet to pronounify
    :param cat_pronouns_dict: Cats to pronounify
    :param raise_exception: If True, will raise an exception if a mistake is found. Necessary for tests!
    :return: Appropriate pronoun/verb/adjective
    :raises KeyError: if cat doesn't have requested pronoun
    :raises IndexError: if cat doesn't have requested pronoun
    """

    # Add protection about the "insert" sometimes used
    if m.group(0) == "{insert}":
        return m.group(0)

    inner_details = m.group(1).split("/")
    out = None

    try:
        if inner_details[1].upper() == "PLURAL":
            inner_details.pop(1)  # remove plural tag so it can be processed as normal
            catlist = []
            for cat in inner_details[1].split("+"):
                try:
                    catlist.append(cat_pronouns_dict[cat][1])
                except KeyError as e:
                    print(f"Missing pronouns for {cat}")
                    if raise_exception:
                        raise e
                    continue
            d = determine_plural_pronouns(catlist)
        else:
            try:
                d = cat_pronouns_dict[inner_details[1]][1]
            except KeyError as e:
                if raise_exception:
                    raise e

                if inner_details[0].upper() == "ADJ":
                    # find the default - this is a semi-expected behaviour for the adj tag as it may be called when
                    # there is no relevant cat
                    return inner_details[localization.get_default_adj()]
                else:
                    logger.warning(
                        f"Could not get pronouns for {inner_details[1]}. Using default."
                    )
                    print(
                        f"Could not get pronouns for {inner_details[1]}. Using default."
                    )
                    d = choice(localization.get_new_pronouns("default"))

        if inner_details[0].upper() == "PRONOUN":
            out = d[inner_details[2]]
        elif inner_details[0].upper() == "VERB":
            out = inner_details[d["conju"] + 1]
        elif inner_details[0].upper() == "ADJ":
            out = inner_details[(d["gender"] + 2) if "gender" in d else 2]

        if out is not None:
            if inner_details[-1] == "CAP":
                out = out.capitalize()
            return out

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
        r"(?<!%)\{(.*?)}", lambda x: pronoun_repl(x, cat_dict, raise_exception), text
    )

    name_patterns = [r"(?<!\{)" + re.escape(l) + r"(?!\})" for l in cat_dict]
    adjust_text = re.sub(
        "|".join(name_patterns), lambda x: name_repl(x, cat_dict), adjust_text
    )
    return adjust_text


def adjust_list_text(list_of_items: List) -> str:
    """
    returns the list in correct grammar format (i.e. item1, item2, item3 and item4)
    this works with any number of items
    :param list_of_items: the list of items you want converted
    :return: the new string
    """

    if not isinstance(list_of_items, list):
        logger.warning("non-list object was passed to adjust_list_text")
        list_of_items = list(list_of_items)

    if len(list_of_items) == 0:
        item1 = ""
        item2 = ""
    elif len(list_of_items) == 1:
        item1 = list_of_items[0]
        item2 = ""
    elif len(list_of_items) == 2:
        item1 = list_of_items[0]
        item2 = list_of_items[1]
    else:
        item1 = ", ".join(list_of_items[:-1])
        if get_lang_config().get("oxford_comma"):
            item1 += ","
        item2 = list_of_items[-1]

    return i18n.t("utility.items", count=len(list_of_items), item1=item1, item2=item2)


def adjust_prey_abbr(patrol_text):
    """
    checks for prey abbreviations and returns adjusted text
    """
    global PREY_LISTS
    if langs["prey"] != i18n.config.get("locale"):
        langs["prey"] = i18n.config.get("locale")
        PREY_LISTS = load_lang_resource("patrols/prey_text_replacements.json")

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
    biome = (
        game.clan.biome if not game.clan.override_biome else game.clan.override_biome
    ).casefold()
    global SNIPPETS
    if langs["snippet"] != i18n.config.get("locale"):
        langs["snippet"] = i18n.config.get("locale")
        SNIPPETS = load_lang_resource("snippet_collections.json")

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
    else:
        logger.error("WARNING: no list type found for %s", list_text)
        return text, None, None, None

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
        text = text.replace("c_n", clan.displayname)
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
        kitty = choice(
            find_alive_cats_with_rank(Cat, [CatRank.MEDICINE_CAT], working=True)
        )
        cat_dict["med_name"] = (str(kitty.name), choice(kitty.pronouns))

    if cat_dict:
        text = process_text(text, cat_dict)

    if other_clan_name:
        text = text.replace("o_c_n", other_clan_name)
    if clan:
        clan_name = str(clan.displayname)
    else:
        if game.clan is None:
            # todo can this be Switch.clan_name ?
            clan_name = switch_get_value(Switch.clan_list)[0]
        else:
            clan_name = str(game.clan.displayname)

    text = text.replace("c_n", clan_name + "Clan")

    return text


def event_text_adjust(
    Cat: Type["Cat"],
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
    if not patrol_apprentices:
        patrol_apprentices = []
    if not new_cats:
        new_cats = []

    if not text:
        text = "This should not appear, report as a bug please! Tried to adjust the text, but no text was provided."
        print("WARNING: Tried to adjust text, but no text was provided.")

    # this check is really just here to catch odd bug edge-cases from old saves, specifically in death history
    # otherwise we should really *never* have lists being passed as the text
    if isinstance(text, list):
        text = text[0]

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
                pronoun = localization.get_new_pronouns("default plural")[0]
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
        med = choice(
            find_alive_cats_with_rank(Cat, [CatRank.MEDICINE_CAT], working=True)
        )
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
    if "o_c_n" in text and other_clan:
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
            clan_name = clan.displayname
        except AttributeError:
            # todo can this be Switch.clan_name ?
            clan_name = switch_get_value(Switch.clan_list)[0]

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
    if main_cat:
        if "acc_plural" in text:
            text = text.replace(
                "acc_plural",
                i18n.t(f"cat.accessories.{main_cat.pelt.accessory[-1]}", count=2),
            )

        # acc_singular (only works for main_cat's acc)
        if "acc_singular" in text:
            text = text.replace(
                "acc_singular",
                i18n.t(f"cat.accessories.{main_cat.pelt.accessory[-1]}", count=1),
            )

        if "given_herb" in text:
            text = text.replace(
                "given_herb", i18n.t(f"conditions.herbs.{chosen_herb}", count=2)
            )

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

    text = text.replace("c_n", str(game.clan.displayname) + "Clan")

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
    clanname = str(game.clan.displayname + "Clan")

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


def get_pronouns(cat: "Cat"):
    """Get a cat's pronoun even if the cat has faded to prevent crashes (use gender-neutral pronouns when the cat has faded)"""
    if not cat.pronouns:
        # since get_new_pronouns returns a list with length 1
        return localization.get_new_pronouns("default")[0]
    else:
        return choice(cat.pronouns)


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
        (
            floor(dim[0] * scripts.game_structure.screen_settings.screen_scale)
            if dim[0] > 0
            else dim[0]
        ),
        (
            floor(dim[1] * scripts.game_structure.screen_settings.screen_scale)
            if dim[1] > 0
            else dim[1]
        ),
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


def update_mask(cat):
    if cat.faded or cat.dead:
        # should never need a mask since they can't appear on the Clan screen
        cat.sprite_mask = None
        return

    val = pygame.mask.from_surface(
        pygame.transform.scale(cat.sprite, ui_scale_dimensions((50, 50))), threshold=250
    )

    inflated_mask = pygame.Mask(
        (
            val.get_size()[0] + 10,
            val.get_size()[1] + 10,
        )
    )
    inflated_mask.draw(val, (5, 5))
    for _ in range(3):
        outline = inflated_mask.outline()
        for point in outline:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    try:
                        inflated_mask.set_at((point[0] + dx, point[1] + dy), 1)
                    except IndexError:
                        continue
    cat.sprite_mask = inflated_mask


def clan_symbol_sprite(clan, return_string=False, force_light=False):
    """
    returns the clan symbol for the given clan_name, if no symbol exists then random symbol is chosen
    :param clan: the clan object
    :param return_string: default False, set True if the sprite name string is required rather than the sprite image
    :param force_light: Set true if you want this sprite to override the dark/light mode changes with the light sprite
    """
    if not clan.chosen_symbol:
        possible_sprites = []
        for sprite in sprites.clan_symbols:
            name = sprite.strip("1234567890")
            if f"symbol{clan.name.upper()}" == name:
                possible_sprites.append(sprite)
        if possible_sprites:
            clan.chosen_symbol = choice(possible_sprites)
        else:
            # give random symbol if no matching symbol exists
            print(
                f"WARNING: attempted to return symbol, but there's no clan symbol for {clan.name.upper()}. "
                f"Random chosen."
            )
            clan.chosen_symbol = choice(sprites.clan_symbols)

    if return_string:
        return clan.chosen_symbol
    else:
        return sprites.get_symbol(clan.chosen_symbol, force_light=force_light)


def generate_sprite(
    cat,
    life_state=None,
    scars_hidden=False,
    acc_hidden=False,
    always_living=False,
    disable_sick_sprite=False,
) -> pygame.Surface:
    """
    Generates the sprite for a cat, with optional arguments that will override certain things.

    :param life_state: sets the age life_stage of the cat, overriding the one set by its age. Set to string.
    :param scars_hidden: If True, doesn't display the cat's scars. If False, display cat scars.
    :param acc_hidden: If True, hide the accessory. If false, show the accessory.
    :param always_living: If True, always show the cat with living lineart
    :param disable_sick_sprite: If true, never use the not_working lineart.
                    If false, use the cat.not_working() to determine the no_working art.
    """
    sprite_poses = sprites.POSE_DATA["poses"]

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
            not disable_sick_sprite
            and cat.not_working()
            and age != CatAge.NEWBORN
            and constants.CONFIG["cat_sprites"]["sick_sprites"]
    ):

        if cat.pelt.length == "long":
            if age in CatAge.KITTEN:
                cat_sprite = str(49)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(51)
            elif age in CatAge.SENIOR:
                cat_sprite = str(55)
            else:
                cat_sprite = str(53)
        else:
            if age in CatAge.KITTEN:
                cat_sprite = str(48)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(50)
            elif age in CatAge.SENIOR:
                cat_sprite = str(54)
            else:
                cat_sprite = str(52)

    elif cat.pelt.paralyzed and age != "newborn":
        if cat.pelt.length == "long":
            if age in CatAge.KITTEN:
                cat_sprite = str(41)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(43)
            elif age in CatAge.SENIOR:
                cat_sprite = str(47)
            else:
                cat_sprite = str(45)
        else:
            if age in CatAge.KITTEN:
                cat_sprite = str(40)
            elif age in CatAge.ADOLESCENT:
                cat_sprite = str(42)
            elif age in CatAge.SENIOR:
                cat_sprite = str(46)
            else:
                cat_sprite = str(44)

    if constants.CONFIG["fun"]["all_cats_are_newborn"]:
        cat_sprite = str(cat.pelt.cat_sprites["newborn"])
    else:
        cat_sprite = str(cat.pelt.cat_sprites[age])

    new_sprite = pygame.Surface(
        (sprites.size, sprites.size), pygame.HWSURFACE | pygame.SRCALPHA
    )

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
            "CEDAR": ["#fff0d7", "#ffd8b1", "#e4b081", "#a66957", "#163138", "#091b20"],
            "COPPER": ["#f6ebd5", "#c39548", "#af773a", "#7f552f", "#3a2011", "#1c0900"],
            "BLUE GOLDEN": ["#feefd2", "#f0c785", "#d6a16d", "#a9a18a", "#8b8a86", "#5b5b5b"],
            "DEER": ["#e0cfb5", "#a38f78", "#9d8364", "#6d5744", "#4a301d", "#281609"],
            "GINGER CROW": ["#3f3f4d", "#222229", "#181821", "#7b300b", "#692200", "#05050a"],
            "STORM": ["#70838e", "#5a6873", "#4b5b6b", "#3d4e5d", "#364452", "#273644"],
            "OCEAN": ["#8daf97", "#4f7077", "#374560", "#181b3a", "#0a1437", "#000614"],
            "PALE ROSE": ["#fffaf6", "#fde8de", "#fedbd2", "#ffccc4", "#ffa7b3", "#e56c88"],
            "PALE SILVER": ["#fafcff", "#f3ecea", "#f3ecea", "#f3ecea", "#453b3a", "#1f1a19"],
            "CROW": ["#867b8c", "#5c5463", "#3e3846", "#2f2935", "#211b27", "#0a070e"],
            "RAVEN": ["#aaa4c6", "#7b7696", "#454060", "#2b2549", "#171133", "#09061b"],
            "SUNSHINE": ["#f7ebd7", "#f7e0a7", "#f9cc91", "#c46032", "#943b26", "#5e0800"],
            "DARK EMBER": ["#dd9a6a", "#993928", "#854848", "#563a3b", "#351d21", "#1f0b0f"]

        }

        # SPRITE GENERATION
        # thank you Kori ;-;
        base_name = None
        base_color = None
        tortie_base_pattern = None
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

        #tuft pieces
        tuft_type = None
        tuft_color = str(cat.pelt.tuft_color)
        tuft_tint = None
        tuft_pelt = None
        tuft_line = None
        tuft_line_tint = None

        if cat.pelt.tortie_tuft:
            tuft_base_color = str(cat.pelt.tortie_colour).upper()
        else:
            tuft_base_color = str(cat.pelt.colour).upper()

        if cat.pelt.tuft is not None:
            tuft_type = str(cat.pelt.tuft)
            if tuft_color == "BASE":
                tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_tint.fill(color_dict[tuft_base_color][1])
                tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_line_tint.fill(color_dict[tuft_base_color][5])
                tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            if tuft_color == "HIGHLIGHT":
                tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_tint.fill(color_dict[tuft_base_color][0])
                tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_line_tint.fill(color_dict[tuft_base_color][5])
                tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            if tuft_color == "MID":
                tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_tint.fill(color_dict[tuft_base_color][2])
                tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_line_tint.fill(color_dict[tuft_base_color][5])
                tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            if tuft_color == "DARK":
                tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_tint.fill(color_dict[tuft_base_color][3])
                tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_line_tint.fill(color_dict[tuft_base_color][5])
                tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            if tuft_color == "SHADE":
                tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_tint.fill(color_dict[tuft_base_color][4])
                tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                tuft_line_tint.fill(color_dict[tuft_base_color][5])
                tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            if tuft_color == "WHITE":
                if cat.pelt.white_patches_tint == "black":
                    tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                    tuft_tint.fill(color_dict["BLACK"][0])
                    tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                    tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                    tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                    tuft_line_tint.fill(color_dict["BLACK"][5])
                    tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                    tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                else:
                    tuft_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                    tuft_tint.fill(color_dict["WHITE"][0])
                    tuft_pelt = sprites.sprites['tufts' + tuft_type + cat_sprite].copy().convert_alpha()
                    tuft_pelt.blit(tuft_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

                    tuft_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                    tuft_line_tint.fill(color_dict["WHITE"][5])
                    tuft_line = sprites.sprites['tuftlines' + tuft_type + cat_sprite].copy().convert_alpha()
                    tuft_line.blit(tuft_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


            new_sprite.blit(tuft_pelt, (0, 0))
            new_sprite.blit(tuft_line, (0, 0))





        # Hello! I'm sorry
        base_name = None
        base_color = None
        tortie_base_pattern = None
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


        if cat.pelt.name not in ['Tortie', 'Calico']:
            base_name = str(cat.pelt.name).upper()
            base_color = str(cat.pelt.colour).upper()

        else:
            base_name = str(cat.pelt.tortiebase).upper()
            base_color = str(cat.pelt.colour).upper()
            tortie_base_pattern = str(cat.pelt.tortiepattern).upper()
            tortie_color = str(cat.pelt.tortie_colour).upper()

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
        if cat.pelt.name in ['Tortie', 'Calico']:
            tortie_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_base_tint.fill(color_dict[tortie_color][1])
            tortie_base_pelt = sprites.sprites['baseSOLID' + cat_sprite].copy().convert_alpha()
            tortie_base_pelt.blit(tortie_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_unders_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_unders_tint.fill(color_dict[tortie_color][0])
            tortie_unders_pelt = sprites.sprites['under' + tortie_base_pattern + cat_sprite].copy().convert_alpha()
            tortie_unders_pelt.blit(tortie_unders_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_mid_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_mid_tint.fill(color_dict[tortie_color][2])
            tortie_mid_pelt = sprites.sprites['mid' + tortie_base_pattern + cat_sprite].copy().convert_alpha()
            tortie_mid_pelt.blit(tortie_mid_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_dark_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_dark_tint.fill(color_dict[tortie_color][3])
            tortie_dark_pelt = sprites.sprites['dark' + tortie_base_pattern + cat_sprite].copy().convert_alpha()
            tortie_dark_pelt.blit(tortie_dark_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_shade_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_shade_tint.fill(color_dict[tortie_color][4])
            tortie_shade_pelt = sprites.sprites['shade' + tortie_base_pattern + cat_sprite].copy().convert_alpha()
            tortie_shade_pelt.blit(tortie_shade_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            tortie_highlight_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tortie_highlight_tint.fill(color_dict[tortie_color][0])
            tortie_highlight_pelt = sprites.sprites['highlight' + tortie_base_pattern + cat_sprite].copy().convert_alpha()
            tortie_highlight_pelt.blit(tortie_highlight_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        if tortie_base_pattern:
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

        if tortie_base_pattern:
            patches = sprites.sprites["baseSOLID" + cat_sprite].copy().convert_alpha()
            patches.blit(tortie_base_pelt, (0, 0))
            patches.blit(tortie_unders_pelt, (0, 0))
            patches.blit(tortie_mid_pelt, (0, 0))
            patches.blit(tortie_dark_pelt, (0, 0))
            patches.blit(tortie_shade_pelt, (0, 0))
            patches.blit(tortie_highlight_pelt, (0, 0))
            patches.blit(tortie_line_pelt, (0, 0))
            patches.blit(sprites.sprites["tortiemask" + cat.pelt.tortie_pattern + cat_sprite], (0, 0),
                         special_flags=pygame.BLEND_RGBA_MULT)
            new_sprite.blit(patches, (0, 0))

        # TINTS
        if (
            cat.pelt.tint is not None
            and cat.pelt.tint in sprites.cat_tints["tint_colours"]
        ):
            # Multiply with alpha does not work as you would expect - it just lowers the alpha of the
            # entire surface. To get around this, we first blit the tint onto a white background to dull it,
            # then blit the surface onto the sprite with pygame.BLEND_RGB_MULT
            tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
            tint.fill(tuple(sprites.cat_tints["tint_colours"][cat.pelt.tint]))
            new_sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if (
            cat.pelt.tint is not None
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
            "MINT": ["#d5f0e6", "#71fac7", "#0cc18b", "#009d6b"],
            "OCEAN": ["#bbe7f6", "#2bc7fb", "#0085e6", "#21239d"],
            "URANIUM": ["#025e00", "#39cf00", "#aaff00", "#547f00"],
            "PLUTONIUM": ["#005e7b", "#00c0c0", "#00ffff", "#007f7f"],
            "PHANTOM": ["#cce7f4", "#787aa0", "#f8d34f", "#5f6187"],
            "PLUMERIA": ["#eae0c9", "#e7c36e", "#e5596f", "#e97c3d"],
            "HYDRANGEA": ["#ebc7f0", "#ec8afb", "#362abe", "#cb32a4"],
            "GHOST": ["#ececec", "#cccccc", "#e95e73", "#b4afba"],
            "PASSION FRUIT": ["#edca75", "#f1ac06", "#bc003f", "#692a59"],
            "LIGHT ROSE": ["#f3f2db", "#fffaa3", "#f67cb3", "#f2559c"],
            "STORM": ["#d8e1d6", "#b9c8b6", "#929b90", "#848b82"],
            "OMEN": ["#848b82", "#be8585", "#764848", "#593535"],
            "PEACH": ["#fffcf8", "#f9e999", "#e79870", "#da7440"],
            "GLASS": ["#fffcf8", "#c0c5d8", "#5ea3d3", "#846ca0"],
            "HABANERO": ["#f9f0de", "#fbc04f", "#f25f1d", "#cd2218"],
            "MANGO": ["#f6eacc", "#fbd26c", "#fb9a26", "#f87040"],
            "VIOLET": ["#d3beed", "#b484ed", "#a759e8", "#4a009a"],
            "CHERRY": ["#edcbc7", "#f74a32", "#d2101e", "#b00006"],
            "STRAWBERRY": ["#edcbc7", "#f36f5d", "#c9333e", "#a6292e"],
            "FIG": ["#d88485", "#ce2427", "#6d407e", "#5b1f3a"],

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

        if cat.pelt.eye_pattern != None:
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

        if cat.pelt.eye_pattern != None:
            second_eye = sprites.sprites['eyebase' + cat_sprite].copy().convert_alpha()
            second_eye.blit(hc_eye_base, (0, 0))
            second_eye.blit(hc_eye_mid, (0, 0))
            second_eye.blit(hc_eye_top, (0, 0))
            second_eye.blit(hc_eye_shade, (0, 0))
            second_eye.blit(sprites.sprites["eyes2" + cat.pelt.eye_pattern + cat_sprite], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            new_sprite.blit(second_eye, (0, 0))

        new_sprite.blit(sprites.sprites["eyelight" + cat_sprite], (0, 0))

        lineart_dict = {
            "BLACK": ["#000000"],
            "RED": ["#410000"],
            "BLUE": ["#94C7E3"],
            "PURPLE": ["#382B4F"]
        }

        if not dead:
            if constants.CONFIG["moss"]["black_lineart"]:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLACK"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
        elif cat.status.group == CatGroup.UNKNOWN_RESIDENCE:
            if constants.CONFIG["moss"]["black_lineart"]:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["BLACK"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
            else:
                black_line_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
                black_line_tint.fill(lineart_dict["PURPLE"][0])
                black_line_pelt = sprites.sprites['line' + cat_sprite].copy().convert_alpha()
                black_line_pelt.blit(black_line_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                new_sprite.blit(black_line_pelt, (0, 0))
        elif cat.status.group == CatGroup.DARK_FOREST:
            if constants.CONFIG["moss"]["black_lineart"]:
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
            if constants.CONFIG["moss"]["black_lineart"]:
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
            "LIGHTBLUE": ["#5f676b"],
            "PALE": ["#d1ccd8"],
            "WARMBROWN": ["#955a37"],
            "PALEBROWN": ["#af9173"],
            "PLUM": ["#754544"],
            "PURPLE": ["#6a525a"],
            "BERRY": ["#894a50"],
            "DARKRED": ["#8c391a"],
            "DARKORANGE": ["#c37251"],
            "ORANGE": ["#da7e51"],
            "GOLD": ["#c3875a"],
            "LEMON": ["#f0b080"],
            "DARKPINK": ["#a37275"],
            "BRIGHTPINK": ["#ffa097"],
            "APRICOT": ["#f9b6a0"]
        }

        skin_color = str(cat.pelt.skin_color).upper()
        skin_name = str(cat.pelt.skin).upper()
        skin_base = None

        skin_base_tint = pygame.Surface((sprites.size, sprites.size)).convert_alpha()
        skin_base_tint.fill(skincolor_dict[skin_color][0])
        skin_base = sprites.sprites['skin' + skin_name + cat_sprite].copy().convert_alpha()
        skin_base.blit(skin_base_tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        new_sprite.blit(skin_base, (0, 0))

        # if not scars_hidden:
        #     for scar in cat.pelt.scars:
        #         if scar in cat.pelt.scars1:
        #             new_sprite.blit(
        #                 sprites.sprites["scars" + scar + cat_sprite], (0, 0)
        #             )
        #         if scar in cat.pelt.scars3:
        #             new_sprite.blit(
        #                 sprites.sprites["scars" + scar + cat_sprite], (0, 0)
        #             )
        #         if scar in cat.pelt.scars2:
        #             new_sprite.blit(
        #                 sprites.sprites["scars" + scar + cat_sprite],
        #                 (0, 0),
        #                 special_flags=blendmode,
        #             )
        #         if scar in cat.pelt.scars4:
        #             new_sprite.blit(
        #                 sprites.sprites["scarscolor" + scar + cat_sprite], (0, 0)
        #             )

       #  draw accessories
       # from scripts.cat.pelts import Pelt

       # if not acc_hidden and cat.pelt.accessory:
       #     cat_accessories = cat.pelt.accessory
       #     for accessory in cat_accessories:
       #                 if accessory.event == "plant":
       #                     sprite_name = f"{sprites.PLANT_DATA['spritesheet']}{accessory}{cat_sprite}"
       #                     new_sprite.blit(
       #                         _recolor_lineart(
       #                             sprites.sprites[sprite_name],
       #                             lineart_color,
       #                             gradient_surface,
       #                         ),
       #                         (0, 0),
       #                     )
       #                 elif accessory.event == "wild":
       #                     sprite_name = f"{sprites.WILD_DATA['spritesheet']}{accessory}{cat_sprite}"
       #                     new_sprite.blit(
       #                         _recolor_lineart(
       #                             sprites.sprites[sprite_name],
       #                             lineart_color,
       #                             gradient_surface,
       #                         ),
       #                         (0, 0),
       #                     )
       #                 elif accessory.event == "neck":
       #                     sprite_name = f"{sprites.COLLAR_DATA['spritesheet']}{accessory}{cat_sprite}"
       #                     new_sprite.blit(
       #                         _recolor_lineart(
       #                             sprites.sprites[sprite_name],
       #                             lineart_color,
       #                             gradient_surface,
       #                         ),
       #                         (0, 0),
       #                     )

        # Apply fading fog
        if (
            cat.pelt.opacity <= 97
            and not cat.prevent_fading
            and get_clan_setting("fading")
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

            if cat.status.group == CatGroup.STARCLAN:
                temp = sprites.sprites["fadestarclan" + stage + cat_sprite].copy()
                temp.blit(new_sprite, (0, 0))
                new_sprite = temp
            elif cat.status.group == CatGroup.UNKNOWN_RESIDENCE:
                temp = sprites.sprites["fadeur" + stage + cat_sprite].copy()
                temp.blit(new_sprite, (0, 0))
                new_sprite = temp
            else:
                temp = sprites.sprites["fadedf" + stage + cat_sprite].copy()
                temp.blit(new_sprite, (0, 0))
                new_sprite = temp

        # ok! we have the sprite! now, do some layer things if the cat's already dead
       # if dead:
       #     temp_sprite = pygame.Surface(
       #         (sprites.size, sprites.size), pygame.HWSURFACE | pygame.SRCALPHA
       #     )
       #
       #     if cat.status.group == CatGroup.STARCLAN:
       #         # no underlay
       #
       #         # cat sprite
       #         temp_sprite.blit(new_sprite, (0, 0))
       #
       #         # overlay
       #         temp_sprite.blit(
       #             sprites.sprites["line_sc_overlay" + cat_sprite],
       #             (0, 0),
       #         )
       #     elif cat.status.group == CatGroup.UNKNOWN_RESIDENCE:
       #         # underlay
       #         temp_sprite.blit(
       #             sprites.sprites["line_ur_overlay" + cat_sprite],
       #             (0, 0),
       #         )
       #
       #         # cat sprite
       #         temp_sprite.blit(new_sprite, (0, 0))
       #
       #         # overlay
       #         temp_sprite.blit(
       #             sprites.sprites["line_ur_overlay" + cat_sprite],
       #             (0, 0),
       #         )
       #     elif cat.status.group == CatGroup.DARK_FOREST:
       #         # no underlay
       #
       #         # cat sprite
       #         temp_sprite.blit(new_sprite, (0, 0))
       #
       #         # no overlay
       #
       #     new_sprite = temp_sprite

        # reverse, if assigned so
        if cat.pelt.reverse:
            new_sprite = pygame.transform.flip(new_sprite, True, False)

    except (TypeError, KeyError):
        traceback.print_exc()
        logger.exception("Failed to load sprite")

        # Placeholder image
        new_sprite = image_cache.load_image(
            f"sprites/error_placeholder.png"
        ).convert_alpha()

    return new_sprite


# ---------------------------------------------------------------------------- #
#                                     OTHER                                    #
# ---------------------------------------------------------------------------- #

def union_of_entries(dict_of_lists):
    return sorted({ x for y in dict_of_lists.values() for x in y })

def chunks(L, n):
    return [L[x : x + n] for x in range(0, len(L), n)]


def clamp(value: float, minimum_value: float, maximum_value: float) -> float:
    """
    Takes a value and returns it constrained to a certain range
    :param value: The input value
    :param minimum_value: Lower bound
    :param maximum_value: Upper bound
    :return: Clamped float.
    """
    if value < minimum_value:
        return minimum_value
    elif value > maximum_value:
        return maximum_value
    return value


def is_iterable(y):
    try:
        0 in y
    except TypeError:
        return False


def get_text_box_theme(theme_name=None):
    """Updates the name of the theme based on dark or light mode"""
    if game_setting_get("dark mode"):
        return ObjectID("#dark", theme_name)
    else:
        return theme_name


def quit(savesettings=False, clearevents=False):
    """
    Quits the game, avoids a bunch of repeated lines
    """
    if savesettings:
        game_settings_save(None)
    if clearevents:
        game.cur_events_list.clear()
    game.rpc.close_rpc.set()
    game.rpc.update_rpc.set()
    pygame.display.quit()
    pygame.quit()
    if game.rpc.is_alive():
        game.rpc.join(1)
    sys_exit()


resource_directory = "resources/dicts/conditions/"
with open(
    os.path.normpath(f"{resource_directory}illnesses.json"), "r", encoding="utf-8"
) as read_file:
    ILLNESSES = ujson.loads(read_file.read())

with open(
    os.path.normpath(f"{resource_directory}injuries.json"), "r", encoding="utf-8"
) as read_file:
    INJURIES = ujson.loads(read_file.read())

with open(
    os.path.normpath(f"{resource_directory}permanent_conditions.json"),
    "r",
    encoding="utf-8",
) as read_file:
    PERMANENT = ujson.loads(read_file.read())

langs = {"snippet": None, "prey": None}

SNIPPETS = None
PREY_LISTS = None

with open(
    os.path.normpath("resources/dicts/backstories.json"), "r", encoding="utf-8"
) as read_file:
    BACKSTORIES = ujson.loads(read_file.read())
