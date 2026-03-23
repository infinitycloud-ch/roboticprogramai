#!/usr/bin/env python3
"""Read current robot state and output human-readable text for LLM consumption.

Reads state from the web_viewer HTTP endpoint (localhost).
Outputs a single text description on stdout, then exits.

Usage:
    python3 mono_robot_sense.py
"""
import sys
import math
import json
import urllib.request
import urllib.error

STATE_URL = "http://127.0.0.1:8080/state"
TIMEOUT = 3.0


def quat_to_yaw_deg(w, x, y, z):
    """Extract yaw angle (degrees) from quaternion (w,x,y,z)."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.degrees(math.atan2(siny_cosp, cosy_cosp))


def assess_stability(z):
    """Assess robot stability from height."""
    if z > 0.20:
        return "stable (debout)"
    elif z > 0.10:
        return "instable (en chute)"
    else:
        return "au sol (tombe)"


def main():
    try:
        req = urllib.request.Request(STATE_URL)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"Erreur: impossible de se connecter au simulateur ({e.reason})", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)

    if not data or "pos" not in data:
        print("Erreur: aucune donnee du simulateur (simulation non demarree?)", file=sys.stderr)
        sys.exit(1)

    pos = data["pos"]
    quat = data["quat"]  # w, x, y, z
    jp = data["jp"]
    sim_time = data["t"]

    yaw = quat_to_yaw_deg(quat[0], quat[1], quat[2], quat[3])
    stability = assess_stability(pos[2])
    active_joints = sum(1 for p in jp if abs(p) > 0.01)

    print(
        f"Le robot est {stability}. "
        f"Position X={pos[0]:.2f}, Y={pos[1]:.2f}, Z={pos[2]:.3f}. "
        f"Orientation: yaw={yaw:.1f} deg. "
        f"{active_joints} joints actifs sur 12. "
        f"Simulation t={sim_time:.1f}s."
    )


if __name__ == "__main__":
    main()
