#!/usr/bin/env bash
# ============================================================
# RoboticProgramAI — Installation ROS2 Humble (aarch64)
# Cible : DGX Spark (GB10 Grace-Blackwell, Ubuntu 22.04 arm64)
# Isolation : /home/panda/robotics/
# ============================================================
set -euo pipefail

ROBOTICS_HOME="/home/panda/robotics"
ROS2_DIR="${ROBOTICS_HOME}/ros2"
LOG_FILE="${ROBOTICS_HOME}/logs/install_ros2_$(date +%Y%m%d_%H%M%S).log"

echo "=== RoboticProgramAI — Install ROS2 Humble aarch64 ===" | tee "$LOG_FILE"
echo "Date: $(date)" | tee -a "$LOG_FILE"
echo "Cible: ${ROBOTICS_HOME}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# --- Étape 1 : Prérequis système (minimal, via apt) ---
echo "[1/5] Installation des prérequis système..." | tee -a "$LOG_FILE"
sudo apt update 2>&1 | tee -a "$LOG_FILE"
sudo apt install -y \
    locales \
    software-properties-common \
    curl \
    gnupg \
    lsb-release \
    python3-pip \
    python3-venv \
    2>&1 | tee -a "$LOG_FILE"

# --- Étape 2 : Ajouter le repo ROS2 (si pas déjà fait) ---
echo "[2/5] Configuration du dépôt ROS2..." | tee -a "$LOG_FILE"
if [ ! -f /etc/apt/sources.list.d/ros2.list ]; then
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | \
        sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    sudo apt update 2>&1 | tee -a "$LOG_FILE"
    echo "  Dépôt ROS2 ajouté." | tee -a "$LOG_FILE"
else
    echo "  Dépôt ROS2 déjà configuré." | tee -a "$LOG_FILE"
fi

# --- Étape 3 : Installer ROS2 Humble (packages apt — aarch64 supporté) ---
echo "[3/5] Installation ROS2 Humble (ros-humble-desktop)..." | tee -a "$LOG_FILE"
sudo apt install -y \
    ros-humble-desktop \
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-rmw-cyclonedds-cpp \
    python3-colcon-common-extensions \
    python3-rosdep \
    2>&1 | tee -a "$LOG_FILE"

# --- Étape 4 : Environnement isolé dans /home/panda/robotics/ ---
echo "[4/5] Configuration environnement isolé..." | tee -a "$LOG_FILE"
mkdir -p "${ROS2_DIR}/colcon_ws/src"

# Créer le script d'activation local
cat > "${ROS2_DIR}/activate.sh" << 'ACTIVATE_EOF'
#!/usr/bin/env bash
# Source ceci pour activer l'environnement ROS2 RoboticProgramAI
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0

# FastDDS config pour multi-machine (UDP)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASTDDS_XML="${SCRIPT_DIR}/../ros2/config/fastdds.xml"
if [ -f "$FASTDDS_XML" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_XML"
    echo "[ROS2] FastDDS XML chargé: $FASTDDS_XML"
fi

# Workspace local
if [ -f "${SCRIPT_DIR}/colcon_ws/install/local_setup.bash" ]; then
    source "${SCRIPT_DIR}/colcon_ws/install/local_setup.bash"
    echo "[ROS2] Workspace local chargé."
fi

echo "[ROS2] Environnement RoboticProgramAI activé (Humble, FastDDS, Domain 0)"
ACTIVATE_EOF
chmod +x "${ROS2_DIR}/activate.sh"

# Copier la config FastDDS du projet
mkdir -p "${ROBOTICS_HOME}/ros2/config"
if [ -f "${ROBOTICS_HOME}/ros/config/fastdds.xml" ]; then
    cp "${ROBOTICS_HOME}/ros/config/fastdds.xml" "${ROBOTICS_HOME}/ros2/config/"
    echo "  FastDDS config copiée." | tee -a "$LOG_FILE"
fi

# --- Étape 5 : Initialiser rosdep ---
echo "[5/5] Initialisation rosdep..." | tee -a "$LOG_FILE"
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init 2>&1 | tee -a "$LOG_FILE" || true
fi
rosdep update 2>&1 | tee -a "$LOG_FILE"

# --- Vérification ---
echo "" | tee -a "$LOG_FILE"
echo "=== VÉRIFICATION ===" | tee -a "$LOG_FILE"
source /opt/ros/humble/setup.bash
ros2 --version 2>&1 | tee -a "$LOG_FILE"
echo "Architecture: $(dpkg --print-architecture)" | tee -a "$LOG_FILE"
echo "RMW disponibles:" | tee -a "$LOG_FILE"
ros2 doctor --report 2>&1 | grep -i "middleware" | tee -a "$LOG_FILE" || true

echo "" | tee -a "$LOG_FILE"
echo "=== ROS2 Humble installé avec succès ===" | tee -a "$LOG_FILE"
echo "Pour activer : source ${ROS2_DIR}/activate.sh" | tee -a "$LOG_FILE"
echo "Log complet : ${LOG_FILE}" | tee -a "$LOG_FILE"
