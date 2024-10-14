# OBS-MIDI-Controller

## Description

OBS Recording Dashboard is a Flask-based web application that allows users to manage and control multiple OBS (Open Broadcaster Software) instances remotely. It provides a centralized interface for starting and stopping recordings across multiple OBS instances simultaneously, triggered by MIDI signals.

## Features

- Connect to multiple OBS instances via WebSocket
- Start and stop recordings on all connected OBS instances simultaneously
- Trigger recording actions using MIDI signals
- Real-time status updates for each OBS instance
- Add and remove OBS instances dynamically
- Persistent storage of OBS instance configurations
- Responsive web interface for easy control and monitoring

## Prerequisites

- Python 3.7+
- OBS Studio 27.0+ with WebSocket plugin installed on all target machines
- A MIDI device (optional, for MIDI-triggered recording)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/Rid1Whitehead/OBS-MIDI-Controller.git
   cd obs-recording-dashboard
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
## Usage

1. Start the application:
   ```
   python app.py
   ```

2. Open a web browser and navigate to `http://localhost:5000` (or your server's IP address).

3. Set the MIDI port if you're using MIDI for triggering recordings.

4. Add OBS instances by providing their IP addresses, WebSocket ports, and passwords.

5. Connect to the OBS instances using the "Connect" button.

6. Start and stop recordings using MIDI signals.

## Adding OBS Instances

1. In the web interface, fill in the "Device Name", "Device IP", "Port", and "Password" fields.
2. Click "Add Device" to add the OBS instance to the dashboard.

## Connecting to OBS Instances

- Click "Connect to All OBS Instances" to connect to all added OBS instances.
- Alternatively, use the "Connect" button next to each instance to connect individually.

## MIDI Configuration

1. Connect your MIDI device to your computer.
2. In the web interface, enter the MIDI port name in the "Set MIDI Port" field.
3. Click "Set MIDI Port" to configure the MIDI listener.

## Troubleshooting

- Ensure all OBS instances and the dashboard are on the same network.
- Verify that the OBS WebSocket plugin is installed and configured correctly on all OBS instances.
- Check firewall settings to allow WebSocket connections on the specified ports.
- If a device doesn't connect, try removing and re-adding it to the dashboard.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- OBS Studio team for their excellent broadcasting software
- Flask and its extensions for providing a robust web framework
- Eventlet for enabling asynchronous operations
- MIDO for MIDI functionality

## Disclaimer

This software is provided as-is, without any warranties. Always test thoroughly in a non-production environment before using in critical recording scenarios.
