#!/usr/bin/env python3
"""Send a movement command to the robot and report the result.

Sends cmd_vel via UDP directly to the simulation, waits for the
specified duration, then stops and reports the final position.

Usage:
    python3 mono_robot_move.py <vx> <vy> <duration>

Examples:
    python3 mono_robot_move.py 0.5 0.0 2.0    # Forward 0.5 m/s for 2s
    python3 mono_robot_move.py 0.0 0.3 1.0    # Strafe left 0.3 m/s for 1s
"""
import sys
import time
import struct
import socket
import json
import urllib.request
import urllib.error

CMD_PORT = 9871
CMD_FMT = "!3d"
STATE_URL = "http://127.0.0.1:8080/state"
TIMEOUT = 3.0
SEND_HZ = 25


def get_state():
    """Fetch current robot state from web viewer."""
    try:
        req = urllib.request.Request(STATE_URL)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def send_cmd_vel(sock, vx, vy, wz=0.0):
    """Send a cmd_vel packet via UDP."""
    data = struct.pack(CMD_FMT, vx, vy, wz)
    sock.sendto(data, ("127.0.0.1", CMD_PORT))


def main():
    if len(sys.argv) != 4:
        print("Usage: mono_robot_move.py <vx> <vy> <duration>", file=sys.stderr)
        sys.exit(1)

    try:
        vx = float(sys.argv[1])
        vy = float(sys.argv[2])
        duration = float(sys.argv[3])
    except ValueError:
        print("Erreur: les arguments doivent etre des nombres (vx vy duration)", file=sys.stderr)
        sys.exit(1)

    if duration <= 0 or duration > 30:
        print("Erreur: duration doit etre entre 0 et 30 secondes", file=sys.stderr)
        sys.exit(1)

    # Check sim is running
    state_before = get_state()
    if not state_before or "pos" not in state_before:
        print("Erreur: impossible de lire l'etat du simulateur", file=sys.stderr)
        sys.exit(1)

    pos_before = state_before["pos"]

    # Create UDP socket for sending cmd_vel
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Send cmd_vel at SEND_HZ for the specified duration
    interval = 1.0 / SEND_HZ
    elapsed = 0.0
    while elapsed < duration:
        send_cmd_vel(sock, vx, vy)
        time.sleep(interval)
        elapsed += interval

    # Stop
    send_cmd_vel(sock, 0.0, 0.0)
    sock.close()

    # Wait briefly for state to settle
    time.sleep(0.2)

    # Read final state
    state_after = get_state()
    if not state_after or "pos" not in state_after:
        print("Erreur: impossible de lire l'etat final", file=sys.stderr)
        sys.exit(1)

    pos_after = state_after["pos"]
    dx = pos_after[0] - pos_before[0]
    dy = pos_after[1] - pos_before[1]
    dist = (dx**2 + dy**2) ** 0.5

    print(
        f"Mouvement termine. "
        f"Duree: {duration:.1f}s. "
        f"Commande: vx={vx:.2f}, vy={vy:.2f}. "
        f"Deplacement: {dist:.3f}m. "
        f"Position finale: X={pos_after[0]:.2f}, Y={pos_after[1]:.2f}, Z={pos_after[2]:.3f}."
    )


if __name__ == "__main__":
    main()
