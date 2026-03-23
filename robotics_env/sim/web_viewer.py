#!/usr/bin/env python3
"""Web-based 3D viewer for Go2 robot simulation.

Receives robot state via UDP from launch_isaaclab.py and serves a Three.js
web page that renders the robot in real-time. All 3D rendering happens in
the client browser — no GPU rendering needed on the server.

Usage:
    python3 web_viewer.py [--port 8080] [--udp-port 9872]

Then open http://<SPARK_IP>:8080/ in your browser.
"""
from __future__ import annotations
import argparse, json, struct, socket, time, threading, math
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Must match launch_isaaclab.py
STATE_FMT = "!d3d4d3d3d12d12d"
STATE_SIZE = struct.calcsize(STATE_FMT)

JOINT_NAMES = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]

# Go2 default joint positions (standing pose)
DEFAULT_JOINT_POS = [
    0.1, -0.1, 0.1, -0.1,    # hips
    0.8, 0.8, 1.0, 1.0,       # thighs
    -1.5, -1.5, -1.5, -1.5,   # calves
]


class StateReceiver:
    """Receives robot state via UDP in a background thread."""

    def __init__(self, port=9872):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(1.0)
        self._state = None
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        self._count = 0

    def _recv_loop(self):
        while self._running:
            try:
                data, _ = self.sock.recvfrom(STATE_SIZE + 64)
            except socket.timeout:
                continue
            except Exception:
                continue
            if len(data) != STATE_SIZE:
                continue
            values = struct.unpack(STATE_FMT, data)
            idx = 0
            sim_time = values[idx]; idx += 1
            pos = list(values[idx:idx+3]); idx += 3
            quat_wxyz = list(values[idx:idx+4]); idx += 4
            lin_vel = list(values[idx:idx+3]); idx += 3
            ang_vel = list(values[idx:idx+3]); idx += 3
            joint_pos = list(values[idx:idx+12]); idx += 12
            joint_vel = list(values[idx:idx+12]); idx += 12

            state = {
                "t": round(sim_time, 3),
                "pos": [round(v, 4) for v in pos],
                "quat": [round(v, 5) for v in quat_wxyz],  # w,x,y,z
                "jp": [round(v, 4) for v in joint_pos],
            }
            with self._lock:
                self._state = state
            self._count += 1
            if self._count == 1:
                print(f"[viewer] First state received: pos={pos[:3]}", flush=True)

    def get_state_json(self):
        with self._lock:
            return self._state

    def stop(self):
        self._running = False
        self.sock.close()


# ---------------------------------------------------------------------------
# HTML/JS Three.js Viewer
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Go2 Sim Viewer</title>
<style>
  body { margin: 0; overflow: hidden; background: #1a1a2e; font-family: monospace; }
  #info {
    position: absolute; top: 10px; left: 10px; color: #0f0;
    font-size: 13px; z-index: 100; background: rgba(0,0,0,0.6);
    padding: 8px 12px; border-radius: 4px;
  }
  #status { color: #ff0; }
</style>
</head>
<body>
<div id="info">
  Go2 Isaac Sim Viewer<br>
  <span id="status">Connecting...</span><br>
  <span id="telemetry"></span>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
// Go2 dimensions (meters)
const BODY_L = 0.38, BODY_W = 0.094*2, BODY_H = 0.07;
const HIP_L = 0.08;
const THIGH_L = 0.213;
const CALF_L = 0.213;

// Hip offsets from body center [x, y] (Isaac Lab order: FL, FR, RL, RR)
const HIP_OFFSETS = [
  [ 0.1881,  0.04675],  // FL
  [ 0.1881, -0.04675],  // FR
  [-0.1881,  0.04675],  // RL
  [-0.1881, -0.04675],  // RR
];
// Hip sign: FL/RL positive Y, FR/RR negative Y
const HIP_SIGN = [1, -1, 1, -1];

// Default joint positions
const DEFAULT_JP = [0.1,-0.1,0.1,-0.1, 0.8,0.8,1.0,1.0, -1.5,-1.5,-1.5,-1.5];

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);
scene.fog = new THREE.Fog(0x1a1a2e, 8, 25);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 100);
camera.position.set(1.5, 1.0, 1.5);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.25, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.1;

// Lights
const ambient = new THREE.AmbientLight(0x404060, 0.6);
scene.add(ambient);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(1024, 1024);
scene.add(dirLight);
const hemiLight = new THREE.HemisphereLight(0x6688cc, 0x333322, 0.4);
scene.add(hemiLight);

// Ground grid
const gridHelper = new THREE.GridHelper(20, 40, 0x444466, 0x222244);
scene.add(gridHelper);
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(20, 20),
  new THREE.MeshStandardMaterial({ color: 0x222233, roughness: 0.9 })
);
ground.rotation.x = -Math.PI/2;
ground.position.y = -0.001;
ground.receiveShadow = true;
scene.add(ground);

// Robot materials
const bodyMat = new THREE.MeshStandardMaterial({ color: 0x2255aa, roughness: 0.5, metalness: 0.3 });
const legMat = new THREE.MeshStandardMaterial({ color: 0x888899, roughness: 0.4, metalness: 0.5 });
const footMat = new THREE.MeshStandardMaterial({ color: 0xdd4444, roughness: 0.6 });

// Build robot
const robotGroup = new THREE.Group();
scene.add(robotGroup);

// Body
const bodyMesh = new THREE.Mesh(
  new THREE.BoxGeometry(BODY_L, BODY_H, BODY_W),
  bodyMat
);
bodyMesh.castShadow = true;
robotGroup.add(bodyMesh);

// Head indicator (front of robot)
const headMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.03, 0.06, 8),
  new THREE.MeshStandardMaterial({ color: 0x44ff44 })
);
headMesh.position.set(BODY_L/2 + 0.03, 0, 0);
headMesh.rotation.z = -Math.PI/2;
robotGroup.add(headMesh);

// Leg segments: for each leg, create hip, thigh, calf meshes
// Stored as [hipPivot, thighPivot, calfPivot] groups
const legs = [];
for (let i = 0; i < 4; i++) {
  // Hip pivot (at body attachment point)
  const hipPivot = new THREE.Group();
  hipPivot.position.set(HIP_OFFSETS[i][0], 0, HIP_OFFSETS[i][1]);
  robotGroup.add(hipPivot);

  // Hip link (short horizontal segment)
  const hipMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.015, 0.015, HIP_L, 8),
    legMat
  );
  hipMesh.rotation.x = Math.PI/2;
  hipMesh.position.z = HIP_SIGN[i] * HIP_L/2;
  hipMesh.castShadow = true;
  hipPivot.add(hipMesh);

  // Thigh pivot (at end of hip)
  const thighPivot = new THREE.Group();
  thighPivot.position.set(0, 0, HIP_SIGN[i] * HIP_L);
  hipPivot.add(thighPivot);

  // Thigh link
  const thighMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.014, THIGH_L, 8),
    legMat
  );
  thighMesh.position.y = -THIGH_L/2;
  thighMesh.castShadow = true;
  thighPivot.add(thighMesh);

  // Calf pivot (at end of thigh)
  const calfPivot = new THREE.Group();
  calfPivot.position.y = -THIGH_L;
  thighPivot.add(calfPivot);

  // Calf link
  const calfMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.014, 0.010, CALF_L, 8),
    legMat
  );
  calfMesh.position.y = -CALF_L/2;
  calfMesh.castShadow = true;
  calfPivot.add(calfMesh);

  // Foot (small sphere at end of calf)
  const footMesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.015, 8, 8),
    footMat
  );
  footMesh.position.y = -CALF_L;
  footMesh.castShadow = true;
  calfPivot.add(footMesh);

  legs.push({ hipPivot, thighPivot, calfPivot });
}

// Apply joint angles to robot
// Joint order: [FL_hip, FR_hip, RL_hip, RR_hip,
//               FL_thigh, FR_thigh, RL_thigh, RR_thigh,
//               FL_calf, FR_calf, RL_calf, RR_calf]
function applyJoints(jp) {
  for (let i = 0; i < 4; i++) {
    // Hip rotation (around X axis in body frame)
    legs[i].hipPivot.rotation.x = jp[i];
    // Thigh rotation (around Z axis, pitch)
    legs[i].thighPivot.rotation.z = -jp[i + 4];
    // Calf rotation (around Z axis, pitch)
    legs[i].calfPivot.rotation.z = -jp[i + 8];
  }
}

// Apply body pose (position + quaternion w,x,y,z)
function applyPose(pos, quat_wxyz) {
  robotGroup.position.set(pos[0], pos[2], -pos[1]);  // Isaac Y->Three Z, Z->Y
  // Convert wxyz to Three.js quaternion (x,y,z,w) with axis swap
  // Isaac: X-fwd Y-left Z-up → Three: X-right Y-up Z-back
  // qx→qx, qz→qy, -qy→qz, qw→qw (no extra frame rotation needed)
  const q = new THREE.Quaternion(quat_wxyz[1], quat_wxyz[3], -quat_wxyz[2], quat_wxyz[0]);
  robotGroup.quaternion.copy(q);
}

// Apply default pose
applyJoints(DEFAULT_JP);
applyPose([0, 0, 0.35], [1, 0, 0, 0]);

// State polling
let lastState = null;
let connected = false;
let stateCount = 0;

function fetchState() {
  fetch('/state')
    .then(r => r.json())
    .then(state => {
      if (state && state.pos) {
        lastState = state;
        connected = true;
        stateCount++;
      }
    })
    .catch(() => { connected = false; });
}
setInterval(fetchState, 40);  // 25 Hz polling

// Animate
function animate() {
  requestAnimationFrame(animate);

  if (lastState) {
    applyPose(lastState.pos, lastState.quat);
    applyJoints(lastState.jp);

    // Camera follow (smooth)
    const tp = robotGroup.position;
    controls.target.lerp(new THREE.Vector3(tp.x, tp.y, tp.z), 0.05);
  }

  controls.update();
  renderer.render(scene, camera);

  // Update UI
  const statusEl = document.getElementById('status');
  const telEl = document.getElementById('telemetry');
  if (connected && lastState) {
    statusEl.textContent = 'Connected';
    statusEl.style.color = '#0f0';
    telEl.textContent =
      `t=${lastState.t.toFixed(1)}s ` +
      `pos=(${lastState.pos[0].toFixed(2)}, ${lastState.pos[1].toFixed(2)}, ${lastState.pos[2].toFixed(3)})`;
  } else {
    statusEl.textContent = 'Waiting for sim...';
    statusEl.style.color = '#ff0';
  }
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(description="Go2 Web Viewer")
    ap.add_argument("--port", type=int, default=8080, help="HTTP server port")
    ap.add_argument("--udp-port", type=int, default=9872, help="UDP port for state input")
    args = ap.parse_args()

    # Start state receiver
    receiver = StateReceiver(port=args.udp_port)
    print(f"[viewer] Listening for state on UDP port {args.udp_port}", flush=True)

    # HTTP server
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_PAGE.encode("utf-8"))
            elif self.path == "/state":
                state = receiver.get_state_json()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if state:
                    self.wfile.write(json.dumps(state).encode())
                else:
                    self.wfile.write(b'{}')
            else:
                self.send_error(404)

        def log_message(self, format, *a):
            pass

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[viewer] HTTP server: http://0.0.0.0:{args.port}/", flush=True)
    print(f"[viewer] Open http://<SPARK_IP>:{args.port}/ in your browser", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        server.shutdown()
        print("[viewer] Shutdown.", flush=True)


if __name__ == "__main__":
    main()
