import os
import json
import struct
import math

TARGET_DIR = "."
REPORT_FILE = "inventory_report.md"

def parse_glb_json(file_path):
    """
    Extracts the JSON chunk from a GLB file.
    """
    try:
        with open(file_path, 'rb') as f:
            # Header
            magic = f.read(4)
            if magic != b'glTF':
                return None # Not a GLB
            version = struct.unpack('<I', f.read(4))[0]
            length = struct.unpack('<I', f.read(4))[0]
            
            # Chunk 0 (JSON)
            chunk_len = struct.unpack('<I', f.read(4))[0]
            chunk_type = f.read(4)
            if chunk_type != b'JSON':
                return None
            
            json_data = f.read(chunk_len)
            return json.loads(json_data.decode('utf-8'))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def analyze_model(file_path, gltf_data):
    """
    Analyzes the glTF JSON data to extract stats.
    """
    stats = {
        "Animations": [],
        "Bones": 0,
        "Meshes": 0,
        "Vertices": 0
    }
    
    # 1. Animations
    if "animations" in gltf_data:
        for anim in gltf_data["animations"]:
            name = anim.get("name", "Unnamed")
            duration = 0.0
            
            # Find max duration from samplers input
            if "samplers" in anim:
                for sampler in anim["samplers"]:
                    input_accessor_idx = sampler["input"]
                    # Get accessor data to find min/max (GLTF stores min/max in accessor)
                    if "accessors" in gltf_data and input_accessor_idx < len(gltf_data["accessors"]):
                        acc = gltf_data["accessors"][input_accessor_idx]
                        if "max" in acc and acc["max"]:
                            duration = max(duration, acc["max"][0])
            
            stats["Animations"].append(f"{name} ({duration:.2f}s)")
            
    # 2. Bones (Joints)
    if "skins" in gltf_data:
        for skin in gltf_data["skins"]:
            if "joints" in skin:
                stats["Bones"] += len(skin["joints"])
                
    # 3. Meshes & Vertices
    if "meshes" in gltf_data:
        stats["Meshes"] = len(gltf_data["meshes"])
        for mesh in gltf_data["meshes"]:
            for prim in mesh.get("primitives", []):
                if "attributes" in prim and "POSITION" in prim["attributes"]:
                    pos_idx = prim["attributes"]["POSITION"]
                    if "accessors" in gltf_data and pos_idx < len(gltf_data["accessors"]):
                         acc = gltf_data["accessors"][pos_idx]
                         stats["Vertices"] += acc.get("count", 0)

    return stats

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
         return f"{size_bytes / (1024 * 1024):.1f} MB"

def main():
    report_lines = []
    report_lines.append("# 3D Model Inventory Report")
    report_lines.append(f"Generated Audit of: `{os.path.abspath(TARGET_DIR)}`")
    report_lines.append("")
    
    # Table Header
    report_lines.append("| Model File | Size | Animations | Bones | Meshes | Vertices |")
    report_lines.append("|---|---|---|---|---|---|")
    
    files = []
    for root, dirs, filenames in os.walk(TARGET_DIR):
        for f in filenames:
            if f.lower().endswith('.glb'):
                files.append(os.path.join(root, f))
    files.sort()
    
    for file_path in files:
        filename = os.path.basename(file_path)
        # Rel path for clarity
        rel_path = os.path.relpath(file_path, TARGET_DIR)
        size = os.path.getsize(file_path)
        
        json_data = parse_glb_json(file_path)
        if json_data:
            stats = analyze_model(file_path, json_data)
            
            anim_str = "<br>".join(stats["Animations"]) if stats["Animations"] else "None"
            bones_str = str(stats["Bones"])
            meshes_str = str(stats["Meshes"])
            verts_str = f"{stats['Vertices']:,}"
            size_str = format_size(size)
            
            report_lines.append(f"| **{rel_path}** | {size_str} | {anim_str} | {bones_str} | {meshes_str} | {verts_str} |")
        else:
             report_lines.append(f"| **{rel_path}** | {format_size(size)} | *Error Parsing* | - | - | - |")
             
    # Write Report
    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(report_lines))
    
    print(f"Report generated: {REPORT_FILE}")
    print("\n".join(report_lines))

if __name__ == "__main__":
    main()
