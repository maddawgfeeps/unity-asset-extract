#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import importlib
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------
# Package handling
# ------------------------------------------------------------
required_packages = {
    "UnityPy": "UnityPy",
    "colorama": "colorama",
}

def install_if_missing(packages: dict[str, str]) -> None:
    for pip_name, import_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"Installing missing package: {pip_name}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

install_if_missing(required_packages)

import UnityPy
from colorama import init, Fore, Style

init(autoreset=True)


# ------------------------------------------------------------
# Logging helper
# ------------------------------------------------------------
def log(msg: str, colour: str = Fore.CYAN, debug_only: bool = False) -> None:
    if debug_only and not DEBUG:
        return
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{colour}[{timestamp}] {msg}{Style.RESET_ALL}")


# ------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="Extract Unity assets from ASTC files")
parser.add_argument("-file", nargs=2, metavar=('INPUT_DIR', 'OUTPUT_DIR'),
                    help="Custom input and output directories")
parser.add_argument("--debug", action="store_true",
                    help="Enable verbose per-file logging")
args = parser.parse_args()

DEBUG = args.debug

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
source_in = Path.cwd()
dest_out = Path.cwd()

if args.file:
    source_in = Path(args.file[0]).resolve()
    dest_out = Path(args.file[1]).resolve()
    log("> Using custom paths:", Fore.CYAN)
else:
    log("> Using current directory:", Fore.CYAN)

log(f"> InputSet : {Fore.WHITE}{source_in}{Style.RESET_ALL}", Fore.CYAN)
log(f"> OutputSet: {Fore.WHITE}{dest_out}{Style.RESET_ALL}", Fore.CYAN)


# ------------------------------------------------------------
# Core extraction
# ------------------------------------------------------------
def unpack_all_assets(src: Path, dst: Path) -> None:
    log("> Extracting Resources", Fore.CYAN)
    astc_count = 0
    failed_files = 0
    start_time = time.perf_counter()

    for root, _, files in os.walk(src):
        for file_name in files:
            if "ASTC" not in file_name:
                continue

            astc_count += 1
            file_path = Path(root) / file_name
            log(f"> Processing File : {Fore.WHITE}{file_name}{Style.RESET_ALL}", Fore.YELLOW, debug_only=True)

            try:
                env = UnityPy.load(str(file_path))

                file_lower = file_name.lower()
                extract_resources = "resources" in file_lower
                extract_metadata = "metadata" in file_lower

                # ------------------------------------------------------------------
                # Helper: Write image (Texture2D / Sprite)
                # ------------------------------------------------------------------
                def save_image(obj, asset_path: str, folder: str):
                    try:
                        data = obj.read()
                        filename = Path(asset_path).name.upper()
                        out_path = dst / folder / filename
                        out_path = out_path.with_suffix(".png")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        data.image.save(str(out_path))
                        log(f"> Writing {obj.type.name} to: {Fore.WHITE}{out_path}{Style.RESET_ALL}", Fore.GREEN, debug_only=True)
                    except Exception as e:
                        log(f"> Error writing {obj.type.name} {asset_path}: {e}", Fore.RED, debug_only=True)

                # ------------------------------------------------------------------
                # Helper: Write TextAsset
                # ------------------------------------------------------------------
                def save_textasset(obj, asset_path: str):
                    try:
                        data = obj.read()
                        filename = Path(asset_path).name.upper()
                        out_path = dst / "TextAsset" / filename
                        out_path = out_path.with_suffix(".txt")
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        script = str(data.m_Script)
                        try:
                            out_path.write_text(script, encoding='utf-8', errors='surrogatepass')
                        except UnicodeEncodeError:
                            log(f"> Unicode error, retrying with replace", Fore.RED, debug_only=True)
                            out_path.write_text(script, encoding='utf-8', errors='replace')
                        log(f"> Writing TextAsset to: {Fore.WHITE}{out_path}{Style.RESET_ALL}", Fore.GREEN, debug_only=True)
                    except Exception as e:
                        log(f"> Error writing TextAsset {asset_path}: {e}", Fore.RED, debug_only=True)

                # ------------------------------------------------------------------
                # Extract Texture2D & Sprite
                # ------------------------------------------------------------------
                if extract_resources or not (extract_resources or extract_metadata):
                    for asset_path, obj in env.container.items():
                        if obj.type.name == "Texture2D":
                            save_image(obj, asset_path, "Texture2D")
                        elif obj.type.name == "Sprite":
                            save_image(obj, asset_path, "Sprite")

                # ------------------------------------------------------------------
                # Extract TextAsset (metadata)
                # ------------------------------------------------------------------
                if extract_metadata or not (extract_resources or extract_metadata):
                    for asset_path, obj in env.container.items():
                        if obj.type.name == "TextAsset":
                            save_textasset(obj, asset_path)

                # ------------------------------------------------------------------
                # Extract MonoBehaviour (fallback)
                # ------------------------------------------------------------------
                if not (extract_resources or extract_metadata):
                    for obj in env.objects:
                        if obj.type.name != "MonoBehaviour":
                            continue
                        try:
                            if obj.serialized_type and obj.serialized_type.nodes:
                                tree = obj.read_typetree()
                                name = tree.get('m_Name', f"MONO_{obj.path_id}")
                                out_path = dst / "MonoBehaviour" / f"{name}.json"
                                out_path.parent.mkdir(parents=True, exist_ok=True)
                                with out_path.open('w', encoding='utf-8') as f:
                                    json.dump(tree, f, ensure_ascii=False, indent=4)
                                log(f"> Writing MonoBehaviour to: {Fore.WHITE}{out_path}{Style.RESET_ALL}", Fore.GREEN, debug_only=True)
                            else:
                                log(f"> Skipping MonoBehaviour {obj.path_id}: no typetree", Fore.RED, debug_only=True)
                        except Exception as e:
                            log(f"> Error processing MonoBehaviour {obj.path_id}: {e}", Fore.RED, debug_only=True)

            except Exception as e:
                failed_files += 1
                log(f"> Error processing file {file_name}: {e}", Fore.RED, debug_only=True)

    elapsed = time.perf_counter() - start_time
    if astc_count == 0:
        log("> No ASTC files found in the input directory", Fore.BLUE)
    else:
        log(f"> Finished processing {astc_count} ASTC file(s). "
            f"{failed_files} file(s) failed. "
            f"Time taken: {elapsed:.2f}s", Fore.BLUE)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    unpack_all_assets(source_in, dest_out)