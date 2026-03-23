#!/usr/bin/env bash
# ============================================================
# RoboticProgramAI — Installation Isaac Sim 5.1.0 (aarch64)
# Cible : DGX Spark (GB10 Grace-Blackwell, Ubuntu 24.04 aarch64)
# Isolation : /home/panda/robotics/isaac_sim/
# Prérequis : ROS2 Jazzy installé (install_ros2_jazzy.sh)
# ============================================================
set -euo pipefail

ROBOTICS_HOME="/home/panda/robotics"
ISAAC_DIR="${ROBOTICS_HOME}/isaac_sim"
VENV_DIR="${ROBOTICS_HOME}/envs/isaac"
LOG_FILE="${ROBOTICS_HOME}/logs/install_isaac_$(date +%Y%m%d_%H%M%S).log"

echo "=== RoboticProgramAI — Install Isaac Sim 5.1.0 aarch64 ===" | tee "$LOG_FILE"
echo "Date: $(date)" | tee -a "$LOG_FILE"
echo "Architecture: $(uname -m)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# --- Vérification architecture ---
if [ "$(uname -m)" != "aarch64" ]; then
    echo "ERREUR: Ce script cible aarch64. Détecté: $(uname -m)" | tee -a "$LOG_FILE"
    exit 1
fi

# --- Étape 1 : Créer le venv Python isolé ---
echo "[1/6] Création du venv Python isolé..." | tee -a "$LOG_FILE"
mkdir -p "${ISAAC_DIR}" "${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"

# --- Étape 2 : Installer Isaac Sim 5.1.0 via pip (aarch64) ---
echo "[2/6] Installation Isaac Sim 5.1.0 via pip (aarch64)..." | tee -a "$LOG_FILE"
echo "  NOTE: L'installation peut prendre 10-20 minutes." | tee -a "$LOG_FILE"
# [all] inclut isaacsim.ros2.bridge + toutes les extensions
# Fix aarch64 OpenMP avant install
export LD_PRELOAD="${LD_PRELOAD:-}:/lib/aarch64-linux-gnu/libgomp.so.1"
pip install "isaacsim[all]==5.1.0" \
    --extra-index-url https://pypi.nvidia.com \
    2>&1 | tee -a "$LOG_FILE"

# --- Étape 3 : Installer Isaac Lab 2.3.x ---
echo "[3/6] Installation Isaac Lab (branche compatible 5.1.0)..." | tee -a "$LOG_FILE"
cd "${ISAAC_DIR}"
if [ ! -d "IsaacLab" ]; then
    git clone https://github.com/isaac-sim/IsaacLab.git 2>&1 | tee -a "$LOG_FILE"
    cd IsaacLab
    # Chercher le tag 2.3.x le plus récent, sinon main
    LATEST_TAG=$(git tag -l 'v2.3*' --sort=-v:refname | head -1)
    if [ -n "$LATEST_TAG" ]; then
        echo "  Checkout tag: ${LATEST_TAG}" | tee -a "$LOG_FILE"
        git checkout "$LATEST_TAG" 2>&1 | tee -a "$LOG_FILE"
    else
        echo "  Pas de tag v2.3.x trouvé, utilisation de main" | tee -a "$LOG_FILE"
    fi
else
    cd IsaacLab
    echo "  IsaacLab déjà cloné." | tee -a "$LOG_FILE"
fi
pip install -e . 2>&1 | tee -a "$LOG_FILE" || {
    echo "  WARN: pip install -e . échoué, tentative alternative..." | tee -a "$LOG_FILE"
    pip install isaaclab 2>&1 | tee -a "$LOG_FILE" || true
}
cd "${ROBOTICS_HOME}"

# --- Étape 4 : Cloner l'URDF Go2 officiel ---
echo "[4/6] Clone URDF Go2 (officiel Unitree)..." | tee -a "$LOG_FILE"
URDF_DIR="${ROBOTICS_HOME}/sim/urdf/go2_description"
if [ ! -d "${URDF_DIR}/.git" ]; then
    git clone https://github.com/Unitree-Go2-Robot/go2_description.git "${URDF_DIR}" 2>&1 | tee -a "$LOG_FILE"
else
    echo "  URDF Go2 déjà cloné." | tee -a "$LOG_FILE"
fi

# --- Étape 5 : Cloner isaac-go2-ros2 (référence) ---
echo "[5/6] Clone isaac-go2-ros2 (référence architecture)..." | tee -a "$LOG_FILE"
REF_DIR="${ISAAC_DIR}/references/isaac-go2-ros2"
mkdir -p "${ISAAC_DIR}/references"
if [ ! -d "${REF_DIR}/.git" ]; then
    git clone https://github.com/Zhefan-Xu/isaac-go2-ros2.git "${REF_DIR}" 2>&1 | tee -a "$LOG_FILE"
else
    echo "  Référence déjà clonée." | tee -a "$LOG_FILE"
fi

# --- Étape 6 : Script d'activation ---
echo "[6/6] Création du script d'activation..." | tee -a "$LOG_FILE"
cat > "${ISAAC_DIR}/activate.sh" << 'ACTIVATE_EOF'
#!/usr/bin/env bash
# Activer l'environnement Isaac Sim 5.1.0 RoboticProgramAI
ROBOTICS_HOME="/home/panda/robotics"
source "${ROBOTICS_HOME}/envs/isaac/bin/activate"
source /opt/ros/jazzy/setup.bash 2>/dev/null || echo "[WARN] ROS2 Jazzy non activé"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

export ISAACSIM_ROS2_BRIDGE=isaacsim.ros2.bridge
export ISAAC_SIM_PATH="$(python3 -c 'import isaacsim; print(isaacsim.__path__[0])' 2>/dev/null || echo 'NOT_FOUND')"

echo "[Isaac Sim 5.1.0] Environnement activé."
echo "[Isaac Sim 5.1.0] Path: ${ISAAC_SIM_PATH}"
echo "[Isaac Sim 5.1.0] Bridge: isaacsim.ros2.bridge"
ACTIVATE_EOF
chmod +x "${ISAAC_DIR}/activate.sh"

# --- Vérification ---
echo "" | tee -a "$LOG_FILE"
echo "=== VÉRIFICATION ===" | tee -a "$LOG_FILE"
python3 -c "import isaacsim; print(f'Isaac Sim: {isaacsim.__version__}')" 2>&1 | tee -a "$LOG_FILE" || echo "WARN: import isaacsim échoué" | tee -a "$LOG_FILE"
ls "${URDF_DIR}/urdf/" 2>&1 | tee -a "$LOG_FILE" || true
echo "" | tee -a "$LOG_FILE"
echo "=== Isaac Sim 5.1.0 + Isaac Lab installés ===" | tee -a "$LOG_FILE"
echo "Pour activer : source ${ISAAC_DIR}/activate.sh" | tee -a "$LOG_FILE"
echo "Log : ${LOG_FILE}" | tee -a "$LOG_FILE"
