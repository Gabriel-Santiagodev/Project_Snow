# Models Directory

This directory contains AI model files for object detection.

## Required Files

### `best.pt` - YOLOv8 Trained Model
- **Size:** ~ TBD (To Be Determined)
- **Purpose:** Person detection for blind assistance
- **Framework:** Ultralytics YOLOv8

## How to Obtain

These files are **not stored in Git** due to their large size.

### Option 1: Download from Team Storage
[Google Drive/OneDrive link ]

### Option 2: Train Your Own Model
If you want to train a custom model:
```bash
# Install ultralytics
pip install ultralytics

# Train on your dataset
yolo train data=your_dataset.yaml model=yolov8n.pt epochs=100
```

## Installation

1. Download `best.pt` from the link above
2. Place it in this directory: `data/models/best.pt`
3. Verify the path matches `settings.yaml`:
```yaml
   ai_model:
     model_path: "data/models/best.pt"
```

## File Structure
```
data/models/
├── .gitkeep          # Preserves folder in git
├── README.md         # This file
└── best.pt           # YOLOv8 model (download separately)
```

---

**⚠️ Important:** Do not commit `.pt` files to git! They are already in `.gitignore`.