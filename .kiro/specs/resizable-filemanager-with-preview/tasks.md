# Implementation Plan: Resizable FileManager with Preview

## Overview

This implementation plan adds resizability and PNG image preview capabilities to the existing FileManager widget in the Python-based tilemap editor. The implementation follows a modular approach with three main subsystems: resize handling, image preview, and dimension persistence.

## Tasks

- [x] 1. Set up dimension persistence system
  - Create DimensionPersistence class in src/widgets/filemanager.py
  - Implement save_dimensions() and load_dimensions() methods
  - Use JSON format for storage in {BASE_PATH}/data/filemanager_prefs.json
  - Handle missing or corrupted preference files gracefully
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 1.1 Write unit tests for dimension persistence
  - Test saving and loading dimensions
  - Test handling of missing preference files
  - Test handling of corrupted JSON files
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 2. Implement ResizeHandler component
  - [x] 2.1 Create ResizeHandler class with initialization
    - Initialize with widget_rect, min_width=400, min_height=300
    - Set up drag state tracking attributes
    - _Requirements: 1.1, 1.3, 1.4_
  
  - [x] 2.2 Implement resize handle detection
    - Write get_handle_at_pos() method to detect right edge (5px wide)
    - Detect bottom edge (5px tall) and corner (10x10px) handles
    - Return handle type ('right', 'bottom', 'corner') or None
    - _Requirements: 1.1_
  
  - [x] 2.3 Implement drag state management
    - Write start_drag() to capture initial position and rect
    - Write update_drag() to calculate new dimensions with constraints
    - Write end_drag() to reset drag state
    - _Requirements: 1.2, 1.3, 1.4_
  
  - [x] 2.4 Implement draw_handles() method
    - Render visual indicators for resize handles
    - Use appropriate colors and styling consistent with widget theme
    - _Requirements: 1.1_

- [ ]* 2.5 Write property test for resize constraints
  - **Property 1: Dimension constraints are always enforced**
  - **Validates: Requirements 1.3, 1.4**
  - Test that resizing never produces dimensions below minimums

- [ ] 3. Checkpoint - Verify resize handler works independently
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement ImagePreview component
  - [x] 4.1 Create ImagePreview class with initialization
    - Initialize with max_file_size_mb=50
    - Set up state attributes for current image, path, dimensions, errors
    - _Requirements: 2.1, 2.2, 4.4_
  
  - [x] 4.2 Implement image loading with error handling
    - Write load_image() to check file size before loading
    - Use pygame.image.load() for supported formats
    - Catch pygame.error for corrupted files
    - Display "file too large" message for files > 50MB
    - _Requirements: 2.2, 4.1, 4.2, 4.3, 4.4_
  
  - [x] 4.3 Implement image scaling logic
    - Write scale_to_fit() to maintain aspect ratio
    - Use calculate_scaled_dimensions() helper function
    - Cache scaled images to avoid redundant processing
    - _Requirements: 2.4_
  
  - [x] 4.4 Implement preview panel rendering
    - Write draw() method to render image, dimensions text, and close button
    - Position elements within provided rect
    - Display error messages when image cannot be loaded
    - _Requirements: 2.2, 2.3, 2.7, 4.1, 4.2_

- [ ]* 4.5 Write unit tests for image preview
  - Test loading valid images
  - Test handling corrupted images
  - Test file size limit enforcement
  - Test aspect ratio preservation during scaling
  - _Requirements: 2.2, 2.4, 4.1, 4.2, 4.3, 4.4_

- [x] 5. Integrate components into FileManager
  - [x] 5.1 Add new attributes to FileManager.__init__()
    - Initialize ResizeHandler with widget rect and constraints
    - Initialize ImagePreview with file size limit
    - Initialize DimensionPersistence with preference file path
    - Load and apply saved dimensions on startup
    - _Requirements: 1.1, 2.1, 5.2_
  
  - [x] 5.2 Implement layout calculation methods
    - Write _get_file_list_rect() to calculate file list area
    - Write _get_preview_rect() to calculate preview panel area
    - Implement 60/40 split when preview is visible
    - Ensure file list minimum width of 40% of content area
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 5.3 Implement preview activation methods
    - Write _show_preview() to load and display image for selected file
    - Write _hide_preview() to clear preview and restore full-width file list
    - Check file extension (.png, .jpg, .jpeg) before showing preview
    - _Requirements: 2.1, 2.5, 2.6, 3.5, 3.6_
  
  - [x] 5.4 Enhance handle_event() for resize interactions
    - Add resize handle hover detection with cursor change
    - Handle mouse button down to start drag
    - Handle mouse motion to update dimensions during drag
    - Handle mouse button up to end drag and persist dimensions
    - _Requirements: 1.1, 1.2, 5.1_
  
  - [x] 5.5 Enhance handle_event() for preview interactions
    - Detect clicks on image files to show preview
    - Detect clicks on non-image files to hide preview
    - Detect clicks on preview close button to hide preview
    - _Requirements: 2.1, 2.5, 2.6, 3.5, 3.6_
  
  - [x] 5.6 Update draw() method for new components
    - Call resize_handler.draw_handles() to render resize handles
    - Call image_preview.draw() when preview is visible
    - Adjust file list rendering to use _get_file_list_rect()
    - _Requirements: 1.1, 2.3_
  
  - [x] 5.7 Update _draw_file_list() for dynamic layout
    - Use _get_file_list_rect() instead of fixed dimensions
    - Ensure proper reflow when preview panel is shown/hidden
    - Maintain scrolling behavior with adjusted dimensions
    - _Requirements: 1.5, 3.1, 3.4_

- [ ] 6. Checkpoint - Verify integration and layout behavior
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 7. Write integration tests for complete feature
  - Test resize interaction with preview panel visible
  - Test preview panel with various image sizes and formats
  - Test dimension persistence across widget lifecycle
  - Test layout adjustments when toggling preview
  - _Requirements: 1.2, 1.5, 1.6, 2.1, 2.6, 3.1, 3.6, 5.1, 5.2_

- [ ] 8. Final checkpoint - Verify all functionality
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The implementation maintains the existing FileManager architecture while adding modular components
- Resize handles follow standard UI conventions (right, bottom, corner)
- Preview panel uses 60/40 split with file list when visible
- Dimension persistence uses JSON format consistent with existing recents.json
