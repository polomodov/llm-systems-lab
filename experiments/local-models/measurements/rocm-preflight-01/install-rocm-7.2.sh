#!/usr/bin/env bash
# Install ROCm 7.2 user-space stack on Ubuntu 24.04 for gfx1151.
#
# Purpose: enable rocminfo for the next LAB02 (Ryzen AI Max+ 395 hardware
# passport) and downstream LAB04/LAB06/LAB07.
#
# Why this script:
# - repo.radeon.com/rocm/apt/7.2 noble is already wired in
#   /etc/apt/sources.list.d/rocm.list; the GPG key is in
#   /etc/apt/keyrings/rocm.gpg. No DKMS, no kernel rebuild, no display driver
#   changes.
# - Default apt pinning prefers Ubuntu's rocminfo 5.7.1 over ROCm's
#   1.0.0.70200 because the former has a higher upstream version string. We
#   add a preferences file with Pin: origin "repo.radeon.com" priority 1001
#   so that the ROCm 7.2 packages win for any ROCm namespaced package. The
#   origin value MUST be quoted; without quotes APT silently ignores the pin.
#   The file name MUST end in .pref; without it APT silently ignores the file.
# - "user-space" here means: amdgpu-core meta + ROCm userspace + HIP runtime,
#   no new systemd units, no kernel module changes. Reboot is not required.
# - After install, /opt/rocm-7.2.0/bin/ holds the actual binaries; this
#   script also creates /usr/local/bin symlinks and /etc/profile.d/rocm-7.2.sh
#   so rocminfo is on PATH for everyone.
# - If you already ran an earlier draft of this script that landed the wrong
#   rocminfo, run ./fix-rocminfo-pin.sh instead.
#
# Usage:
#   sudo ./install-rocm-7.2.sh minimal     # rocminfo + hipconfig (for LAB02)
#   sudo ./install-rocm-7.2.sh full        # full rocm-hip-runtime (for LAB04/06)
#   sudo ./install-rocm-7.2.sh status      # just check what is installed
#
# Dry-run check (no root needed):
#   apt-get -s install -o Dir::Etc::Preferences=./rocm-7.2-preferences \
#     rocm-hip-runtime

set -euo pipefail

MODE="${1:-minimal}"

PREFERENCES_SRC="$(dirname "$0")/rocm-7.2-preferences"
# IMPORTANT: filename must end in .pref on Ubuntu 24.04's apt. Without the
# extension, APT silently ignores the file:
#   N: Ignoring file 'rocm-7.2-user-space' in directory '/etc/apt/preferences.d/'
#   as it has an invalid filename extension
PREFERENCES_DST="/etc/apt/preferences.d/rocm-7.2-user-space.pref"
PREFERENCES_LEGACY="/etc/apt/preferences.d/rocm-7.2-user-space"
PROFILED="/etc/profile.d/rocm-7.2.sh"
ROCMPREFIX="/opt/rocm-7.2.0"

LAB_DIR="$(dirname "$0")"
RAW_DIR="$LAB_DIR/raw"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "This script needs sudo. Re-run with: sudo $0 $MODE" >&2
  exit 1
fi

create_symlinks() {
  for tool in rocminfo rocm_agent_enumerator rdhc; do
    src="$ROCMPREFIX/bin/$tool"
    dst="/usr/local/bin/$tool"
    if [[ -x "$src" ]]; then
      ln -sf "$src" "$dst"
      echo "    $dst -> $src"
    fi
  done
}

write_profiled() {
  cat > "$PROFILED" <<EOF
# ROCm 7.2 user-space environment (managed by rocm-preflight-01/install-rocm-7.2.sh)
export PATH="$ROCMPREFIX/bin:\$PATH"
export LD_LIBRARY_PATH="$ROCMPREFIX/lib:\${LD_LIBRARY_PATH:-}"
EOF
  chmod 0644 "$PROFILED"
}

capture_evidence() {
  local out="$RAW_DIR/rocm-tools-after.txt"
  dpkg -l | awk '/(rocm|hip|hsa|amdgpu|comgr|rocprofiler)/ {print $2, $3}' \
    > "$RAW_DIR/dpkg-after.txt" || true
  {
    echo "--- /etc/apt/preferences.d/ listing"
    ls -la /etc/apt/preferences.d/ 2>&1
    echo
    echo "--- /usr/local/bin symlinks"
    ls -la /usr/local/bin/rocminfo /usr/local/bin/rocm_agent_enumerator /usr/local/bin/rdhc 2>&1
    echo
    echo "--- which rocminfo"
    command -v rocminfo 2>&1
    echo
    echo "--- rocminfo (head 40)"
    rocminfo 2>&1 | head -40 || true
    echo
    echo "--- rocm_agent_enumerator"
    rocm_agent_enumerator 2>&1
    echo
    echo "--- hipconfig status"
    if command -v hipconfig >/dev/null; then
      hipconfig --version 2>&1
    else
      echo "(hipconfig absent in ROCm 7.2 user-mode apt packages)"
    fi
  } > "$out"
  cat > "$RAW_DIR/hipconfig-unavailable-reason.txt" <<'EOF'
hipconfig is not part of ROCm 7.2 user-mode apt packages.
A grep across https://repo.radeon.com/rocm/apt/7.2/dists/noble/main/binary-amd64/Packages.gz
returned no Package: hipconfig line. The utility has been removed from the
ROCm 7.x distribution; HIP version information can be obtained instead from
the runtime libraries (/opt/rocm-7.2.0/lib/libamdhip64.so.7.2.70200) or
hipcc --version after installing rocm-hip-runtime-dev. For LAB02 this field
is filled as unavailable with this reason.
EOF
}

case "$MODE" in
  minimal)
    PACKAGES=(rocminfo=1.0.0.70200-43~24.04 hsa-rocr hip-runtime-amd)
    ;;
  full)
    PACKAGES=(rocm-hip-runtime)
    ;;
  status)
    echo "--- dpkg rocm-related:"
    dpkg -l | awk '/(rocm|hip|hsa|amdgpu|comgr|rocprofiler)/ {print $2, $3}' || true
    echo "--- /opt:"
    ls /opt 2>/dev/null || true
    echo "--- rocminfo:"
    command -v rocminfo && rocminfo 2>&1 | head -10 || echo "absent"
    echo "--- hipconfig:"
    command -v hipconfig && hipconfig --version || echo "absent"
    exit 0
    ;;
  *)
    echo "Unknown mode: $MODE (use minimal | full | status)" >&2
    exit 2
    ;;
esac

echo "[1/5] Installing ROCm apt preferences to $PREFERENCES_DST"
if [[ -e "$PREFERENCES_LEGACY" ]]; then
  echo "    Removing legacy file with invalid extension: $PREFERENCES_LEGACY"
  rm -f "$PREFERENCES_LEGACY"
fi
install -m 0644 "$PREFERENCES_SRC" "$PREFERENCES_DST"

echo "[2/5] apt-get update"
apt-get update

echo "[3/5] apt-get install ${PACKAGES[*]}"
DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"

echo "[4/5] Creating /usr/local/bin symlinks and /etc/profile.d/rocm-7.2.sh"
create_symlinks
write_profiled

echo "[5/5] Capturing after-install evidence to $RAW_DIR"
capture_evidence

echo
echo "Done. Run 'sudo $0 status' any time to inspect."
