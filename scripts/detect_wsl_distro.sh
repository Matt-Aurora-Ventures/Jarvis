#!/bin/bash
# WSL Distribution Detection Script

echo "=== WSL Distribution Information ==="
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    echo "❌ Not running in WSL!"
    exit 1
fi

echo "✓ Running in WSL"
echo ""

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "Distribution: $NAME"
    echo "Version: $VERSION"
    echo "ID: $ID"
    echo "ID Like: $ID_LIKE"
    echo "Pretty Name: $PRETTY_NAME"
    echo "Version ID: $VERSION_ID"
    echo "Version Codename: $VERSION_CODENAME"
else
    echo "⚠️  Cannot detect distribution (no /etc/os-release)"
fi

echo ""

# Check kernel version
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo ""

# Check WSL version
if grep -qi "WSL2" /proc/version; then
    echo "WSL Version: 2"
elif grep -qi "Microsoft" /proc/version; then
    echo "WSL Version: 1"
fi

echo ""

# Check systemd support
if [ -d /run/systemd/system ]; then
    echo "✓ Systemd is enabled"
    echo "  Systemd version: $(systemd --version | head -1)"
else
    echo "❌ Systemd is NOT enabled"
    echo "  (Some features like auto-start services won't work)"
    echo ""
    echo "To enable systemd in WSL2, add to /etc/wsl.conf:"
    echo "[boot]"
    echo "systemd=true"
    echo ""
    echo "Then restart WSL: wsl --shutdown (from Windows)"
fi

echo ""

# Package manager detection
echo "Package Manager:"
if command -v apt &> /dev/null; then
    echo "  ✓ apt (Debian/Ubuntu)"
fi
if command -v yum &> /dev/null; then
    echo "  ✓ yum (RHEL/CentOS)"
fi
if command -v dnf &> /dev/null; then
    echo "  ✓ dnf (Fedora)"
fi
if command -v pacman &> /dev/null; then
    echo "  ✓ pacman (Arch)"
fi
if command -v zypper &> /dev/null; then
    echo "  ✓ zypper (openSUSE)"
fi

echo ""

# Memory and CPU info
echo "Resources:"
echo "  Total Memory: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  Available Memory: $(free -h | awk '/^Mem:/ {print $7}')"
echo "  CPU Cores: $(nproc)"

echo ""
echo "=== Detection Complete ==="
