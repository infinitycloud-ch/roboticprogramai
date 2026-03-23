#!/usr/bin/env bash
# =============================================================================
# ROS2 Jazzy Jalisco - Installation sur DGX Spark (Ubuntu 24.04 aarch64)
# Target: /home/panda/robotics/ros2/
# =============================================================================
set -euo pipefail

echo "=== ROS2 Jazzy Installation (Ubuntu 24.04 aarch64) ==="
echo ""

ROS2_BASE="/home/panda/robotics/ros2"
mkdir -p "${ROS2_BASE}"

# --- Step 1: Add ROS2 apt repository ---
echo "[1/5] Configuration du dépôt ROS2..."
sudo apt update && sudo apt install -y software-properties-common curl

# Clé GPG ROS2
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

# Dépôt apt ROS2 pour Noble (24.04)
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update

# --- Step 2: Install ROS2 Jazzy ---
echo "[2/5] Installation ROS2 Jazzy desktop..."
sudo apt install -y ros-jazzy-desktop

# --- Step 3: Install FastDDS (rmw_fastrtps_cpp) ---
echo "[3/5] Installation FastDDS RMW..."
sudo apt install -y ros-jazzy-rmw-fastrtps-cpp

# --- Step 4: Install dev tools ---
echo "[4/5] Installation outils de développement ROS2..."
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-argcomplete \
  ros-jazzy-tf2-tools \
  ros-jazzy-rqt*

# Init rosdep si pas déjà fait
if [ ! -d /etc/ros/rosdep/sources.list.d ] || [ -z "$(ls -A /etc/ros/rosdep/sources.list.d 2>/dev/null)" ]; then
  sudo rosdep init
fi
rosdep update

# --- Step 5: Créer env.sh pour sourcer facilement ---
echo "[5/5] Configuration environnement..."
cat > "${ROS2_BASE}/env.sh" << 'ENVEOF'
#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0

# FastDDS multi-machine config (si le fichier existe)
FASTDDS_CFG="$(dirname "$0")/../robotics_env/ros/config/fastdds.xml"
if [ -f "${FASTDDS_CFG}" ]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_CFG}"
fi

echo "ROS2 Jazzy activé (FastDDS, Domain ID: ${ROS_DOMAIN_ID})"
ENVEOF
chmod +x "${ROS2_BASE}/env.sh"

echo ""
echo "=== Installation ROS2 Jazzy terminée ==="
echo ""
echo "Pour activer ROS2 :"
echo "  source ${ROS2_BASE}/env.sh"
echo ""
echo "Vérification :"
echo "  ros2 --version"
echo "  ros2 topic list"
