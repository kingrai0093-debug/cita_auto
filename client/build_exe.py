#!/usr/bin/env python3
"""Cross-platform automated builder for cita_auto executable."""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(HERE)
    print("=" * 68)
    print("     CITA AUTO - Automated Standalone Executable Builder")
    print("=" * 68)

    # 1. Check requirements
    print("[1/3] Ensuring required packages are installed...")
    req_file = os.path.join(HERE, "requirements.txt")
    cmd_install = [sys.executable, "-m", "pip", "install", "-r", req_file, "pyinstaller"]
    ret = subprocess.call(cmd_install)
    if ret != 0:
        print("[ERROR] Failed to install dependencies. Exiting.")
        return 1

    # 2. Run PyInstaller
    spec_file = os.path.join(HERE, "cita_auto.spec")
    print("\n[2/3] Compiling standalone executable with PyInstaller...")
    cmd_build = [sys.executable, "-m", "PyInstaller", "--clean", spec_file]
    ret_build = subprocess.call(cmd_build)
    if ret_build != 0:
        print("[ERROR] Compilation failed. Exiting.")
        return 1

    # 3. Deploy to client folder
    exe_name = "cita_auto.exe" if sys.platform == "win32" else "cita_auto"
    built_path = os.path.join(HERE, "dist", exe_name)
    target_path = os.path.join(HERE, exe_name)

    print(f"\n[3/3] Deploying {exe_name} into {HERE}...")
    if os.path.exists(built_path):
        shutil.copy2(built_path, target_path)
        print("=" * 68)
        print(f"[SUCCESS] Standalone executable ready at: {target_path}")
        print(f"File size: {os.path.getsize(target_path):,} bytes")
        print("You can now run it directly or via start.bat!")
        print("=" * 68)
        return 0
    else:
        print(f"[ERROR] {built_path} was not found after compilation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
