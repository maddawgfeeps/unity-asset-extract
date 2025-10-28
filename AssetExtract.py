import os, sys, subprocess, importlib
import json
import argparse


# Mapping of pip install name -> import module name
required_packages = {
    "UnityPy": "UnityPy",
    "colorama": "colorama"
}

def install_if_missing(packages):
    for pip_name, import_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print("Installing missing package: ", pip_name)
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

install_if_missing(required_packages)

import UnityPy
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init(autoreset=True)

def main():
    parser = argparse.ArgumentParser(description="Extract Unity assets from ASTC files")
    parser.add_argument("-file", nargs=2, metavar=('INPUT_DIR', 'OUTPUT_DIR'), 
                       help="Specify custom input and output directories")
    
    args = parser.parse_args()
    
    # Default to current working directory for both input and output
    source_in = os.getcwd()
    dest_out = os.getcwd()
    
    # Override with -file argument if provided
    if args.file:
        source_in = os.path.abspath(args.file[0])
        dest_out = os.path.abspath(args.file[1])
        print(f"{Fore.CYAN}> Using custom paths:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}> InputSet : {Fore.WHITE}{source_in}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}> OutputSet: {Fore.WHITE}{dest_out}{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}> Using current directory:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}> InputSet : {Fore.WHITE}{source_in}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}> OutputSet: {Fore.WHITE}{dest_out}{Style.RESET_ALL}")
    
    unpack_all_assets(source_in, dest_out)

def unpack_all_assets(source_folder: str, destination_folder: str):
    print(f"{Fore.CYAN}> Extracting Resource{Style.RESET_ALL}")
    astc_count = 0
    failed_files = 0
    
    # Iterate over all files in source folder
    for root, dirs, files in os.walk(source_folder):
        print(f"{Fore.CYAN}> Walking through : {Fore.WHITE}{source_folder}{Style.RESET_ALL}")
        for file_name in files:
            # Only process files containing "ASTC" in the filename
            if "ASTC" not in file_name:
                continue
                
            astc_count += 1
            print(f"{Fore.YELLOW}> Processing File : {Fore.WHITE}{file_name}{Style.RESET_ALL}")
            # Generate file_path
            file_path = os.path.join(root, file_name)
            
            try:
                # Load that file via UnityPy.load
                env = UnityPy.load(file_path)

                # Determine which assets to extract based on filename
                file_name_lower = file_name.lower()
                extract_resources = "resources" in file_name_lower
                extract_metadata = "metadata" in file_name_lower

                # Handle Texture2D (only for "resources" or no specific filter)
                if extract_resources or not (extract_resources or extract_metadata):
                    for path, obj in env.container.items():
                        if obj.type.name == "Texture2D":
                            try:
                                data = obj.read()
                                # Get the filename and convert to uppercase
                                filename = os.path.basename(path).upper()
                                # Save to Texture2D folder
                                dest = os.path.join(destination_folder, "Texture2D", filename)
                                # Ensure the directory exists
                                os.makedirs(os.path.dirname(dest), exist_ok=True)
                                # Correct extension
                                dest, ext = os.path.splitext(dest)
                                dest = dest + ".png"
                                print(f"{Fore.GREEN}> Writing Texture2D to: {Fore.WHITE}{dest}{Style.RESET_ALL}")
                                data.image.save(dest)
                            except Exception as e:
                                print(f"{Fore.RED}> Error writing Texture2D {path}: {e}{Style.RESET_ALL}")

                # Handle Sprite (only for "resources" or no specific filter)
                if extract_resources or not (extract_resources or extract_metadata):
                    for path, obj in env.container.items():
                        if obj.type.name == "Sprite":
                            try:
                                data = obj.read()
                                # Get the filename and convert to uppercase
                                filename = os.path.basename(path).upper()
                                # Save to Sprite folder
                                dest = os.path.join(destination_folder, "Sprite", filename)
                                # Ensure the directory exists
                                os.makedirs(os.path.dirname(dest), exist_ok=True)
                                # Correct extension
                                dest, ext = os.path.splitext(dest)
                                dest = dest + ".png"
                                print(f"{Fore.GREEN}> Writing Sprite to: {Fore.WHITE}{dest}{Style.RESET_ALL}")
                                data.image.save(dest)
                            except Exception as e:
                                print(f"{Fore.RED}> Error writing Sprite {path}: {e}{Style.RESET_ALL}")

                # Handle TextAsset (only for "metadata" or no specific filter)
                if extract_metadata or not (extract_resources or extract_metadata):
                    for path, obj in env.container.items():
                        if obj.type.name == "TextAsset":
                            try:
                                data = obj.read()
                                # Get the filename and convert to uppercase
                                filename = os.path.basename(path).upper()
                                # Save to TextAsset folder
                                dest = os.path.join(destination_folder, "TextAsset", filename)
                                # Ensure the directory exists
                                os.makedirs(os.path.dirname(dest), exist_ok=True)
                                # Correct extension
                                dest, ext = os.path.splitext(dest)
                                dest = dest + ".txt"
                                print(f"{Fore.GREEN}> Writing TextAsset to: {Fore.WHITE}{dest}{Style.RESET_ALL}")
                                with open(dest, 'w', encoding='utf-8', errors='surrogatepass') as f:
                                    f.write(str(data.m_Script))
                            except UnicodeEncodeError as e:
                                print(f"{Fore.RED}> Unicode error writing TextAsset {path}: {e}. Retrying with replacement characters{Style.RESET_ALL}")
                                try:
                                    with open(dest, 'w', encoding='utf-8', errors='replace') as f:
                                        f.write(str(data.m_Script))
                                    print(f"{Fore.GREEN}> Successfully wrote TextAsset with replacements to: {Fore.WHITE}{dest}{Style.RESET_ALL}")
                                except Exception as e2:
                                    print(f"{Fore.RED}> Failed to write TextAsset {path} with replacements: {e2}{Style.RESET_ALL}")
                            except Exception as e:
                                print(f"{Fore.RED}> Error writing TextAsset {path}: {e}{Style.RESET_ALL}")

                # Handle MonoBehaviour (only if no specific filter)
                if not (extract_resources or extract_metadata):
                    for obj in env.objects:
                        if obj.type.name == "MonoBehaviour":
                            try:
                                if obj.serialized_type.nodes:
                                    tree = obj.read_typetree()
                                    # Use original case for m_Name instead of uppercase
                                    filename = tree.get('m_Name', f"MONO_{obj.path_id}")
                                    dest = os.path.join(destination_folder, "MonoBehaviour", f"{filename}.json")
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    print(f"{Fore.GREEN}> Writing MonoBehaviour to: {Fore.WHITE}{dest}{Style.RESET_ALL}")
                                    with open(dest, 'w', encoding='utf-8') as f:
                                        json.dump(tree, f, ensure_ascii=False, indent=4)
                                else:
                                    print(f"{Fore.RED}> Skipping MonoBehaviour {obj.path_id}: no typetree nodes{Style.RESET_ALL}")
                            except Exception as e:
                                print(f"{Fore.RED}> Error processing MonoBehaviour {obj.path_id}: {e}{Style.RESET_ALL}")

            except Exception as e:
                failed_files += 1
                print(f"{Fore.RED}> Error processing file {file_name}: {e}{Style.RESET_ALL}")

    if astc_count == 0:
        print(f"{Fore.BLUE}> No ASTC files found in the input directory{Style.RESET_ALL}")
    else:
        print(f"{Fore.BLUE}> Finished processing {astc_count} ASTC file(s). {failed_files} file(s) failed.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()