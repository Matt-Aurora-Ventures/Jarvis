"""Generate an ed25519 SSH key pair for VPS access."""
import subprocess
import sys
import os

key_path = os.path.join(os.environ["USERPROFILE"], ".ssh", "id_ed25519_vps")

if os.path.exists(key_path):
    print(f"Key already exists at {key_path}")
    with open(key_path + ".pub") as f:
        print(f"\nPublic key:\n{f.read()}")
    sys.exit(0)

# Ensure .ssh dir exists
os.makedirs(os.path.dirname(key_path), exist_ok=True)

result = subprocess.run(
    ["ssh-keygen", "-t", "ed25519", "-C", "jarvis-vps", "-f", key_path, "-P", ""],
    capture_output=True, text=True
)

if result.returncode == 0:
    print("Key generated successfully!")
    with open(key_path + ".pub") as f:
        pub = f.read()
    print(f"\nPublic key:\n{pub}")
else:
    print(f"Error: {result.stderr}")
    sys.exit(1)
