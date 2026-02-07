# Audio Directory

This directory contains audio alert files for the blind assistance system.

## Required Files - TBD (To Be Determined)

### `sonido_prueva0.mp3`
- **Size:** ~ TBD (To Be Determined)
- **Purpose:** Primary alert sound
- **Format:** MP3

### `sonido_prueva2.mp3`
- **Size:** ~ TBD (To Be Determined)
- **Purpose:** Secondary alert sound
- **Format:** MP3

## How to Obtain

These files are **not stored in Git** to keep the repository lightweight.

### Download from Team Storage
[Google Drive/OneDrive link]

## Installation

1. Download the audio files from the link above
2. Place them in this directory:
```
   data/audio/sonido_prueva0.mp3
   data/audio/sonido_prueva2.mp3
```
3. Verify the paths match `settings.yaml`:
```yaml
   audio:
     audio_files:
       sonido_prueva0_path: "data/audio/sonido_prueva0.mp3"
       sonido_prueva2_path: "data/audio/sonido_prueva2.mp3"
```

## File Structure
```
data/audio/
├── .gitkeep                # Preserves folder in git
├── README.md               # This file
├── sonido_prueva0.mp3     # Alert sound 1 (download separately)
└── sonido_prueva2.mp3     # Alert sound 2 (download separately)
```

## Testing Audio

To test if audio files are working:
```python
import pygame
pygame.mixer.init()
pygame.mixer.music.load("data/audio/sonido_prueva0.mp3")
pygame.mixer.music.play()
```

---

**⚠️ Important:** Do not commit `.mp3` or `.wav` files to git! They are already in `.gitignore`.