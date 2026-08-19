# Project Snow — Development Guidelines

## Project Overview
Project Snow is an autonomous edge-computing node (100% off-grid) using AI to assist visually impaired people.

## Architecture: Concurrent Microservices (`src/`)
- **Core Engine**: `ServiceManager` dynamically loads modules from `config/services_list.json`.
- **BaseService**: All threads inherit from `BaseService`. Logic goes in `_main_loop()`. Do not override `run()`.
- **State Management**: NO direct thread-to-thread communication. Use `SharedState` (Mutex protected).
  - Mutable (Queues): Use `.put()`, `.get()`. NEVER use `set_volatile()`.
  - Immutable (Bools): Use `.get_volatile()` and `.set_volatile()`.

## Core Rules
1. **MVP First**: Generate only necessary, functional code. No over-engineering.
2. **No Emojis**: Do not use emojis in code or UI.
3. **PEP 8**: Strictly follow Python PEP 8 styling.
4. **No Hardcoding**: All pins, paths, and thresholds MUST go in `config/settings.yaml`. Access via `self.config`.
5. **Observability**: NEVER use `print()`. Use `self.logger`.
6. **Graceful Exits**: Use `while not self._stop_event.is_set():`. No `while True:` for logic loops.
7. **Health Checks**: Call `self.report_error()` + `continue` on failure. Call `self.report_health()` on success.
8. **Permissions**: Do NOT commit or modify other branches without explicit permission.
9. **Documentation**: Explain all changes with professional, pedagogical detail.

## Target Branch
- **Target**: `innovafest` (Target for current sprint/exhibition).
- Feature branches (e.g., `lightservice`, `oledservice`, `camerasservice`) merge here.

## Deep Dive / Context Files (Read on demand)
If you need specific context, load the relevant skill:
- **Architecture**: `architecture` (Concurrency, SharedState details).
- **Hardware & Recovery**: `hardware_recovery` (Specs, Tiered Recovery, Zombie Loop).
- **QA & Testing**: `qa` (Pytest, Hardware Mocking, Edge Cases).
- **Project Background**: `project_background` (Full history, goals, and 'why' of Project Snow).
- **Final Phase Plan**: `final_phase_plan` (Block 1 & 2 instructions, expo logic, camera tracking details).
