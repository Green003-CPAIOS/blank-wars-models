
import struct
import json
import math
import os

# CONFIGURATION
INPUT_FILE = "Meshy_AI_Roaring_Dinosaur_0126033222_texture.glb"
OUTPUT_FILE = "Rhino_Dino_Rigged_v11.glb"

# ... (Bones list remains the same) ...
BONES = [
    {"name": "Root",   "pos": [0.0, 0.45, -0.1],   "parent": None},
    {"name": "Spine",  "pos": [0.0, 0.50, 0.2],    "parent": "Root"},
    {"name": "Neck",   "pos": [0.0, 0.60, 0.5],    "parent": "Spine"},
    {"name": "Head",   "pos": [0.0, 0.70, 0.8],    "parent": "Neck"},
    {"name": "Jaw",    "pos": [0.0, 0.60, 0.85],   "parent": "Head"},
    {"name": "Tail_1", "pos": [0.0, 0.45, -0.4],   "parent": "Root"},
    {"name": "Tail_2", "pos": [0.0, 0.40, -0.7],   "parent": "Tail_1"},
    {"name": "Tail_3", "pos": [0.0, 0.35, -1.0],   "parent": "Tail_2"},
    {"name": "Hip_L",  "pos": [0.10, 0.40, -0.1],  "parent": "Root"},
    {"name": "Leg_L",  "pos": [0.15, 0.25, -0.1],  "parent": "Hip_L"},
    {"name": "Foot_L", "pos": [0.15, 0.05, 0.0],   "parent": "Leg_L"},
    {"name": "Hip_R",  "pos": [-0.10, 0.40, -0.1], "parent": "Root"},
    {"name": "Leg_R",  "pos": [-0.15, 0.25, -0.1], "parent": "Hip_R"},
    {"name": "Foot_R", "pos": [-0.15, 0.05, 0.0],  "parent": "Leg_R"},
]

def create_accessors(bin_data_offset, vertex_count, joints_count):
    pass

def main():
    print(f"Rigging {INPUT_FILE}...")
    
    with open(INPUT_FILE, 'rb') as f:
        glb_bytes = f.read()

    # Parse Header
    magic, version, length = struct.unpack('<4sII', glb_bytes[:12])
    
    # Parse Chunk 0 (JSON)
    chunk0_len, chunk0_type = struct.unpack('<II', glb_bytes[12:20])
    json_bytes = glb_bytes[20:20+chunk0_len]
    gltf = json.loads(json_bytes)
    
    # Parse Chunk 1 (BIN)
    chunk1_offset = 20 + chunk0_len
    chunk1_len, chunk1_type = struct.unpack('<II', glb_bytes[chunk1_offset:chunk1_offset+8])
    bin_bytes = glb_bytes[chunk1_offset+8 : chunk1_offset+8+chunk1_len]

    # 1. Identify Mesh Primitives
    mesh = gltf['meshes'][0]
    primitive = mesh['primitives'][0]
    pos_accessor_idx = primitive['attributes']['POSITION']
    pos_accessor = gltf['accessors'][pos_accessor_idx]
    vertex_count = pos_accessor['count']
    
    print(f"Vertex Count: {vertex_count}")

    # Read POSITION data
    bv_idx = pos_accessor['bufferView']
    bv = gltf['bufferViews'][bv_idx]
    bv_offset = bv.get('byteOffset', 0)
    stride = 12 
    if 'byteStride' in bv: stride = bv['byteStride']
        
    raw_pos = bin_bytes[bv_offset : bv_offset + vertex_count * stride]
    
    positions = []
    for i in range(vertex_count):
        x, y, z = struct.unpack('<fff', raw_pos[i*stride : i*stride+12])
        positions.append((x, y, z))

    # 2. Calculate Weights & Joints
    joint_data = [] 
    weight_data = []

    for i, (x, y, z) in enumerate(positions):
        # v11: GRADIENT WEIGHTS (Soft Falloff using Penalty Multipliers)
        # Instead of strict "allowed_groups", we calculate a penalty for every bone.
        # effective_dist = dist * penalty
        
        penalties = {} # bone_name -> multiplier (default 1.0)
        
        # HEAD ZONE
        if z > 0.3:
            # Boost Head/Neck/Jaw (1.0)
            # DAMPEN Spine/Root (2.0 - weak pull)
            penalties["Spine"] = 2.0
            penalties["Root"] = 3.0
            # BLOCK others
            default_penalty = 10.0
            valid_bones = ["Head", "Neck", "Jaw", "Spine", "Root"]
        
        # TAIL ZONE
        elif z < -0.2:
            # Boost Tail (1.0)
            # DAMPEN Root/Hips (1.5 - blend zone)
            penalties["Root"] = 1.5
            penalties["Hip_L"] = 1.5
            penalties["Hip_R"] = 1.5
             # BLOCK others
            default_penalty = 10.0
            valid_bones = ["Tail_1", "Tail_2", "Tail_3", "Root", "Hip_L", "Hip_R"]

        # LEGS ZONE
        elif y < 0.4 and abs(x) > 0.05:
            # Determine Side
            is_left = (x > 0)
            
            # Primary: Side Hips/Legs (1.0)
            prefix = "Hip_L" if is_left else "Hip_R" # Just marker
            
            # Dampen Root/Spine (Prevent torso pulling down)
            penalties["Root"] = 2.0
            penalties["Spine"] = 4.0
            
            # BLOCK Opposite Side
            default_penalty = 10.0 # Block everything else
            
            if is_left:
                valid_bones = ["Hip_L", "Leg_L", "Foot_L", "Root", "Spine"]
            else:
                valid_bones = ["Hip_R", "Leg_R", "Foot_R", "Root", "Spine"]

        # BODY ZONE (Default)
        else:
            default_penalty = 10.0
            # Primary: Root/Spine (1.0)
            # Blend Neighbors (1.5)
            # Weak Hips (Prevent twisting) -> 2.5
            # Very Weak Legs -> 4.0
            
            penalties["Root"] = 1.0
            penalties["Spine"] = 1.0
            penalties["Neck"] = 1.2
            penalties["Tail_1"] = 1.2
            
            penalties["Hip_L"] = 2.5
            penalties["Hip_R"] = 2.5
            penalties["Leg_L"] = 4.0
            penalties["Leg_R"] = 4.0
            
            valid_bones = ["Root", "Spine", "Neck", "Tail_1", "Hip_L", "Hip_R", "Leg_L", "Leg_R"]

        dists = [] 
        for b_idx, bone in enumerate(BONES):
            name = bone['name']
            
            # If not in our "valid list" for this zone, heavily penalize or skip
            # Using 10.0 penalty effectively skips it unless it's literally on top of the vertex
            if 'valid_bones' in locals() and name not in valid_bones:
                penalty = 10.0
            else:
                penalty = penalties.get(name, 1.0)

            bx, by, bz = bone['pos']
            d = math.sqrt((x-bx)**2 + (y-by)**2 + (z-bz)**2)
            
            # --- JAW BOOST (Preserved) ---
            if name == 'Jaw':
                if z > 0.6 and y < 0.65: 
                     d *= 0.1 # Real 10x boost (distance becomes tiny)
            
            # APPLY PENALTY
            effective_dist = d * penalty
            dists.append((effective_dist, b_idx))
        
        if not dists:
             for b_idx, bone in enumerate(BONES):
                bx, by, bz = bone['pos']
                d = math.sqrt((x-bx)**2 + (y-by)**2 + (z-bz)**2)
                dists.append((d, b_idx))
        
        dists.sort(key=lambda k: k[0])
        
        # Take top 4
        top4 = dists[:4]
        
        # Normalize weights (Balanced Falloff: Power of 2)
        total_inv_dist = sum(1.0 / ((d[0] + 0.0001)**2) for d in top4)
        
        weights = []
        joints = []
        
        final_w_sum = 0
        for d, b_idx in top4:
            w = (1.0 / ((d + 0.0001)**2)) / total_inv_dist
            weights.append(w)
            joints.append(b_idx)
            final_w_sum += w
            
        # Pad to 4
        while len(weights) < 4:
            weights.append(0.0)
            joints.append(0)
            
        if final_w_sum > 0:
            weights = [w/final_w_sum for w in weights]
            
        weight_data.append(weights)
        joint_data.append(joints)

    # 3. Serialize New Data (JOINTS_0 and WEIGHTS_0)
    # JOINTS_0 needs unsigned short (5125) => 2 bytes * 4 = 8 bytes per vert
    # WEIGHTS_0 needs float (5126) => 4 bytes * 4 = 16 bytes per vert
    
    new_joints_bytes = bytearray()
    new_weights_bytes = bytearray()
    
    for j in joint_data:
        new_joints_bytes += struct.pack('<HHHH', *j)
    
    for w in weight_data:
        new_weights_bytes += struct.pack('<ffff', *w)

    # Padding to 4 bytes
    while len(new_joints_bytes) % 4 != 0: new_joints_bytes += b'\x00'
    while len(new_weights_bytes) % 4 != 0: new_weights_bytes += b'\x00'

    # 4. Append to BIN chunk
    start_offset = len(bin_bytes)
    
    bin_bytes += new_joints_bytes
    joints_offset = start_offset
    joints_len = len(new_joints_bytes)
    
    bin_bytes += new_weights_bytes
    weights_offset = start_offset + joints_len
    weights_len = len(new_weights_bytes)

    # 5. Update JSON: Add BufferViews
    # Current buffer index is 0
    
    # Joints BufferView
    gltf['bufferViews'].append({
        "buffer": 0,
        "byteOffset": joints_offset + chunk1_offset + 8 - 20 - chunk0_len, # Relative to bin start? No, relative to buffer start
        # Wait, buffer[0] usually points to the BIN chunk implicit uri
        # The 'byteOffset' in bufferView is relative to the start of the buffer.
        # In GLB, buffer[0] is the BIN chunk body.
        "byteOffset": joints_offset,
        "byteLength": joints_len,
        "target": 34963 # ARRAY_BUFFER?
    })
    joints_bv_idx = len(gltf['bufferViews']) - 1
    
    # Weights BufferView
    gltf['bufferViews'].append({
        "buffer": 0,
        "byteOffset": weights_offset,
        "byteLength": weights_len,
        "target": 34963
    })
    weights_bv_idx = len(gltf['bufferViews']) - 1
    
    # 6. Update JSON: Add Accessors
    
    # Joints Accessor (VEC4, UNSIGNED_SHORT)
    gltf['accessors'].append({
        "bufferView": joints_bv_idx,
        "componentType": 5123, # UNSIGNED_SHORT
        "count": vertex_count,
        "type": "VEC4"
    })
    joints_acc_idx = len(gltf['accessors']) - 1
    
    # Weights Accessor (VEC4, FLOAT)
    gltf['accessors'].append({
        "bufferView": weights_bv_idx,
        "componentType": 5126, # FLOAT
        "count": vertex_count,
        "type": "VEC4"
    })
    weights_acc_idx = len(gltf['accessors']) - 1
    
    # 7. Update JSON: Create Nodes (Bones)
    # We must add nodes for our bones, and a skin definition
    
    # Find scene root to attach our Root bone? 
    # Or just add to scenes[0].nodes?
    # Let's create the bone nodes
    bone_node_indices = []
    start_node_index = len(gltf['nodes'])
    
    for i, bone in enumerate(BONES):
        node = {
            "name": bone['name'],
            "translation": bone['pos'],
            "rotation": [0, 0, 0, 1], # Identity quaternion
            "children": []
        }
        gltf['nodes'].append(node)
        bone_node_indices.append(start_node_index + i)

    # Link Parents
    for i, bone in enumerate(BONES):
        if bone['parent']:
            parent_local_idx = next(k for k, b in enumerate(BONES) if b['name'] == bone['parent'])
            parent_global_idx = bone_node_indices[parent_local_idx]
            gltf['nodes'][parent_global_idx]['children'].append(bone_node_indices[i])
            
            # Important: Bone positions in GLTF nodes are LOCAL relative to parent
            # My BONES list has WORLD positions.
            # I must convert to LOCAL.
            p_pos = BONES[parent_local_idx]['pos']
            c_pos = bone['pos']
            local_pos = [c_pos[0]-p_pos[0], c_pos[1]-p_pos[1], c_pos[2]-p_pos[2]]
            gltf['nodes'][bone_node_indices[i]]['translation'] = local_pos
        else:
             # Root bone: translation is World pos (if attached to scene root)
             # But usually Skinned Meshes have a Root Node.
             pass
             
    # Add Root Bone to Scene
    scene_nodes = gltf['scenes'][gltf['scene']]['nodes']
    # scene_nodes.append(bone_node_indices[0]) 
    
    # We should encapsulate the mesh inside a node, or attach skeleton to it?
    # Existing mesh is likely in a node.
    mesh_node_idx = -1
    for idx, node in enumerate(gltf['nodes']):
        if 'mesh' in node and node['mesh'] == 0:
            mesh_node_idx = idx
            break
            
    if mesh_node_idx == -1:
        print("Error: Could not find node with mesh 0")
        return

    # Add Root Bone as SIBLING of Mesh? Or Child?
    # Usually:
    # Scene -> [MeshNode, RootBoneNode]
    # MeshNode -> skin: SkinID
    scene_nodes.append(bone_node_indices[0])

    # 8. Update JSON: Create Skin
    inverse_bind_matrices_bin = bytearray()
    # IBM = Inverse of World Matrix of bone at bind time.
    # Since my bones are defined in World Space and Rotation is Identity:
    # World Matrix = Translation Matrix(pos).
    # Inverse = Translation Matrix(-pos).
    
    for bone in BONES:
        x, y, z = bone['pos']
        # 4x4 Identity with translation -x, -y, -z in last column (col-major?)
        # GLTF is Column Major
        # 1 0 0 0
        # 0 1 0 0
        # 0 0 1 0
        # -x -y -z 1
        ibm = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            -x, -y, -z, 1.0
        ]
        for val in ibm:
            inverse_bind_matrices_bin += struct.pack('<f', val)
            
    # Append IBM to BIN
    while len(inverse_bind_matrices_bin) % 4 != 0: inverse_bind_matrices_bin += b'\x00'
    ibm_offset = len(bin_bytes) # Relative to start
    bin_bytes += inverse_bind_matrices_bin
    ibm_len = len(inverse_bind_matrices_bin)
    
    # IBM BufferView & Accessor
    gltf['bufferViews'].append({
        "buffer": 0,
        "byteOffset": ibm_offset,
        "byteLength": ibm_len,
        "target": None
    })
    ibm_bv_idx = len(gltf['bufferViews']) - 1
    
    gltf['accessors'].append({
        "bufferView": ibm_bv_idx,
        "componentType": 5126, # FLOAT
        "count": len(BONES),
        "type": "MAT4"
    })
    ibm_acc_idx = len(gltf['accessors']) - 1
    
    # Create Skin
    gltf['skins'] = [{
        "inverseBindMatrices": ibm_acc_idx,
        "joints": bone_node_indices,
        "skeleton": bone_node_indices[0] # Root
    }]
    skin_idx = 0
    
    # 9. Update Mesh Primitive attributes
    primitive['attributes']['JOINTS_0'] = joints_acc_idx
    primitive['attributes']['WEIGHTS_0'] = weights_acc_idx
    
    # 10. Link Skin to Mesh Node
    gltf['nodes'][mesh_node_idx]['skin'] = skin_idx

    # 11. Reconstruct GLB
    # Re-serialize JSON
    new_json_bytes = json.dumps(gltf).encode('utf-8')
    # Padding
    while len(new_json_bytes) % 4 != 0: new_json_bytes += b' '
    
    # Padding BIN
    while len(bin_bytes) % 4 != 0: bin_bytes += b'\x00'
    
    # Header
    total_len = 12 + 8 + len(new_json_bytes) + 8 + len(bin_bytes)
    header = struct.pack('<4sII', b'glTF', 2, total_len)
    
    chunk0_header = struct.pack('<II', len(new_json_bytes), 0x4E4F534A) # JSON
    chunk1_header = struct.pack('<II', len(bin_bytes), 0x004E4942) # BIN
    
    with open(OUTPUT_FILE, 'wb') as f:
        f.write(header)
        f.write(chunk0_header)
        f.write(new_json_bytes)
        f.write(chunk1_header)
        f.write(bin_bytes)
        
    print(f"Saved {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
