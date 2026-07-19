"""
Automap models for pattern-based tile transformations.

This module provides data structures and algorithms for regex-like pattern matching
and transformation of tiles in a tilemap layer. It operates independently from the
existing 3x3 neighbor-based autotiling system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ttypes.tilemap import TypeTile

if TYPE_CHECKING:
    from src.layers import Layer


class MatchMode(Enum):
    """Defines how a pattern cell matches against layer tiles."""

    EXACT = "exact"
    WILDCARD = "wildcard"
    ANY_FILLED = "any_filled"
    ANY_EMPTY = "any_empty"


@dataclass
class PatternCell:
    """A single cell within a pattern grid with tile ID and match mode.

    Attributes:
        tile_id: The tile variant ID to match (None for wildcard/empty)
        tileset_index: The tileset index (ttype) for the tile
        match_mode: How this cell matches against layer tiles
    """

    tile_id: int | None
    tileset_index: int | None
    match_mode: MatchMode

    def matches(
        self, actual_tile_id: int | None, actual_tileset_index: int | None = None
    ) -> bool:
        """Check if actual tile matches this pattern cell.

        Args:
            actual_tile_id: The tile variant ID from the layer (None for empty)
            actual_tileset_index: The tileset index (ttype) from the layer (None for empty)

        Returns:
            True if the tile matches according to this cell's match mode
        """
        if self.match_mode == MatchMode.WILDCARD:
            return True
        if self.match_mode == MatchMode.ANY_FILLED:
            return actual_tile_id is not None
        if self.match_mode == MatchMode.ANY_EMPTY:
            return actual_tile_id is None
        return (
            self.tile_id == actual_tile_id
            and self.tileset_index == actual_tileset_index
        )


class PatternGrid:
    """A grid of pattern cells with sparse storage for efficient memory usage.

    Uses a sparse dictionary to store only non-wildcard cells, minimizing
    memory usage for patterns with many wildcard cells.

    Attributes:
        width: Grid width in cells
        height: Grid height in cells
        cells: Sparse dictionary mapping (x, y) to PatternCell
    """

    def __init__(self, width: int, height: int):
        """Initialize a pattern grid with given dimensions.

        Args:
            width: Grid width (must be positive)
            height: Grid height (must be positive)
        """
        self.width = width
        self.height = height
        self.cells: dict[tuple[int, int], PatternCell] = {}

    def set_cell(self, x: int, y: int, cell: PatternCell) -> None:
        """Set pattern cell at position.

        If the cell is WILDCARD, it will be removed from storage to save memory.

        Args:
            x: X coordinate (0-indexed)
            y: Y coordinate (0-indexed)
            cell: The pattern cell to set
        """
        if cell.match_mode == MatchMode.WILDCARD:
            if (x, y) in self.cells:
                del self.cells[(x, y)]
        else:
            self.cells[(x, y)] = cell

    def get_cell(self, x: int, y: int) -> PatternCell:
        """Get pattern cell at position.

        Returns a default wildcard cell if the position is not in storage.

        Args:
            x: X coordinate (0-indexed)
            y: Y coordinate (0-indexed)

        Returns:
            The pattern cell at this position, or a default wildcard cell
        """
        return self.cells.get((x, y), PatternCell(None, None, MatchMode.WILDCARD))

    def matches(self, tiles: dict[tuple[int, int], int | None]) -> bool:
        """Check if tile data matches this pattern.

        Args:
            tiles: Dictionary mapping (x, y) to tile variant ID

        Returns:
            True if all pattern cells match their corresponding tiles
        """
        for y in range(self.height):
            for x in range(self.width):
                cell = self.get_cell(x, y)
                actual_tile_id = tiles.get((x, y))
                if not cell.matches(actual_tile_id):
                    return False
        return True

    def to_dict(self) -> dict:
        """Serialize pattern to dictionary.

        Returns:
            Dictionary containing width, height, and cell data
        """
        cells_data = {}
        for (x, y), cell in self.cells.items():
            cells_data[f"{x},{y}"] = {
                "tile_id": cell.tile_id,
                "tileset_index": cell.tileset_index,
                "match_mode": cell.match_mode.value,
            }

        return {"width": self.width, "height": self.height, "cells": cells_data}

    @staticmethod
    def from_dict(data: dict) -> "PatternGrid":
        """Deserialize pattern from dictionary.

        Args:
            data: Dictionary containing pattern data

        Returns:
            Reconstructed PatternGrid instance
        """
        grid = PatternGrid(data["width"], data["height"])

        for pos_str, cell_data in data.get("cells", {}).items():
            x, y = map(int, pos_str.split(","))
            cell = PatternCell(
                tile_id=cell_data["tile_id"],
                tileset_index=cell_data["tileset_index"],
                match_mode=MatchMode(cell_data["match_mode"]),
            )
            grid.set_cell(x, y, cell)

        return grid


@dataclass
class PatternRule:
    """A complete automap rule with input pattern, output pattern, and metadata.

    Attributes:
        name: User-defined name for the rule
        input_pattern: Pattern to match in the layer
        output_pattern: Pattern to apply when input matches
        enabled: Whether this rule is active
        priority: Higher priority rules are applied first
    """

    name: str
    input_pattern: PatternGrid
    output_pattern: PatternGrid
    enabled: bool = True
    priority: int = 0

    def __post_init__(self):
        """Validate that input and output patterns have matching dimensions."""
        if self.input_pattern.width != self.output_pattern.width:
            raise ValueError(
                f"Pattern dimension mismatch: input width {self.input_pattern.width} "
                f"!= output width {self.output_pattern.width}"
            )
        if self.input_pattern.height != self.output_pattern.height:
            raise ValueError(
                f"Pattern dimension mismatch: input height {self.input_pattern.height} "
                f"!= output height {self.output_pattern.height}"
            )
        if not self.name:
            raise ValueError("Pattern rule name cannot be empty")

    def to_dict(self) -> dict:
        """Serialize pattern rule to dictionary.

        Returns:
            Dictionary containing all rule data
        """
        return {
            "name": self.name,
            "input_pattern": self.input_pattern.to_dict(),
            "output_pattern": self.output_pattern.to_dict(),
            "enabled": self.enabled,
            "priority": self.priority,
        }

    @staticmethod
    def from_dict(data: dict) -> "PatternRule":
        """Deserialize pattern rule from dictionary with validation.

        Args:
            data: Dictionary containing rule data

        Returns:
            Reconstructed PatternRule instance

        Raises:
            ValueError: If validation fails
        """

        input_data = data["input_pattern"]
        output_data = data["output_pattern"]

        if input_data["width"] <= 0 or input_data["height"] <= 0:
            raise ValueError("Pattern dimensions must be positive integers")
        if output_data["width"] <= 0 or output_data["height"] <= 0:
            raise ValueError("Pattern dimensions must be positive integers")

        priority = data.get("priority", 0)
        if priority < 0:
            raise ValueError("Priority must be a non-negative integer")

        input_pattern = PatternGrid.from_dict(input_data)
        output_pattern = PatternGrid.from_dict(output_data)

        return PatternRule(
            name=data["name"],
            input_pattern=input_pattern,
            output_pattern=output_pattern,
            enabled=data.get("enabled", True),
            priority=priority,
        )


class AutomapEngine:
    """Engine for executing pattern matching and tile transformation.

    Processes pattern rules to transform tiles in a layer based on visual
    pattern matching, similar to Tiled editor's automap functionality.

    Attributes:
        tilemap: Reference to the tilemap (currently unused, for future expansion)
        max_transformations: Maximum transformations per execution to prevent infinite loops
    """

    def __init__(self, tilemap=None):
        """Initialize the automap engine.

        Args:
            tilemap: Optional reference to the tilemap
        """
        self.tilemap = tilemap
        self.max_transformations = 10000

    def match_pattern(
        self, layer: "Layer", x: int, y: int, pattern: PatternGrid
    ) -> bool:
        """Check if pattern matches at given position in layer.

        Args:
            layer: The layer to check
            x: Starting X coordinate
            y: Starting Y coordinate
            pattern: The pattern to match

        Returns:
            True if pattern matches at this position, False otherwise
        """

        for py in range(pattern.height):
            for px in range(pattern.width):
                layer_x = x + px
                layer_y = y + py

                pattern_cell = pattern.get_cell(px, py)
                layer_tile = layer.get_tile((layer_x, layer_y))

                actual_tile_id = layer_tile["variant"] if layer_tile else None
                actual_tileset_index = layer_tile["ttype"] if layer_tile else None

                if not pattern_cell.matches(actual_tile_id, actual_tileset_index):
                    return False

        return True

    def scan_layer_for_pattern(
        self, layer: "Layer", pattern: PatternGrid
    ) -> list[tuple[int, int]]:
        """Find all positions where pattern matches in the layer.

        Scans the entire layer and returns all positions where the pattern matches.
        Uses early termination on first cell mismatch for optimization.

        Args:
            layer: The layer to scan
            pattern: The pattern to find

        Returns:
            List of (x, y) positions where pattern matches
        """
        import logging

        matches = []

        if not layer.tiles:
            logging.debug("Layer has no tiles, skipping scan")
            return matches

        tile_positions = list(layer.tiles.keys())
        min_x = min(pos[0] for pos in tile_positions)
        max_x = max(pos[0] for pos in tile_positions)
        min_y = min(pos[1] for pos in tile_positions)
        max_y = max(pos[1] for pos in tile_positions)

        logging.debug(
            f"Scanning layer bounds: x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]"
        )

        for y in range(min_y, max_y + 2):
            for x in range(min_x, max_x + 2):
                if self.match_pattern(layer, x, y, pattern):
                    matches.append((x, y))
                    logging.debug(f"Pattern matched at position ({x}, {y})")

        logging.debug(f"Found {len(matches)} pattern matches")
        return matches

    def apply_pattern_at_position(
        self, layer: "Layer", x: int, y: int, pattern: PatternGrid
    ) -> None:
        """Apply output pattern at specific position.

        Only modifies tiles for cells with EXACT match mode. WILDCARD cells
        preserve existing tiles. Includes boundary checking and error handling.

        Args:
            layer: The layer to modify
            x: Starting X coordinate
            y: Starting Y coordinate
            pattern: The output pattern to apply
        """
        import logging

        for py in range(pattern.height):
            for px in range(pattern.width):
                layer_x = x + px
                layer_y = y + py

                pattern_cell = pattern.get_cell(px, py)

                if pattern_cell.match_mode == MatchMode.EXACT:
                    if pattern_cell.tile_id is not None and pattern_cell.tile_id < 0:
                        logging.warning(
                            f"Invalid tile ID {pattern_cell.tile_id} at pattern position ({px}, {py}), skipping cell"
                        )
                        continue

                    if (
                        pattern_cell.tileset_index is not None
                        and pattern_cell.tileset_index < 0
                    ):
                        logging.warning(
                            f"Invalid tileset index {pattern_cell.tileset_index} at pattern position ({px}, {py}), skipping cell"
                        )
                        continue

                    if (
                        pattern_cell.tile_id is not None
                        and pattern_cell.tileset_index is not None
                    ):
                        tile_data: TypeTile = {
                            "pos": (layer_x, layer_y),
                            "ttype": pattern_cell.tileset_index,
                            "variant": pattern_cell.tile_id,
                        }
                        layer.set_tile((layer_x, layer_y), tile_data)
                    else:
                        layer.remove_tile((layer_x, layer_y))

    def apply_rules(self, layer: "Layer", rules: list[PatternRule]) -> int:
        """Apply all enabled pattern rules to layer in priority order.

        Rules are sorted by priority (descending) and applied sequentially.
        Disabled rules are skipped. Includes transformation limit to prevent
        infinite loops from circular dependencies.

        Args:
            layer: The layer to transform
            rules: List of pattern rules to apply

        Returns:
            Total number of tile transformations applied
        """
        import logging

        if not rules:
            return 0

        sorted_rules = sorted(
            [r for r in rules if r.enabled], key=lambda r: r.priority, reverse=True
        )

        transformation_count = 0

        for rule in sorted_rules:
            if transformation_count >= self.max_transformations:
                logging.warning(
                    f"Transformation limit ({self.max_transformations}) reached. "
                    f"Stopping automap execution. This may indicate circular dependencies."
                )
                break

            matches = self.scan_layer_for_pattern(layer, rule.input_pattern)

            for x, y in matches:
                if transformation_count >= self.max_transformations:
                    break

                self.apply_pattern_at_position(layer, x, y, rule.output_pattern)
                transformation_count += 1

        return transformation_count
