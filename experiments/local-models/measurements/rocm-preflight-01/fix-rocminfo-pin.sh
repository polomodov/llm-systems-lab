#!/usr/bin/env bash
# Fix script: undo the wrong rocminfo/libhsa-runtime64-1/libhsakmt1 from
# Ubuntu noble/universe that snuck in on the first run because the apt pin
# was misconfigured (no quotes around origin, missing .pref extension).
#
# This script:
#   1. Rewrites /etc/apt/preferences.d/rocm-7.2-user-space.pref with the
#      correct Pin: origin "repo.radeon.com" syntax and .pref extension.
#   2. Removes the Ubuntu versions of rocminfo, libhsa-runtime64-1, libhsakmt1
#      that the first run pulled in.
#   3. apt-get update so the new pin takes effect.
#   4. Installs rocminfo=1.0.0.70200-43~24.04 from repo.radeon.com.
#   5. Creates /usr/local/bin symlinks so rocminfo etc. are in PATH without
#      requiring users to know about /opt/rocm-7.2.0/bin/.
#   6. Writes /etc/profile.d/rocm-7.2.sh for shell login paths.
#   7. Captures after-fix evidence.
#
# No DKMS, no kernel rebuild, no display driver changes. Reboot not required.

set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")" && pwd)"
RAW_DIR="$LAB_DIR/raw"
# IMPORTANT: filename must end in .pref on Ubuntu 24.04's apt. Without the
# extension, APT silently ignores the file:
#   N: Ignoring file 'rocm-7.2-user-space' in directory '/etc/apt/preferences.d/'
#   as it has an invalid filename extension
PREFERENCES_DST="/etc/apt/preferences.d/rocm-7.2-user-space.pref"
PREFERENCES_LEGACY="/etc/apt/preferences.d/rocm-7.2-user-space"
PROFILED="/etc/profile.d/rocm-7.2.sh"
ROCMPREFIX="/opt/rocm-7.2.0"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-run with: sudo $0" >&2
  exit 1
fi

echo "[1/7] Rewriting $PREFERENCES_DST with quoted origin (.pref extension)"
if [[ -e "$PREFERENCES_LEGACY" ]]; then
  echo "    Removing legacy file with invalid extension: $PREFERENCES_LEGACY"
  rm -f "$PREFERENCES_LEGACY"
fi
cat > "$PREFERENCES_DST" <<'EOF'
Package: *
Pin: origin "repo.radeon.com"
Pin-Priority: 1001
EOF
chmod 0644 "$PREFERENCES_DST"
cat "$PREFERENCES_DST"

echo "[2/7] Removing Ubuntu versions of rocminfo, libhsa-runtime64-1, libhsakmt1"
DEBIAN_FRONTEND=noninteractive apt-get remove -y \
  rocminfo libhsa-runtime64-1 libhsakmt1 || true
DEBIAN_FRONTEND=noninteractive apt-get autoremove -y || true

echo "[3/7] apt-get update"
apt-get update

echo "[4/7] apt-get install rocminfo=1.0.0.70200-43~24.04 from repo.radeon.com"
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  rocminfo=1.0.0.70200-43~24.04

echo "[5/7] Creating /usr/local/bin symlinks for ROCm 7.2 binaries"
for tool in rocminfo rocm_agent_enumerator rdhc; do
  src="$ROCMPREFIX/bin/$tool"
  dst="/usr/local/bin/$tool"
  if [[ -x "$src" ]]; then
    ln -sf "$src" "$dst"
    echo "    $dst -> $src"
  else
    echo "    (skip) $src not present"
  fi
done

echo "[6/7] Writing $PROFILED for PATH and LD_LIBRARY_PATH"
cat > "$PROFILED" <<EOF
# ROCm 7.2 user-space environment (managed by rocm-preflight-01/fix-rocminfo-pin.sh)
export PATH="$ROCMPREFIX/bin:\$PATH"
export LD_LIBRARY_PATH="$ROCMPREFIX/lib:\${LD_LIBRARY_PATH:-}"
EOF
chmod 0644 "$PROFILED"
cat "$PROFILED"

echo "[7/7] Capturing after-fix evidence to $RAW_DIR"
dpkg -l | awk '/(rocm|hip|hsa|amdgpu|comgr|rocprofiler)/ {print $2, $3}' \
  > "$RAW_DIR/dpkg-after-fix.txt" || true
{
  echo "--- apt-cache policy rocminfo (after fix)"
  apt-cache policy rocminfo 2>&1
  echo
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
    echo "(hipconfig absent in ROCm 7.2 — see raw/hipconfig-unavailable-reason.txt)"
  fi
} > "$RAW_DIR/rocm-tools-after-fix.txt"

cat > "$RAW_DIR/hipconfig-unavailable-reason.txt" <<'EOF'
hipconfig is not part of ROCm 7.2 user-mode apt packages.
A grep across https://repo.radeon.com/rocm/apt/7.2/dists/noble/main/binary-amd64/Packages.gz
returned no Package: hipconfig line. The utility has been removed from the
ROCm 7.x distribution; HIP version information can be obtained instead from
the runtime libraries (/opt/rocm-7.2.0/lib/libamdhip64.so.7.2.70200) or
hipcc --version after installing rocm-hip-runtime-dev. For LAB02 this field
is filled as unavailable with this reason.
EOF

echo
echo "Done. Quick check:"
echo "  rocminfo | head -5:"
rocminfo 2>&1 | head -5
