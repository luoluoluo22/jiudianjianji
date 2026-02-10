# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- **Install Dependencies**: `pip install requests pymediainfo pillow uiautomation playwright pynput edge-tts`
- **Global Installation**: Run the PowerShell script `install.ps1` to set up the environment and link skills to supported editors (Claude Code, Trae, Antigravity).
- **Environment Variable**: `JY_SKILL_ROOT` should point to the root of the `jianying-editor` skill directory.

### Build and Packaging
- **Build Executable**: `pyinstaller --noconfirm gui_launcher.spec`
- **Alternative Build Scripts**: `python build_exe.py` or `python build_gui.py`

### Execution
- **Main GUI Launcher**: `python gui_launcher.py`
- **CLI Launcher**: `python launcher.py`
- **Visualizer**: `python start_visualizer.py`
- **Debug UI Tree**: `python debug_ui_tree.py` (Used to inspect the Jianying desktop UI structure)

## Architecture and Structure

### High-Level Design
This project is an automation framework for the **Jianying (CapCut Desktop)** video editor. It operates by controlling the Windows desktop application via UI automation and interacting with its internal files/API.

### Core Components
- **UI Automation**: Uses `uiautomation` and `pynput` to interact with the Jianying interface. `ui_tree.txt` and `debug_ui_tree.py` are critical for mapping UI elements.
- **Exporter Core (`exporter_core.py`)**: Central logic for managing the export process within Jianying.
- **Media Processing**: Uses `pymediainfo` for metadata and `extract_speaking_segments.py` for audio analysis.
- **TTS Integration**: Uses `edge-tts` for generating voiceovers.
- **Skills System**: The project is structured to work as a "Skill" for AI agents, located in the `.agent/skills/` directory.

### Key Files
- `gui_launcher.py`: The primary entry point for the user-facing application.
- `exporter_core.py`: Contains the low-level automation logic for the editor.
- `install.ps1`: Orchestrates the deployment of the skill across different AI coding environments.
- `*.spec`: PyInstaller configurations for creating standalone Windows binaries.
