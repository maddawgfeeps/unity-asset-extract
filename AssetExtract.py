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
parser = argparse.ArgumentParser(description="Extract Unity assets from ASTC bundles and unpacked __data")
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
# Core extraction helpers
# ------------------------------------------------------------
def save_image(obj, asset_path: str, folder: str, out_root: Path):
    try:
        data = obj.read()
        filename = Path(asset_path).name.upper()
        out_path = out_root / folder / filename
        out_path = out_path.with_suffix(".png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data.image.save(str(out_path))
        log(f"> Writing {obj.type.name} to: {Fore.WHITE}{out_path}{Style.RESET_ALL}", Fore.GREEN, debug_only=True)
    except Exception as e:
        log(f"> Error writing {obj.type.name} {asset_path}: {e}", Fore.RED, debug_only=True)

def save_textasset(obj, asset_path: str, out_root: Path):
    try:
        data = obj.read()
        filename = Path(asset_path).name.upper()
        out_path = out_root / "TextAsset" / filename
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

def extract_from_env(env, name_hint: str, out_root: Path):
    """name_hint: lowercase string like 'metadata' or 'resources' from file/folder name"""
    extract_resources = "resources" in name_hint
    extract_metadata = "metadata" in name_hint

    if extract_resources or not (extract_resources or extract_metadata):
        for asset_path, obj in env.container.items():
            if obj.type.name == "Texture2D":
                save_image(obj, asset_path, "Texture2D", out_root)
            elif obj.type.name == "Sprite":
                save_image(obj, asset_path, "Sprite", out_root)

    if extract_metadata or not (extract_resources or extract_metadata):
        for asset_path, obj in env.container.items():
            if obj.type.name == "TextAsset":
                save_textasset(obj, asset_path, out_root)

    if not (extract_resources or extract_metadata):
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                if obj.serialized_type and obj.serialized_type.nodes:
                    tree = obj.read_typetree()
                    name = tree.get('m_Name', f"MONO_{obj.path_id}")
                    out_path = out_root / "MonoBehaviour" / f"{name}.json"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with out_path.open('w', encoding='utf-8') as f:
                        json.dump(tree, f, ensure_ascii=False, indent=4)
                    log(f"> Writing MonoBehaviour to: {Fore.WHITE}{out_path}{Style.RESET_ALL}", Fore.GREEN, debug_only=True)
                else:
                    log(f"> Skipping MonoBehaviour {obj.path_id}: no typetree", Fore.RED, debug_only=True)
            except Exception as e:
                log(f"> Error processing MonoBehaviour {obj.path_id}: {e}", Fore.RED, debug_only=True)


# ------------------------------------------------------------
# Phase 1: Extract ASTC bundles
# ------------------------------------------------------------
def extract_astc_bundles(src: Path, dst: Path):
    log("> Phase 1: Extracting ASTC bundle files", Fore.CYAN)
    count = 0
    failed = 0
    start = time.perf_counter()

    for root, _, files in os.walk(src):
        for file_name in files:
            if "ASTC" not in file_name:
                continue

            count += 1
            file_path = Path(root) / file_name
            log(f"> Processing bundle: {Fore.WHITE}{file_name}{Style.RESET_ALL}", Fore.YELLOW, debug_only=True)

            try:
                env = UnityPy.load(str(file_path))
                extract_from_env(env, file_name.lower(), dst)
            except Exception as e:
                failed += 1
                log(f"> Failed bundle {file_name}: {e}", Fore.RED, debug_only=True)

    elapsed = time.perf_counter() - start
    log(f"> Phase 1 Complete: {count} bundle(s), {failed} failed ({elapsed:.2f}s)", Fore.BLUE)
    return count


# ------------------------------------------------------------
# Phase 2: Extract from __data files inside ASTC folders
# ------------------------------------------------------------
def extract_data_files(root_dir: Path):
    log("> Phase 2: Extracting from __data files (recursive)", Fore.CYAN)
    count = 0
    failed = 0
    start = time.perf_counter()

    astc_folders = [p for p in root_dir.rglob("*") if p.is_dir() and "ASTC" in p.name]
    if not astc_folders:
        log("> No ASTC folders found for __data extraction.", Fore.YELLOW)
        return 0

    for folder in astc_folders:
        data_files = list(folder.rglob("__data"))
        for data_file in data_files:
            count += 1
            rel = data_file.relative_to(root_dir)
            log(f"> Found __data: {Fore.WHITE}{rel}{Style.RESET_ALL}", Fore.YELLOW, debug_only=True)

            try:
                env = UnityPy.load(str(data_file))
                # Use closest ASTC folder name for filtering
                astc_parent = next(p for p in data_file.parents if "ASTC" in p.name)
                extract_from_env(env, astc_parent.name.lower(), root_dir)
            except Exception as e:
                failed += 1
                log(f"> Failed __data {rel}: {e}", Fore.RED, debug_only=True)

    elapsed = time.perf_counter() - start
    log(f"> Phase 2 Complete: {count} __data file(s), {failed} failed ({elapsed:.2f}s)", Fore.BLUE)
    return count


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    total_start = time.perf_counter()

    bundle_count = extract_astc_bundles(source_in, dest_out)
    log("")  # blank line

    data_count = extract_data_files(dest_out)

    total_time = time.perf_counter() - total_start
    summary = f"> All done! {bundle_count} bundle(s) + {data_count} __data file(s) in {total_time:.2f}s"
    log(summary, Fore.MAGENTA)