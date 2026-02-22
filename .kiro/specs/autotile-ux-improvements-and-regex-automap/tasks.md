# Implementation Plan: Autotile UX Improvements and Regex Automap

## Overview

This implementation plan covers three main enhancements to the tilemap editor's autotiling system: (1) scrollable rule lists with visual indicators in the AutotileRuleDesigner, (2) inline group renaming with improved UX, and (3) a new regex-based automap system for pattern-based tile transformations. The implementation follows a bottom-up approach, starting with core data models and building up to UI components.

## Tasks

- [x] 1. Implement core data models for pattern-based automap
  - [x] 1.1 Create MatchMode enum and PatternCell dataclass
    - Implement MatchMode enum with EXACT, WILDCARD, ANY_FILLED, ANY_EMPTY values
    - Implement PatternCell dataclass with tile_id, tileset_index, match_mode fields
    - Implement PatternCell.matches() method with logic for each match mode
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_
  
  - [ ]* 1.2 Write property tests for PatternCell matching
    - **Property 13: Wildcard Match Behavior**
    - **Property 14: Exact Match Behavior**
    - **Property 15: Filled Match Behavior**
    - **Property 16: Empty Match Behavior**
    - **Validates: Requirements 5.6, 5.7, 5.8, 5.9**
  
  - [x] 1.3 Create PatternGrid class with sparse storage
    - Implement PatternGrid with width, height, and sparse cells dictionary
    - Implement set_cell() and get_cell() methods
    - Implement default wildcard cell return for unset cells
    - Implement matches() method to compare against tile data
    - _Requirements: 5.1, 19.1, 19.2, 19.3_
  
  - [ ]* 1.4 Write property tests for PatternGrid
    - **Property 39: Sparse Grid Default Wildcard**
    - **Validates: Requirements 19.3**
  
  - [x] 1.5 Implement PatternGrid serialization
    - Implement to_dict() method for serialization
    - Implement from_dict() static method for deserialization
    - _Requirements: 12.1, 12.2_
  
  - [ ]* 1.6 Write property tests for PatternGrid serialization
    - **Property 20: Pattern Grid Serialization Round-Trip**
    - **Validates: Requirements 12.1**

- [x] 2. Implement PatternRule data model
  - [x] 2.1 Create PatternRule dataclass
    - Implement PatternRule with name, input_pattern, output_pattern, enabled, priority fields
    - Implement dimension validation (input and output must match)
    - Implement empty name validation
    - _Requirements: 6.1, 6.2, 6.3, 6.6_
  
  - [x] 2.2 Implement PatternRule serialization
    - Implement to_dict() method
    - Implement from_dict() static method with validation
    - Add validation for dimensions, tile IDs, match modes, priority
    - _Requirements: 6.4, 6.5, 12.3, 12.4, 20.1, 20.2, 20.3, 20.4, 20.5_
  
  - [ ]* 2.3 Write property tests for PatternRule
    - **Property 17: Pattern Dimension Consistency**
    - **Property 18: Pattern Rule Serialization Round-Trip**
    - **Property 19: Empty Rule Name Rejection**
    - **Property 40: Dimension Validation**
    - **Property 41: Tile ID Validation**
    - **Property 42: Match Mode Validation**
    - **Property 43: Priority Validation**
    - **Validates: Requirements 6.3, 6.4, 6.6, 12.3, 20.1, 20.2, 20.3, 20.4**

- [x] 3. Implement AutomapEngine for pattern matching and transformation
  - [x] 3.1 Create AutomapEngine class with match_pattern method
    - Implement AutomapEngine.__init__() with tilemap reference
    - Implement match_pattern_at_position() with boundary checking
    - Implement cell-by-cell matching with MatchMode support
    - Handle patterns extending beyond layer boundaries
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [ ]* 3.2 Write property tests for pattern matching
    - **Property 24: Pattern Boundary Rejection**
    - **Property 25: Pattern Match Consistency**
    - **Validates: Requirements 8.2, 8.3**
  
  - [x] 3.3 Implement scan_layer_for_pattern method
    - Scan entire layer for pattern matches
    - Return list of all matching positions
    - Optimize with early termination on first cell mismatch
    - _Requirements: 8.5, 8.6_
  
  - [ ]* 3.4 Write property tests for layer scanning
    - **Property 26: Pattern Scan Completeness**
    - **Validates: Requirements 8.5**
  
  - [x] 3.5 Implement apply_pattern_at_position method
    - Apply output pattern at specified position
    - Only modify tiles for EXACT match mode cells
    - Preserve tiles for WILDCARD cells
    - Ensure all modifications stay within layer boundaries
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 3.6 Write property tests for pattern application
    - **Property 27: Pattern Application Correctness**
    - **Property 28: Wildcard Preservation**
    - **Property 29: Pattern Application Bounds Safety**
    - **Validates: Requirements 9.1, 9.2, 9.4**
  
  - [x] 3.7 Implement apply_rules method with priority ordering
    - Sort rules by priority (descending order)
    - Skip disabled rules
    - Apply each rule to entire layer
    - Count and return total transformations
    - Implement transformation limit (10,000) to prevent infinite loops
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 15.1, 15.2, 15.3_
  
  - [ ]* 3.8 Write property tests for rule application
    - **Property 30: Rule Priority Ordering**
    - **Property 31: Disabled Rule Skipping**
    - **Property 32: Transformation Count Accuracy**
    - **Property 35: Transformation Limit Enforcement**
    - **Validates: Requirements 10.1, 10.3, 10.4, 15.1**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Enhance AutotileRuleDesigner with scrollable rule list
  - [x] 5.1 Add scroll state management to AutotileRuleDesigner
    - Add scroll_offset, max_visible_rules, scroll_bar_rect, is_scrolling attributes
    - Initialize scroll state in __init__()
    - _Requirements: 1.1_
  
  - [x] 5.2 Implement _draw_scrollable_rule_list method
    - Calculate visible rule range based on scroll_offset
    - Render only visible rules within rule_list_area
    - Draw scrollbar when total rules > max_visible_rules
    - Calculate and draw scrollbar position based on scroll_offset
    - _Requirements: 1.1, 1.6_
  
  - [x] 5.3 Implement scroll visual indicators
    - Draw upward arrow when scroll_offset > 0
    - Draw downward arrow when scroll_offset < max_scroll
    - Hide indicators when all rules are visible
    - Update indicators immediately on scroll changes
    - _Requirements: 1.2, 1.3, 17.1, 17.2, 17.3, 17.4_
  
  - [x] 5.4 Implement _handle_scroll_event method
    - Handle MOUSEWHEEL events to update scroll_offset
    - Handle scrollbar dragging (MOUSEBUTTONDOWN, MOUSEMOTION, MOUSEBUTTONUP)
    - Clamp scroll_offset to valid range [0, max_scroll]
    - Recalculate max_scroll when rule count changes
    - _Requirements: 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_
  
  - [ ]* 5.5 Write property tests for scroll functionality
    - **Property 1: Scroll Bounds Integrity**
    - **Property 2: Scrollbar Visibility**
    - **Property 3: Scroll Indicator Display**
    - **Property 4: Scrollbar Position Mapping**
    - **Property 5: Visible Rules Calculation**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 17.3**

- [x] 6. Implement group renaming functionality in AutotileRuleDesigner
  - [x] 6.1 Add rename state management
    - Add renaming_group_idx and rename_text attributes
    - Initialize rename state in __init__()
    - _Requirements: 3.1_
  
  - [x] 6.2 Implement _handle_group_rename method
    - Handle F2 key to enter rename mode
    - Handle text input (printable characters, backspace)
    - Handle Enter key to confirm rename
    - Handle Escape key to cancel rename
    - Update group_id for all rules in renamed group
    - Implement duplicate name resolution with numeric suffix
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 14.1, 14.2, 14.3_
  
  - [x] 6.3 Implement rename mode visual feedback
    - Display editable text field in rename mode
    - Highlight text field to indicate edit state
    - Display text cursor in rename field
    - Return to normal display when rename mode exits
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
  
  - [x] 6.4 Implement _create_new_group_with_focus method
    - Create new group with default name
    - Select the new group
    - Immediately enter rename mode
    - Allow typing without pressing F2
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 6.5 Write property tests for group management
    - **Property 6: Rename Mode Activation**
    - **Property 7: Rename Text Input**
    - **Property 8: Rename Backspace Handling**
    - **Property 9: Rename Confirmation**
    - **Property 10: Rename Cancellation**
    - **Property 11: Group Name Synchronization**
    - **Property 12: New Group Creation**
    - **Property 34: Duplicate Group Name Resolution**
    - **Property 38: Rename Mode Exit**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 14.1, 18.4**

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement RegexAutomapDesigner UI component
  - [x] 8.1 Create RegexAutomapDesigner class with basic structure
    - Implement __init__() with editor reference and position
    - Add visible, pattern_rules, selected_rule_idx attributes
    - Add input_pattern_grid and output_pattern_grid attributes
    - Implement show() and hide() methods
    - _Requirements: 7.1, 7.2_
  
  - [x] 8.2 Implement pattern grid UI for input and output patterns
    - Draw input pattern grid with tile selection
    - Draw output pattern grid with tile selection
    - Allow users to set pattern cells with different match modes
    - Display visual indicators for match modes (wildcard, filled, empty)
    - _Requirements: 7.3, 7.4_
  
  - [x] 8.3 Implement pattern rule list display
    - Display list of saved pattern rules
    - Allow rule selection from list
    - Load selected rule's patterns into grids
    - _Requirements: 7.5, 7.8, 7.9_
  
  - [x] 8.4 Implement pattern rule save and delete operations
    - Implement _save_pattern_rule() method
    - Validate rule before saving (non-empty name, matching dimensions)
    - Implement _delete_pattern_rule() method
    - Update pattern_rules list on save/delete
    - _Requirements: 6.6, 7.6, 7.7, 13.3, 13.4_
  
  - [ ]* 8.5 Write property tests for rule management
    - **Property 21: Rule List Addition**
    - **Property 22: Rule List Removal**
    - **Property 23: Rule Selection Loading**
    - **Property 33: Empty Pattern Rejection**
    - **Validates: Requirements 7.6, 7.7, 7.9, 13.3**
  
  - [x] 8.6 Implement apply_automap_to_layer method
    - Get AutomapEngine instance
    - Call engine.apply_rules() with pattern_rules
    - Display transformation count to user
    - Handle errors gracefully
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 8.7 Implement event handling for RegexAutomapDesigner
    - Handle mouse clicks on pattern grids
    - Handle mouse clicks on rule list
    - Handle keyboard shortcuts (save, delete, apply)
    - Handle window close events
    - _Requirements: 7.1, 7.2_

- [x] 9. Implement error handling and validation
  - [x] 9.1 Add pattern boundary error handling
    - Check pattern bounds before application
    - Skip positions that would extend beyond layer
    - Log warnings for invalid tile IDs
    - _Requirements: 13.1, 13.2_
  
  - [x] 9.2 Add serialization error handling
    - Wrap serialization in try-except blocks
    - Display error dialog on save failure
    - Keep rules in memory on save failure
    - Log warnings and skip invalid rules on load failure
    - _Requirements: 12.5, 12.6_
  
  - [x] 9.3 Add circular dependency detection
    - Implement transformation limit in apply_rules()
    - Notify user when limit is reached
    - Suggest potential circular dependency
    - _Requirements: 15.1, 15.2, 15.3_

- [x] 10. Integrate automap with project persistence
  - [x] 10.1 Add pattern rules to project save format
    - Serialize pattern_rules to project JSON
    - Include automap data in project file structure
    - _Requirements: 12.1, 12.3_
  
  - [x] 10.2 Add pattern rules to project load format
    - Deserialize pattern_rules from project JSON
    - Validate loaded rules
    - Handle missing or corrupted rule data
    - _Requirements: 12.2, 12.4, 12.6_
  
  - [ ]* 10.3 Write integration tests for persistence
    - Test save and load round-trip
    - Test handling of corrupted data
    - Test backward compatibility

- [x] 11. Verify autotile and automap independence
  - [x] 11.1 Test automap does not modify autotile data
    - Apply automap rules to layer
    - Verify autotile rules and groups unchanged
    - _Requirements: 16.2_
  
  - [x] 11.2 Test autotile does not modify automap data
    - Apply autotile rules to layer
    - Verify automap pattern rules unchanged
    - _Requirements: 16.3_
  
  - [x] 11.3 Test sequential application of both systems
    - Apply autotile to layer
    - Apply automap to same layer
    - Verify both systems work correctly
    - _Requirements: 16.4_
  
  - [ ]* 11.4 Write property tests for data isolation
    - **Property 36: Autotile Data Isolation**
    - **Property 37: Automap Data Isolation**
    - **Validates: Requirements 16.2, 16.3**

- [x] 12. Add menu integration and UI polish
  - [x] 12.1 Add "Regex Automap Designer" menu item
    - Add menu item to appropriate menu
    - Connect menu item to RegexAutomapDesigner.show()
    - _Requirements: 7.1_
  
  - [x] 12.2 Add keyboard shortcuts
    - Add shortcut for opening automap designer
    - Add shortcuts for save/delete/apply within designer
    - Document shortcuts in UI
  
  - [x] 12.3 Add visual polish to scrollable rule list
    - Smooth scrolling animations (optional)
    - Hover effects on scrollbar
    - Fade effects at list edges
    - _Requirements: 17.1, 17.2_

- [ ] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation uses Python with pygame for UI rendering
- Pattern matching is optimized with early termination and sparse storage
- Transformation limits prevent infinite loops from circular dependencies
