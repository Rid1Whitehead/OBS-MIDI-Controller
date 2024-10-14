import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import mido
from obswebsocket import obsws, requests, exceptions
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong secret key
app.debug = True  # Enable debugging
socketio = SocketIO(app, async_mode='eventlet')

# Global variables
obs_connections = {}     # Stores active OBS WebSocket connections
recording_status = {}    # Tracks recording status of each OBS instance

# In-memory storage for OBS instances
obs_instances = []

# Load OBS instances from a JSON file
def load_obs_instances():
    global obs_instances
    if os.path.exists('devices.json'):
        with open('devices.json', 'r') as f:
            try:
                obs_instances = json.load(f)
                print(f"Loaded {len(obs_instances)} OBS instances from devices.json")
            except json.JSONDecodeError as e:
                print(f"Error decoding devices.json: {e}")
                obs_instances = []
    else:
        obs_instances = []

# Save OBS instances to a JSON file
def save_obs_instances():
    with open('devices.json', 'w') as f:
        json.dump(obs_instances, f, indent=4)
        print("Saved OBS instances to devices.json")

# Establish OBS WebSocket connection to a single device
def connect_to_obs_instance(ip, port):
    global obs_instances
    key = f"{ip}:{port}"
    if key not in obs_connections:
        # Find the device in obs_instances to get password and name
        device = next((obs for obs in obs_instances if obs['ip'] == ip and str(obs['port']) == str(port)), None)
        if device:
            ws = obsws(host=ip, port=port, password=device['password'])
            try:
                ws.connect()
                obs_connections[key] = ws
                recording_status[key] = False
                print(f"Connected to OBS at {key}")

                # Notify frontend about the new connection
                socketio.emit('device_status', {
                    'ip': ip,
                    'port': port,
                    'name': device.get('name', ''),
                    'status': 'Connected',
                    'recording': False
                })
            except exceptions.ConnectionFailure as e:
                print(f"Failed to connect to OBS at {key}: {e}")
                socketio.emit('device_status', {
                    'ip': ip,
                    'port': port,
                    'name': device.get('name', ''),
                    'status': 'Disconnected',
                    'recording': False
                })
                return False
        else:
            print(f"Device with IP {ip} and port {port} not found in obs_instances.")
            return False
    else:
        print(f"Already connected to OBS at {key}")
    return True

# Establish OBS WebSocket connections to all devices
def connect_to_obs_instances():
    global obs_instances
    for obs in obs_instances:
        connect_to_obs_instance(obs['ip'], obs['port'])

# Disconnect from an OBS instance
def disconnect_obs_instance(ip, port):
    key = f"{ip}:{port}"
    if key in obs_connections:
        try:
            obs_connections[key].disconnect()
            print(f"Disconnected from OBS at {key}")
        except Exception as e:
            print(f"Error disconnecting from OBS at {key}: {e}")
        del obs_connections[key]
        del recording_status[key]
        # Find the device in obs_instances to get the name
        device_name = ''
        for obs in obs_instances:
            if obs['ip'] == ip and str(obs['port']) == str(port):
                device_name = obs.get('name', '')
                break
        socketio.emit('device_status', {
            'ip': ip,
            'port': port,
            'name': device_name,
            'status': 'Disconnected',
            'recording': False
        })
    else:
        print(f"No active connection to OBS at {key}")

# Background task to monitor connections
def monitor_connections():
    while True:
        keys_to_remove = []
        for key, ws in list(obs_connections.items()):
            try:
                ws.call(requests.GetVersion())
            except Exception as e:
                print(f"Connection to OBS at {key} lost: {e}")
                keys_to_remove.append(key)
                # Get device info
                ip, port = key.split(':')
                device = next((obs for obs in obs_instances if obs['ip'] == ip and str(obs['port']) == port), None)
                device_name = device.get('name', '') if device else ''
                # Emit device_status to frontend
                with app.app_context():
                    socketio.emit('device_status', {
                        'ip': ip,
                        'port': port,
                        'name': device_name,
                        'status': 'Disconnected',
                        'recording': False
                    })
        # Remove disconnected connections
        for key in keys_to_remove:
            if key in obs_connections:
                del obs_connections[key]
            if key in recording_status:
                del recording_status[key]
        eventlet.sleep(5)  # Wait for 5 seconds before next check

# Modify the midi_listener to use the dynamic midi_port variable
def midi_listener():
    print("MIDI listener started")
    try:
        with mido.open_input(midi_port) as port:
            print(f"Listening for MIDI messages on port: {port.name}")
            while True:
                for msg in port.iter_pending():
                    print(f"Received MIDI message: {msg}")
                    if msg.type == 'start':
                        start_recording()
                    elif msg.type == 'stop':
                        stop_recording()
                eventlet.sleep(0.1)
    except Exception as e:
        print(f"MIDI Error: {e}")
        socketio.emit('log', {'message': f"MIDI Error: {e}"})

# Start the MIDI listener in a background task
def start_midi_thread():
    socketio.start_background_task(midi_listener)

# Start recording on all connected devices
def start_recording():
    print("start_recording() called")
    for key, ws in obs_connections.items():
        try:
            ws.call(requests.StartRecord())
            recording_status[key] = True
            print(f"Started recording on {key}")
            # Find the device in obs_instances to get the name
            device_name = ''
            for obs in obs_instances:
                if obs['ip'] == ws.host and str(obs['port']) == str(ws.port):
                    device_name = obs.get('name', '')
                    break
            socketio.emit('device_status', {
                'ip': ws.host,
                'port': ws.port,
                'name': device_name,
                'status': 'Connected',
                'recording': True
            })
        except Exception as e:
            print(f"Error starting recording on {key}: {e}")
            socketio.emit('log', {'message': f"Error starting recording on {key}: {e}"})

# Stop recording on all connected devices
def stop_recording():
    print("stop_recording() called")
    for key, ws in obs_connections.items():
        try:
            response = ws.call(requests.StopRecord())
            recording_status[key] = False
            print(f"Stopped recording on {key}")
            # Find the device in obs_instances to get the name
            device_name = ''
            for obs in obs_instances:
                if obs['ip'] == ws.host and str(obs['port']) == str(ws.port):
                    device_name = obs.get('name', '')
                    break
            socketio.emit('device_status', {
                'ip': ws.host,
                'port': ws.port,
                'name': device_name,
                'status': 'Connected',
                'recording': False
            })
            # Optionally, handle the recording path
            if hasattr(response, 'getOutputPath'):
                output_path = response.getOutputPath()
                socketio.emit('log', {'message': f"Recording saved to {output_path}"})
        except Exception as e:
            print(f"Error stopping recording on {key}: {e}")
            socketio.emit('log', {'message': f"Error stopping recording on {key}: {e}"})

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_midi_port', methods=['POST'])
def set_midi_port():
    global midi_port
    data = request.get_json()
    new_midi_port = data.get('midi_port', None)
    
    if not new_midi_port:
        return jsonify({'status': 'error', 'message': 'MIDI port is required'}), 400
    
    midi_port = new_midi_port
    print(f"MIDI port updated to: {midi_port}")

    # Restart the MIDI listener with the new port
    start_midi_thread()
    
    return jsonify({'status': 'success', 'message': f'MIDI port set to {midi_port}'})

@app.route('/get_devices', methods=['GET'])
def get_devices():
    device_list = []
    for obs in obs_instances:
        key = f"{obs['ip']}:{obs['port']}"
        status = 'Connected' if key in obs_connections else 'Disconnected'
        recording = recording_status.get(key, False)
        device = {
            'ip': obs['ip'],
            'port': obs['port'],
            'name': obs.get('name', ''),
            'status': status,
            'recording': recording
        }
        device_list.append(device)
    return jsonify(device_list)

@app.route('/add_device', methods=['POST'])
def add_device():
    global obs_instances
    data = request.get_json()
    print(f"Received add_device request: {data}")
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    # Check if the device already exists
    for obs in obs_instances:
        if obs['ip'] == data['ip'] and str(obs['port']) == str(data['port']):
            return jsonify({'status': 'error', 'message': 'Device already exists'}), 400
    obs_instances.append(data)
    save_obs_instances()
    # Do not connect automatically
    # Notify frontend to update the devices table
    socketio.emit('device_status', {
        'ip': data['ip'],
        'port': data['port'],
        'name': data.get('name', ''),
        'status': 'Disconnected',
        'recording': False
    })
    return jsonify({'status': 'success'})

@app.route('/remove_device', methods=['POST'])
def remove_device():
    global obs_instances
    data = request.get_json()
    print(f"Received remove_device request: {data}")
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    obs_instances = [i for i in obs_instances if not (i['ip'] == data['ip'] and str(i['port']) == str(data['port']))]
    save_obs_instances()
    # Disconnect if connected
    disconnect_obs_instance(data['ip'], data['port'])
    return jsonify({'status': 'success'})

@app.route('/connect_obs_instances', methods=['POST'])
def connect_obs_instances_route():
    connect_to_obs_instances()
    return jsonify({'status': 'success'})

@app.route('/connect_device', methods=['POST'])
def connect_device_route():
    data = request.get_json()
    print(f"Received connect_device request: {data}")
    if not data or 'ip' not in data or 'port' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    success = connect_to_obs_instance(data['ip'], data['port'])
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to connect'}), 500

@app.route('/disconnect_device', methods=['POST'])
def disconnect_device_route():
    data = request.get_json()
    print(f"Received disconnect_device request: {data}")
    if not data or 'ip' not in data or 'port' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    disconnect_obs_instance(data['ip'], data['port'])
    return jsonify({'status': 'success'})

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print("Client connected")
    # Send current device statuses
    for obs in obs_instances:
        key = f"{obs['ip']}:{obs['port']}"
        status = 'Connected' if key in obs_connections else 'Disconnected'
        recording = recording_status.get(key, False)
        emit('device_status', {
            'ip': obs['ip'],
            'port': obs['port'],
            'name': obs.get('name', ''),
            'status': status,
            'recording': recording
        })

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    # Load OBS instances from devices.json
    load_obs_instances()
    # Start MIDI listener thread
    start_midi_thread()
    # Start connection monitor thread
    socketio.start_background_task(monitor_connections)
    # Do not connect automatically on startup
    # Run the Flask app
    socketio.run(app, host='0.0.0.0', port=5000)
