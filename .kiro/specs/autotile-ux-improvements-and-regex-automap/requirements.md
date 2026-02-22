# Requirements Document

## Introduction

This document specifies the requirements for enhancing the tilemap editor's autotiling system with three key improvements: (1) a scrollable rules container with visual overflow indicators, (2) fully renameable autotile groups with improved UX feedback, and (3) a regex-based automap feature for pattern-based tile replacement. The automap system operates independently from the existing 3x3 neighbor autotiling, allowing users to define visual pattern rules similar to Tiled editor's automap functionality.

## Glossary

- **AutotileRuleDesigner**: The UI component for managing 3x3 neighbor-based autotile rules and groups
- **RegexAutomapDesigner**: The UI component for creating and managing pattern-based automap rules
- **AutomapEngine**: The processing component that executes pattern matching and tile transformation
- **PatternGrid**: A data structure representing a tile pattern with support for wildcards and match modes
- **PatternCell**: A single cell within a pattern grid with tile ID and match mode
- **PatternRule**: A complete automap rule consisting of input pattern, output pattern, and metadata
- **MatchMode**: An enumeration defining how pattern cells match tiles (EXACT, WILDCARD, ANY_FILLED, ANY_EMPTY)
- **Layer**: A tilemap layer containing tile data that can be transformed by automap rules
- **Tilemap**: The complete map structure containing multiple layers
- **AutotileGroup**: A collection of related autotile rules with a user-defined name
- **Scroll_Offset**: The index of the first visible rule in a scrollable list
- **Transformation**: The act of replacing tiles in a layer based on a matched pattern

## Requirements

### Requirement 1: Scrollable Rule List Display

**User Story:** As a user with many autotile rules, I want to scroll through the rule list with clear visual indicators, so that I can navigate and manage large rule sets efficiently.

#### Acceptance Criteria

1. WHEN the number of rules exceeds the maximum visible count, THE AutotileRuleDesigner SHALL display a scrollbar
2. WHEN rules are not scrolled to the top, THE AutotileRuleDesigner SHALL display an upward arrow indicator
3. WHEN rules are not scrolled to the bottom, THE AutotileRuleDesigner SHALL display a downward arrow indicator
4. WHEN the user scrolls with the mouse wheel, THE AutotileRuleDesigner SHALL update the scroll offset within valid bounds
5. WHEN the user drags the scrollbar, THE AutotileRuleDesigner SHALL update the visible rules based on scrollbar position
6. THE AutotileRuleDesigner SHALL render only the visible rules based on scroll offset and maximum visible count

### Requirement 2: Scroll Bounds Management

**User Story:** As a user interacting with the rule list, I want scroll operations to stay within valid bounds, so that the interface behaves predictably.

#### Acceptance Criteria

1. THE AutotileRuleDesigner SHALL maintain scroll offset greater than or equal to zero
2. THE AutotileRuleDesigner SHALL maintain scroll offset less than or equal to the maximum scroll value
3. WHEN rules are deleted while scrolled, THE AutotileRuleDesigner SHALL clamp scroll offset to the new valid range
4. WHEN the rule count changes, THE AutotileRuleDesigner SHALL recalculate the maximum scroll value

### Requirement 3: Autotile Group Renaming

**User Story:** As a user organizing autotile rules, I want to rename groups with inline editing, so that I can maintain clear organization without cumbersome dialogs.

#### Acceptance Criteria

1. WHEN the user presses F2 with a group selected, THE AutotileRuleDesigner SHALL enter rename mode for that group
2. WHILE in rename mode, THE AutotileRuleDesigner SHALL display an editable text field with the current group name
3. WHEN the user types printable characters in rename mode, THE AutotileRuleDesigner SHALL append them to the rename text
4. WHEN the user presses backspace in rename mode, THE AutotileRuleDesigner SHALL remove the last character from the rename text
5. WHEN the user presses Enter in rename mode, THE AutotileRuleDesigner SHALL save the new group name and exit rename mode
6. WHEN the user presses Escape in rename mode, THE AutotileRuleDesigner SHALL cancel the rename and exit rename mode
7. WHEN a group is renamed, THE AutotileRuleDesigner SHALL update the group_id for all rules in that group

### Requirement 4: New Group Creation with Immediate Rename

**User Story:** As a user creating new autotile groups, I want to immediately name the group without extra steps, so that I can work efficiently.

#### Acceptance Criteria

1. WHEN the user creates a new group, THE AutotileRuleDesigner SHALL generate a default name
2. WHEN a new group is created, THE AutotileRuleDesigner SHALL immediately enter rename mode for that group
3. WHEN a new group is created, THE AutotileRuleDesigner SHALL select the new group
4. THE AutotileRuleDesigner SHALL allow the user to type the new name without pressing F2

### Requirement 5: Pattern Grid Definition

**User Story:** As a user creating automap rules, I want to define tile patterns with wildcards and match modes, so that I can create flexible pattern-based transformations.

#### Acceptance Criteria

1. THE PatternGrid SHALL store cells with tile IDs and match modes
2. THE PatternGrid SHALL support EXACT match mode for specific tile IDs
3. THE PatternGrid SHALL support WILDCARD match mode for any tile
4. THE PatternGrid SHALL support ANY_FILLED match mode for any non-empty tile
5. THE PatternGrid SHALL support ANY_EMPTY match mode for empty tiles only
6. WHEN a pattern cell has WILDCARD match mode, THE PatternCell SHALL match any tile ID including None
7. WHEN a pattern cell has EXACT match mode, THE PatternCell SHALL match only the specified tile ID
8. WHEN a pattern cell has ANY_FILLED match mode, THE PatternCell SHALL match any non-None tile ID
9. WHEN a pattern cell has ANY_EMPTY match mode, THE PatternCell SHALL match only None tile ID

### Requirement 6: Pattern Rule Management

**User Story:** As a user creating automap transformations, I want to define rules with input and output patterns, so that I can specify how tiles should be transformed.

#### Acceptance Criteria

1. THE PatternRule SHALL contain an input pattern and an output pattern
2. THE PatternRule SHALL contain a name, enabled flag, and priority value
3. WHEN a pattern rule is created, THE PatternRule SHALL validate that input and output patterns have identical dimensions
4. THE PatternRule SHALL support serialization to dictionary format
5. THE PatternRule SHALL support deserialization from dictionary format
6. WHEN a pattern rule name is empty, THE RegexAutomapDesigner SHALL prevent saving the rule

### Requirement 7: Regex Automap Designer Interface

**User Story:** As a user defining automap rules, I want a dedicated UI for creating and managing pattern rules, so that I can work with automap independently from 3x3 autotiling.

#### Acceptance Criteria

1. THE RegexAutomapDesigner SHALL provide a show method to display the designer window
2. THE RegexAutomapDesigner SHALL provide a hide method to close the designer window
3. THE RegexAutomapDesigner SHALL display an input pattern grid for defining match patterns
4. THE RegexAutomapDesigner SHALL display an output pattern grid for defining replacement patterns
5. THE RegexAutomapDesigner SHALL display a list of saved pattern rules
6. WHEN the user saves a pattern rule, THE RegexAutomapDesigner SHALL add it to the pattern rules list
7. WHEN the user deletes a pattern rule, THE RegexAutomapDesigner SHALL remove it from the pattern rules list
8. THE RegexAutomapDesigner SHALL allow the user to select a pattern rule from the list
9. WHEN a pattern rule is selected, THE RegexAutomapDesigner SHALL load its patterns into the input and output grids

### Requirement 8: Pattern Matching

**User Story:** As a user applying automap rules, I want the system to accurately match patterns in the tilemap, so that transformations occur only where intended.

#### Acceptance Criteria

1. WHEN checking if a pattern matches at a position, THE AutomapEngine SHALL compare each pattern cell with the corresponding layer tile
2. WHEN a pattern extends beyond layer boundaries, THE AutomapEngine SHALL return false for the match
3. WHEN all pattern cells match their corresponding layer tiles, THE AutomapEngine SHALL return true for the match
4. THE AutomapEngine SHALL respect the match mode of each pattern cell during matching
5. WHEN scanning a layer for pattern matches, THE AutomapEngine SHALL check every valid position in the layer
6. WHEN scanning a layer for pattern matches, THE AutomapEngine SHALL return a list of all matching positions

### Requirement 9: Pattern Application

**User Story:** As a user applying automap rules, I want matched patterns to be replaced with output patterns, so that my tilemap is transformed according to the rules.

#### Acceptance Criteria

1. WHEN applying a pattern at a position, THE AutomapEngine SHALL set tiles according to the output pattern
2. WHEN applying a pattern, THE AutomapEngine SHALL only modify tiles for cells with EXACT match mode
3. WHEN applying a pattern, THE AutomapEngine SHALL preserve tiles for cells with WILDCARD match mode
4. WHEN applying a pattern at a position, THE AutomapEngine SHALL stay within layer boundaries
5. THE AutomapEngine SHALL apply pattern transformations atomically for each matched position

### Requirement 10: Rule Priority and Execution Order

**User Story:** As a user with multiple automap rules, I want rules to be applied in priority order, so that I can control which transformations take precedence.

#### Acceptance Criteria

1. WHEN applying multiple rules to a layer, THE AutomapEngine SHALL sort rules by priority in descending order
2. WHEN applying multiple rules to a layer, THE AutomapEngine SHALL process higher priority rules before lower priority rules
3. WHEN applying rules to a layer, THE AutomapEngine SHALL skip disabled rules
4. WHEN applying rules to a layer, THE AutomapEngine SHALL return the total count of transformations applied
5. THE AutomapEngine SHALL apply each enabled rule to the entire layer before proceeding to the next rule

### Requirement 11: Automap Execution

**User Story:** As a user applying automap to a layer, I want all pattern rules to be executed efficiently, so that I can transform large tilemaps quickly.

#### Acceptance Criteria

1. WHEN the user applies automap to a layer, THE RegexAutomapDesigner SHALL invoke the AutomapEngine with all pattern rules
2. WHEN applying automap, THE AutomapEngine SHALL scan the layer for each rule's input pattern
3. WHEN applying automap, THE AutomapEngine SHALL apply the output pattern at each matched position
4. WHEN applying automap, THE AutomapEngine SHALL count the total number of tile transformations
5. WHEN automap execution completes, THE RegexAutomapDesigner SHALL display the transformation count to the user

### Requirement 12: Pattern Serialization

**User Story:** As a user saving my project, I want pattern rules to be persisted, so that I can reload them in future sessions.

#### Acceptance Criteria

1. THE PatternGrid SHALL serialize to a dictionary containing width, height, and cell data
2. THE PatternGrid SHALL deserialize from a dictionary to restore the pattern
3. THE PatternRule SHALL serialize to a dictionary containing name, patterns, enabled flag, and priority
4. THE PatternRule SHALL deserialize from a dictionary to restore the rule
5. WHEN serialization fails, THE RegexAutomapDesigner SHALL display an error message and keep rules in memory
6. WHEN deserialization fails, THE RegexAutomapDesigner SHALL log a warning and skip the invalid rule

### Requirement 13: Error Handling for Pattern Boundaries

**User Story:** As a user applying automap rules, I want the system to handle edge cases gracefully, so that invalid operations don't cause crashes or corruption.

#### Acceptance Criteria

1. WHEN a pattern would extend beyond layer boundaries, THE AutomapEngine SHALL skip that position
2. WHEN a pattern cell references an invalid tile ID, THE AutomapEngine SHALL log a warning and skip that cell
3. WHEN a pattern rule has no cells defined, THE RegexAutomapDesigner SHALL prevent saving the rule
4. WHEN a pattern rule has mismatched input and output dimensions, THE RegexAutomapDesigner SHALL reject the rule

### Requirement 14: Duplicate Group Name Handling

**User Story:** As a user renaming groups, I want the system to prevent name conflicts, so that each group has a unique identifier.

#### Acceptance Criteria

1. WHEN a user renames a group to an existing name, THE AutotileRuleDesigner SHALL append a numeric suffix to make the name unique
2. WHEN a duplicate name is detected, THE AutotileRuleDesigner SHALL automatically resolve the conflict without user intervention
3. THE AutotileRuleDesigner SHALL allow the user to rename the group again after automatic conflict resolution

### Requirement 15: Circular Dependency Prevention

**User Story:** As a user creating complex automap rules, I want the system to prevent infinite loops, so that automap execution completes in reasonable time.

#### Acceptance Criteria

1. WHEN applying rules to a layer, THE AutomapEngine SHALL limit the total number of transformations per execution
2. WHEN the transformation limit is reached, THE AutomapEngine SHALL stop execution and notify the user
3. THE AutomapEngine SHALL use a maximum transformation limit of at least 10,000 per execution

### Requirement 16: Automap and Autotile Independence

**User Story:** As a user of both autotile and automap features, I want them to work independently, so that I can use both systems without interference.

#### Acceptance Criteria

1. THE RegexAutomapDesigner SHALL operate independently from the AutotileRuleDesigner
2. WHEN automap rules are applied to a layer, THE AutomapEngine SHALL not modify autotile rules or groups
3. WHEN autotile rules are applied to a layer, THE autotile system SHALL not modify automap pattern rules
4. THE system SHALL allow both autotile and automap to be applied to the same layer sequentially

### Requirement 17: Visual Feedback for Scrolling

**User Story:** As a user scrolling through rules, I want clear visual feedback, so that I know when more content is available.

#### Acceptance Criteria

1. WHEN rules extend above the visible area, THE AutotileRuleDesigner SHALL display a fade effect or arrow at the top
2. WHEN rules extend below the visible area, THE AutotileRuleDesigner SHALL display a fade effect or arrow at the bottom
3. WHEN all rules are visible, THE AutotileRuleDesigner SHALL hide scroll indicators
4. THE AutotileRuleDesigner SHALL update scroll indicators immediately when scroll offset changes

### Requirement 18: Rename Mode Visual Feedback

**User Story:** As a user renaming a group, I want clear visual feedback that I'm in rename mode, so that I understand the current interaction state.

#### Acceptance Criteria

1. WHILE in rename mode, THE AutotileRuleDesigner SHALL display the group name in an editable text field
2. WHILE in rename mode, THE AutotileRuleDesigner SHALL highlight the text field to indicate edit state
3. WHILE in rename mode, THE AutotileRuleDesigner SHALL display a text cursor in the rename field
4. WHEN rename mode is exited, THE AutotileRuleDesigner SHALL return to normal display mode

### Requirement 19: Pattern Grid Sparse Storage

**User Story:** As a user creating large patterns with many wildcards, I want efficient memory usage, so that the system performs well with complex rules.

#### Acceptance Criteria

1. THE PatternGrid SHALL use a sparse dictionary to store only non-wildcard cells
2. WHEN a pattern cell is set to WILDCARD, THE PatternGrid SHALL remove it from storage if it exists
3. WHEN a pattern cell is queried and not in storage, THE PatternGrid SHALL return a default wildcard cell
4. THE PatternGrid SHALL minimize memory usage for patterns with many wildcard cells

### Requirement 20: Input Validation for Pattern Rules

**User Story:** As a user loading projects with pattern rules, I want the system to validate rule data, so that malicious or corrupted data doesn't cause crashes.

#### Acceptance Criteria

1. WHEN deserializing a pattern rule, THE PatternRule SHALL validate that dimensions are positive integers
2. WHEN deserializing a pattern rule, THE PatternRule SHALL validate that tile IDs are within valid range or None
3. WHEN deserializing a pattern rule, THE PatternRule SHALL validate that match modes are valid MatchMode enum values
4. WHEN deserializing a pattern rule, THE PatternRule SHALL validate that priority is a non-negative integer
5. WHEN validation fails, THE PatternRule SHALL raise an exception with a descriptive error message
