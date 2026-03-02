# Dummy Services (Sandbox Environment)

## 1. Overview

This directory contains simulated microservices (`dummy_producer.py` and `dummy_consumer.py`) designed specifically for developer onboarding and architectural validation. 

These modules provide a "Sandbox Environment" that allows new contributors to observe and interact with the core concurrent topology—including the `SharedState` memory bank and the `ServiceManager` orchestrator—without requiring physical hardware (e.g., cameras, GPIO pins) or computationally expensive AI models.

## 2. Execution Guide

To safely execute these modules and observe the inter-thread communication, follow these steps:

**Step 1: Reroute the Service Manager**
Open the main configuration file located at `config/services_list.json` and temporarily replace its contents with the exact paths of the dummy modules:

```json
{
    "_comment": "SANDBOX MODE ACTIVE - Revert before pushing to production",
    "services": [
        "src.tests.dummies.dummy_producer.DummyProducer",
        "src.tests.dummies.dummy_consumer.DummyConsumer"
    ]
}
```

**Step 2: Launch the Node**
Initialize the system using the standard entry point. Since these modules do not require hardware integration, you can run this safely on any local machine (Windows, macOS, or Linux).

```bash
python3 src/core/main.py
```

## 3. Post-Test Protocol

**Critical**: Do not commit the modified `services_list.json` to the repository.
Once you have finished analyzing the console outputs and understanding the `SharedState` behavior, you must revert `services_list.json` to its original state, pointing to the real hardware services (CameraService, YoloService, etc.) before creating any Pull Requests.