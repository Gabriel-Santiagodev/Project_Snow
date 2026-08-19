---
name: qa
description: Guidelines for Testing and Quality Assurance (QA) in Project Snow using Pytest.
---

# Testing and Quality Assurance (QA)

## Test Structure
- Every new service must have tests written using the `pytest` framework.
- Files must be located in `tests/test_services/` following the convention `test_[service_name].py` (e.g., `test_audio_service.py`).

## Rules for Writing Tests (24/7 Environment)
1. **Hardware Mocking:** Since tests might run in environments without physical actuators (e.g., a developer's PC), EVERY GPIO pin (lights, OLED, buttons) or Hailo model must be mocked or simulated to prevent crashes caused by missing libraries like `gpiozero` or `hailo`.
2. **Edge Case Evaluation:** Tests must verify system behavior in a continuous 24/7 run state.
   - Example: What happens if the `person_detected` flag gets stuck as `True`? Does the service reset it to `False` after its actuation cycle?
   - Example: What happens if the camera continuously returns an empty frame (`None`)?
3. **Log Validation:** Ensure console logs are informative and correct. Tests should mock the logger to verify that service startup, detection triggers, and graceful shutdowns are properly documented.
4. **Fault Tolerance Verification:** Test that when a simulated logical error occurs, the service correctly calls `self.report_error()`, and that successful calls trigger `self.report_health()`.
