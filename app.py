import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from obswebsocket import obsws, requests, exceptions
import json
import os
import time
from pythonosc import udp_client

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong secret key
app.debug = True  # Enable debugging
socketio = SocketIO(app, async_mode='eventlet')

# Global variables
obs_connections = {}     # Stores active OBS WebSocket connections
recording_status = {}    # Tracks recording status of each OBS instance
reaper_client = None     # OSC client for REAPER (initialized when configuration is set)

# In-memory storage for OBS instances
obs_instances = []

# Initialize REAPER IP and port as None
REAPER_IP = None
REAPER_PORT = None

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

# Function to update the REAPER client when IP or port changes
def update_reaper_client(ip, port):
    global REAPER_IP, REAPER_PORT, reaper_client
    REAPER_IP = ip
    REAPER_PORT = port
    try:
        reaper_client = udp_client.SimpleUDPClient(REAPER_IP, REAPER_PORT)
        print(f"Updated OSC client for REAPER at {REAPER_IP}:{REAPER_PORT}")
        return True
    except Exception as e:
        print(f"Error updating OSC client for REAPER: {e}")
        return False

# Start recording on all connected devices and REAPER
def start_recording():
    print("start_recording() called")
    # Compute the future start time (e.g., 5 seconds from now)
    start_time = time.time() + 5  # Adjust the delay as needed
    print(f"Scheduling recording to start at {time.ctime(start_time)}")

    # Start recording in REAPER
    socketio.start_background_task(start_reaper_recording_at_time, start_time)

    # For each OBS instance, schedule the start recording
    for key, ws in obs_connections.items():
        # Start a background task for each device
        socketio.start_background_task(start_recording_at_time, ws, key, start_time)

def start_reaper_recording_at_time(start_time):
    # Wait until start_time
    now = time.time()
    wait_time = start_time - now
    if wait_time > 0:
        print(f"Waiting {wait_time} seconds to start recording in REAPER")
        eventlet.sleep(wait_time)
    else:
        print("Start time already passed for REAPER, starting immediately")
    # Send the OSC command to start recording
    if reaper_client:
        try:
            reaper_client.send_message('/action/1013', [])  # Action ID 1013 corresponds to 'Transport: Record'
            print(f"Started recording in REAPER at {time.ctime(time.time())}")
        except Exception as e:
            print(f"Error starting recording in REAPER: {e}")
            socketio.emit('log', {'message': f"Error starting recording in REAPER: {e}"})
    else:
        print("REAPER client not configured. Cannot start recording in REAPER.")
        socketio.emit('log', {'message': "REAPER client not configured. Cannot start recording in REAPER."})

def start_recording_at_time(ws, key, start_time):
    # Wait until start_time
    now = time.time()
    wait_time = start_time - now
    if wait_time > 0:
        print(f"Waiting {wait_time} seconds to start recording on {key}")
        eventlet.sleep(wait_time)
    else:
        print(f"Start time already passed for {key}, starting immediately")
    # Now send the StartRecord command
    try:
        ws.call(requests.StartRecord())
        recording_status[key] = True
        print(f"Started recording on {key} at {time.ctime(time.time())}")
        # Update frontend
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

# Stop recording on all connected devices and REAPER
def stop_recording():
    print("stop_recording() called")
    # Stop recording in REAPER
    socketio.start_background_task(stop_reaper_recording)

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

def stop_reaper_recording():
    if reaper_client:
        try:
            reaper_client.send_message('/action/1016', [])  # Action ID 1016 corresponds to 'Transport: Stop'
            print(f"Stopped recording in REAPER at {time.ctime(time.time())}")
        except Exception as e:
            print(f"Error stopping recording in REAPER: {e}")
            socketio.emit('log', {'message': f"Error stopping recording in REAPER: {e}"})
    else:
        print("REAPER client not configured. Cannot stop recording in REAPER.")
        socketio.emit('log', {'message': "REAPER client not configured. Cannot stop recording in REAPER."})

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/start_recording', methods=['POST'])
def start_recording_route():
    start_recording()
    return jsonify({'status': 'success'})

@app.route('/stop_recording', methods=['POST'])
def stop_recording_route():
    stop_recording()
    return jsonify({'status': 'success'})

# New route to set REAPER configuration
@app.route('/set_reaper_config', methods=['POST'])
def set_reaper_config():
    data = request.get_json()
    ip = data.get('reaper_ip', None)
    port = data.get('reaper_port', None)

    if not ip or not port:
        return jsonify({'status': 'error', 'message': 'REAPER IP and port are required'}), 400

    # Update the REAPER client
    success = update_reaper_client(ip, int(port))
    if success:
        return jsonify({'status': 'success', 'message': f'REAPER configuration updated to {ip}:{port}'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update REAPER configuration'}), 500

# New route to get current REAPER configuration
@app.route('/get_reaper_config', methods=['GET'])
def get_reaper_config():
    if REAPER_IP and REAPER_PORT:
        return jsonify({'reaper_ip': REAPER_IP, 'reaper_port': REAPER_PORT})
    else:
        return jsonify({'reaper_ip': '', 'reaper_port': ''})

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
    # Remove or comment out the create_reaper_client() call
    # Start connection monitor thread
    socketio.start_background_task(monitor_connections)
    # Do not connect automatically on startup
    # Run the Flask app
    socketio.run(app, host='0.0.0.0', port=5000)
