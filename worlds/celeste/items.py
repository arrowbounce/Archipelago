from abc import ABC, abstractmethod
from typing import Dict, List

from BaseClasses import ItemClassification
from random import randint, choices

from .data import VICTORY_UUID, TRAP_UUID, BaseData, CelesteItem, CelesteItemType, CelesteSide
from .options import CelesteGameOptions, ProgressionSystem


class ItemGeneratorFactory:
    """Factory used for retrieving an `ItemGenerator` for dependency injection in building a `ProgressionSystem`."""

    @staticmethod
    def get_item_generator(player: int, options: CelesteGameOptions) -> "ItemGenerator":
        """Retrieves a `RegionAccessor` sub-class based on the provided player options.

        Args:
            player (`int`): The number representing a player.
            options (`CelesteGameOptions`): The world options provided by the given player.

        Returns:
            `RegionAccessor`: Object for generating region access rules.
        """
        if options.progression_system == ProgressionSystem.option_default_progression:
            return OriginalItemGenerator(player, options)


class ItemGenerator(ABC):
    """Abstract class for generating items to add to the MultiWorld."""

    _player: int
    _options: CelesteGameOptions

    def __init__(self, player: int, options: CelesteGameOptions):
        self._player = player
        self._options = options

    @abstractmethod
    def generate_items(self) -> List[CelesteItem]:
        """Generates a list of items that should be included in the MultiWorld for this player.

        Returns:
            `List[CelesteItem]`: Items that should be included in the MultiWorld.
        """

    @abstractmethod
    def generate_item_dict(self) -> Dict[int, CelesteItem]:
        """Generates a mapping from UUID for items that should be included in the MultiWorld for this player.

        Returns:
            `Dict[int, CelesteItem]`: Mapping from UUID for items that should be included in the MultiWorld.
        """


class OriginalItemGenerator(ItemGenerator):
    """Class for generating items to add to the MultiWorld based on original Celeste requirements."""

    _items: List[CelesteItem]
    _item_dict: Dict[int, CelesteItem]
    _traps: Dict[str, int]

    def __init__(self, player: int, options: CelesteGameOptions):
        super().__init__(player, options)
        self._items = []
        self._item_dict = {}
        self._traps = self.generate_traps()

    def _fix_broken_options(self):
        """Fixes any goal level requirements that are above their completable single-player numbers.

        e.g., if the goal level is Summit A-Side, the maximum crystal heart requirement should be 18 rather than 24.
        """
        item_counts = {}
        goal_level = self._options.get_goal_level()

        for item_type, level, _, _ in BaseData.items():
            # Skip all items that aren't accessible before the goal level
            if level >= goal_level:
                continue

            if item_type not in item_counts:
                item_counts[item_type] = 0
            item_counts[item_type] += 1

        self._options.berries_required.value = min(
            self._options.berries_required.value, item_counts[CelesteItemType.STRAWBERRY]
        )
        self._options.cassettes_required.value = min(
            self._options.cassettes_required.value, item_counts[CelesteItemType.CASSETTE]
        )
        self._options.hearts_required.value = min(
            self._options.hearts_required.value, item_counts[CelesteItemType.GEMHEART]
        )
        self._options.levels_required.value = min(
            self._options.levels_required.value, item_counts[CelesteItemType.COMPLETION]
        )

    def generate_items(self) -> List[CelesteItem]:
        if len(self._items) > 0:
            return self._items

        self._fix_broken_options()

        strawberry_count = 0
        gemheart_count = 0
        goal_level = self._options.get_goal_level()
        trap_chance = self._options.trap_chance
        for item_type, level, name, uuid in BaseData.items():
            # Skip all items that would ordinarily come after the goal level
            if level > goal_level:
                continue

            # Initially assume items are progression.
            classification = ItemClassification.progression

            # All collectable items above the required number are filler, rather than progression.
            if item_type == CelesteItemType.STRAWBERRY:
                if strawberry_count > self._options.berries_required.value:
                    uuid, name, item_type, classification = self.set_filler_item(uuid, name, item_type, trap_chance)
                strawberry_count += 1
            elif item_type == CelesteItemType.GEMHEART:
                if gemheart_count > self._options.hearts_required.value and level.side == CelesteSide.C_SIDE:
                    uuid, name, item_type, classification = self.set_filler_item(uuid, name, item_type, trap_chance)
                gemheart_count += 1
            
            # All items normally found in the goal level are filler, rather than progression.
            if level == goal_level and item_type != CelesteItemType.COMPLETION:
                uuid, name, item_type, classification = self.set_filler_item(uuid, name, item_type, trap_chance)

            # Adjust name for victory condition
            if level == goal_level and item_type == CelesteItemType.COMPLETION:
                name = "Victory (Celeste)"
                uuid = VICTORY_UUID

            # Generate given item.
            item = CelesteItem(
                name=name,
                classification=classification,
                code=uuid,
                player=self._player,
                item_type=item_type,
                level=level,
            )
            self._items.append(item)

        return self._items

    def generate_item_dict(self) -> Dict[int, CelesteItem]:
        if len(self._item_dict) > 0:
            return self._item_dict

        items = self.generate_items()

        for item in items:
            if item.code not in self._item_dict:
                self._item_dict[item.code] = item

        return self._item_dict

    def generate_traps(self) -> Dict[str, int]:
        trap_data = {}
        trap_data["Theo Crystal Trap"] = self._options.theo_crystal_trap
        trap_data["Badeline Chasers Trap"] = self._options.badeline_chasers_trap
        trap_data["Seeker Trap"] = self._options.seeker_trap
        
        return trap_data
    
    def set_filler_item(self, uuid: int, name: str, item_type: CelesteItemType, trap_chance: int) -> tuple[int, str, CelesteItemType, ItemClassification]:
        if trap_chance > 0 and randint(1, 100) <= trap_chance:
            # Filler item has become a trap item
            trap_uuid, trap_name = self.choose_trap()
            return trap_uuid, trap_name, CelesteItemType.TRAP , ItemClassification.trap
        return uuid, name, item_type, ItemClassification.filler
    
    def choose_trap(self):
        trap = choices(list(self._traps.keys()), weights=list(self._traps.values()), k=1)[0]
        
        match trap:
            case "Theo Crystal Trap":
                return (TRAP_UUID, trap)
            case "Badeline Chasers Trap":
                return (TRAP_UUID + 1, trap)
            case "Seeker Trap":
                return (TRAP_UUID + 2, trap)
            case _:
                raise Exception(f"Trap {trap} has not been implemented")