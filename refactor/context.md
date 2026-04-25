# Refactor Context

## Why This Refactor

The tilemap editor has evolved organically over time, resulting in significant code duplication, inconsistent patterns, and scattered implementations. The code works but is difficult to maintain, extend, and debug.

## What Issues Exist

1. **Code Duplication**
   - 44 hardcoded `pygame.font.SysFont` calls instead of centralized font_manager
   - Hardcoded colors like `(30,30,30)`, `(20,20,20)` scattered across files
   - Button drawing repeated in 6+ files
   - Modal dialog background repeated 5 times
   - Scrollbar calculation repeated 4 times
   - Radio button code 95% identical in two dialogs

2. **Inconsistent Patterns**
   - UI components use different approaches to same problems
   - Event handling boilerplate duplicated everywhere
   - No clear base class hierarchy for UI widgets
   - theme.py exists but not used consistently

3. **Entry Point Confusion**
   - editor.py is the main entry point
   - Hard to trace component dependencies

## Reasons For Refactor Approach

### Why Start From editor.py
- Central hub - understanding its dependencies reveals the component tree
- Safe refactors first (utility functions, constants) won't break integration
- Can identify coupling before touching tightly-coupled components

### Why Not Jump to Core Files
- Risk of breaking integration without understanding dependencies
- Need context of how components connect
- Better to refactor incrementally, testing at each step

### Why Not Everything at Once
- Large rewrites are risky and hard to verify
- Small, focused refactors are testable and reversible
- Allows learning as we refactor

## Causes (Root Issues)

1. **No UI Base Architecture**
   - No common foundation for UI components
   - Each widget reinventing similar patterns

2. **No Shared Input Component**
   - FilenameInput and FormInput have duplicated text handling
   - Could have shared base

3. **No Scroll View Abstraction**
   - 4 components repeat same scroll logic

4. **No Modal/Dialog Abstraction**
   - 5+ files repeat modal background + overlay

## What We Have As Reference

The `refactor/reference/uibase/` folder contains UI patterns from a 2D game project that demonstrate clean, reusable architecture:
- UIOptions - declarative config
- box_model - CSS-like layout
- UIBase - base class with plugin system
- ProgressBarUI example
- CooldownOverlay example

**Note:** These are examples to learn from, NOT everything needs this pattern - adapt where it makes sense.

## Approach

1. **Phase 1:** Reference setup + scan (done)
2. **Phase 2:** Entry point (editor.py) analysis + safe refactors
3. **Phase 3:** Core utilities (event management, etc.)
4. **Phase 4:** Component refactors (least coupled first)
5. **Phase 5:** UI components (reuse UIBase where applicable)

## Non-Goals

- Not a complete rewrite
- Not adding unnecessary abstraction
- Not breaking existing functionality
- Not changing user-facing behavior