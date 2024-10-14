# OBS-MIDI-Controller
This app manages connections to OBS WebSocket instances and communicates with MIDI signals to control recording functions in OBS. It allows users to start and stop OBS recordings based on MIDI inputs, making it easy to automate video recording tasks using external MIDI controllers. Most importantly, it allows synchronized recording of multiple devices and audio tracks, which allows for the opportunity to use ffmpeg scripts to automize video editing.

## Overview
The OBS MIDI Recording Controller is a web-based application that allows users to manage multiple OBS (Open Broadcaster Software) instances over WebSocket and control their recording status using MIDI signals. Built using Flask and Flask-SocketIO, this app provides real-time control of OBS recording functions through MIDI inputs, simplifying the process of automating video recording tasks.

## Key Features
- **Manage Multiple OBS Instances**: Easily connect to and manage multiple OBS WebSocket servers.
- **MIDI-Controlled Recordings**: Start and stop recordings in OBS through MIDI signals, allowing hands-free control.
- **Real-time Status Updates**: View the connection status and recording state of each connected OBS instance in real time.
- **OBS WebSocket Integration**: Establish secure WebSocket connections with OBS instances to send recording commands.
- **Configuration File**: Use `devices.json` to store information about connected OBS devices, including their IP addresses, ports, and passwords.

## How It Works
- The app connects to OBS WebSocket instances, allowing remote control of recording features.
- It listens for MIDI input signals (via loopMIDI or similar software) and triggers start/stop recording commands based on the signals received.
- WebSocket events are used to update the app's frontend with the current status of each OBS instance, including whether it is currently recording.

## System Requirements
- **Python 3.11.5**
- **OBS with WebSocket Plugin**
- **MIDI Input Device or Software** (e.g., loopMIDI)
- **Supported Libraries**:
  - Flask
  - Flask-SocketIO
  - Eventlet
  - Mido
  - obs-websocket-py
  - rtpmidi
  - dnspython

## Installation
1. **Clone the Repository**: 
   Clone the repository to your local machine and navigate into the project directory.
  
   git clone <repository_url>
   cd <project_directory>
   python install -r requirements.txt
   python app.py

   The app will be accessible at http://localhost:5000 in your web browser.
