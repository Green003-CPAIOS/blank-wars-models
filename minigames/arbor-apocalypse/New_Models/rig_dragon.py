"""
Inferno Soar Dragon Rigging Script v2
=====================================
Uses actual mesh vertex analysis to place bones correctly.

Model orientation (from analysis):
- X: left/right (-0.95 to +0.95) - wings span
- Y: up/down (-0.24 to +0.23) - model is nearly flat (flying pose)
- Z: front/back (-0.60 to +0.60) - head at Z-, tail at Z+

IMPORTANT NOTE - Animation Name Mapping:
=========================================
Due to how vertex weights ended up being assigned in this model, the bone names
don't match the body parts they actually control:
- Head/Neck/Jaw bones → control the TAIL area visually
- Tail_1/2/3 bones → control the HEAD area visually

To compensate, the animation NAMES are swapped in the export:
- "FireBreath" animation → animates Tail bones → moves HEAD in the rendered model
- "TailSway" animation → animates Head/Jaw bones → moves TAIL in the rendered model

This means in your game code:
- Call "FireBreath" to trigger the head/jaw fire-breathing motion
- Call "TailSway" to trigger the tail swaying motion
- Call "WingFlap_Fast/Normal/Slow" for wing animations (these work normally)

DO NOT change the bone weight assignments without also updating the animation names!
"""

import bpy
import numpy as np
from mathutils import Vector
import math

# ============================================================================
# CONFIGURATION
# ============================================================================

INPUT_FILE = "/Users/gabrielgreenstein/blank-wars-models/minigames/arbor-apocalypse/New_Models/Meshy_AI_Inferno_Soar_0126020814_texture.glb"
OUTPUT_FILE = "/Users/gabrielgreenstein/blank-wars-models/minigames/arbor-apocalypse/New_Models/Inferno_Soar_Rigged.glb"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def clear_scene():
    """Remove all objects from scene"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.armatures:
        if block.users == 0:
            bpy.data.armatures.remove(block)


def analyze_mesh(mesh_obj):
    """Analyze mesh to find key body part positions"""
    mesh_data = mesh_obj.data
    world_matrix = mesh_obj.matrix_world
    
    # Get all vertex positions in world space
    coords = np.array([(world_matrix @ v.co)[:] for v in mesh_data.vertices])
    
    print(f"\n=== MESH ANALYSIS ===")
    print(f"Vertex count: {len(coords):,}")
    
    min_x, max_x = np.min(coords[:, 0]), np.max(coords[:, 0])
    min_y, max_y = np.min(coords[:, 1]), np.max(coords[:, 1])
    min_z, max_z = np.min(coords[:, 2]), np.max(coords[:, 2])
    
    print(f"X range: {min_x:.3f} to {max_x:.3f} (width: {max_x-min_x:.3f})")
    print(f"Y range: {min_y:.3f} to {max_y:.3f} (height: {max_y-min_y:.3f})")
    print(f"Z range: {min_z:.3f} to {max_z:.3f} (depth: {max_z-min_z:.3f})")
    
    # Detect body parts based on position
    # REVERSED LOGIC based on user feedback:
    #   Y = depth (front-back)
    #   HEAD is at MIN Y (approx -0.6)
    #   TAIL is at MAX Y (approx +0.6)
    
    # Wings: extreme X values
    left_wing = coords[coords[:, 0] < -0.5]
    right_wing = coords[coords[:, 0] > 0.5]
    
    # Wing root: where wings attach to body (X around ±0.2-0.4)
    left_wing_root = coords[(coords[:, 0] > -0.4) & (coords[:, 0] < -0.15) & (coords[:, 1] < -0.2)]
    right_wing_root = coords[(coords[:, 0] < 0.4) & (coords[:, 0] > 0.15) & (coords[:, 1] < -0.2)]
    
    # Head: FRONT of model = minimum Y (Reversed)
    head_verts = coords[coords[:, 1] < min_y + 0.2]
    
    # Tail: BACK of model = maximum Y (Reversed)
    tail_verts = coords[coords[:, 1] > max_y - 0.15]
    
    # Body center: middle Y area
    body_center = coords[(np.abs(coords[:, 0]) < 0.2) & 
                         (coords[:, 1] > min_y + 0.2) & 
                         (coords[:, 1] < max_y - 0.2)]
    
    def avg_pos(verts, name):
        if len(verts) == 0:
            return None
        avg = np.mean(verts, axis=0)
        print(f"  {name}: ({avg[0]:.3f}, {avg[1]:.3f}, {avg[2]:.3f}) - {len(verts)} verts")
        return avg
    
    print("\n=== DETECTED POSITIONS ===")
    positions = {
        'left_wing_tip': avg_pos(left_wing[left_wing[:, 0] == np.min(left_wing[:, 0])], "Left wing tip"),
        'left_wing_center': avg_pos(left_wing, "Left wing (avg)"),
        'right_wing_tip': avg_pos(right_wing[right_wing[:, 0] == np.max(right_wing[:, 0])], "Right wing tip"),
        'right_wing_center': avg_pos(right_wing, "Right wing (avg)"),
        'left_wing_root': avg_pos(left_wing_root, "Left wing root"),
        'right_wing_root': avg_pos(right_wing_root, "Right wing root"),
        'head': avg_pos(head_verts, "Head"),
        'head_front': np.array([0, np.mean(head_verts[:, 1]), min_z]) if len(head_verts) > 0 else None,
        'tail': avg_pos(tail_verts, "Tail"),
        'tail_tip': np.array([0, np.mean(tail_verts[:, 1]), max_z]) if len(tail_verts) > 0 else None,
        'body_center': avg_pos(body_center, "Body center"),
        'bounds': {
            'min': (min_x, min_y, min_z),
            'max': (max_x, max_y, max_z),
            'center': ((min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2)
        }
    }
    
    return coords, positions


def create_dragon_armature(positions):
    """Create armature with bones placed at detected positions"""
    
    # Calculate bone positions from detected mesh data
    head = positions['head']
    tail = positions['tail']
    body = positions['body_center']
    left_wing = positions['left_wing_center']
    right_wing = positions['right_wing_center']
    
    # For wings, use LEFT wing as reference and MIRROR for right (ensures symmetry)
    # Left wing extends in -X direction
    left_tip = positions['left_wing_tip'] if positions['left_wing_tip'] is not None else np.array([-0.95, left_wing[1], left_wing[2]])
    
    # Wing root should be near the body center
    left_wing_root = np.array([-0.15, left_wing[1], left_wing[2]])
    
    # Mirror for right wing (flip X)
    right_wing_root = np.array([0.15, left_wing[1], left_wing[2]])
    right_wing_center = np.array([-left_wing[0], left_wing[1], left_wing[2]])  # Mirror X
    right_tip = np.array([-left_tip[0], left_tip[1], left_tip[2]])  # Mirror X
    
    print(f"\n=== WING BONE POSITIONS (SYMMETRIC) ===")
    print(f"  Left wing root: {left_wing_root}")
    print(f"  Left wing center: {left_wing}")
    print(f"  Left wing tip: {left_tip}")
    print(f"  Right wing root: {right_wing_root}")
    print(f"  Right wing center: {right_wing_center}")
    print(f"  Right wing tip: {right_tip}")
    
    # Spine positions
    spine_start = body if body is not None else np.array([0, 0, 0])
    neck_pos = (spine_start + head) / 2 if head is not None else spine_start + np.array([0, -0.05, -0.2])
    
    # Tail positions - tail extends BACKWARD (+Y direction now)
    tail_base = spine_start + np.array([0, 0.15, 0])  # Start behind body center
    tail_mid = tail if tail is not None else tail_base + np.array([0, 0.2, 0])
    tail_tip_pos = positions['tail_tip'] if positions['tail_tip'] is not None else tail_mid + np.array([0, 0.15, 0])
    
    print("\n=== BONE CONFIGURATION ===")
    bone_config = {
        # Root and spine
        "Root": {"head": tuple(spine_start), "tail": tuple(spine_start + np.array([0, 0.05, 0])), "parent": None},
        "Spine": {"head": tuple(spine_start), "tail": tuple(neck_pos), "parent": "Root"},
        
        # Head chain (Extending -Y)
        "Neck": {"head": tuple(neck_pos), "tail": tuple(head) if head is not None else tuple(neck_pos + np.array([0, -0.02, -0.15])), "parent": "Spine"},
        "Head": {"head": tuple(head) if head is not None else tuple(neck_pos + np.array([0, -0.02, -0.15])), 
                 "tail": tuple(positions['head_front']) if positions['head_front'] is not None else tuple(head + np.array([0, -0.02, -0.1])), "parent": "Neck"},
        "Jaw": {"head": tuple(head + np.array([0, -0.02, 0.02])) if head is not None else (0, -0.05, -0.5),
                "tail": tuple(head + np.array([0, -0.04, -0.05])) if head is not None else (0, -0.07, -0.55), "parent": "Head"},
        
        # Left wing (3 segments) - bones point outward (-X)
        "Wing_L_Root": {"head": tuple(left_wing_root), "tail": tuple((left_wing_root + left_wing) / 2), "parent": "Spine"},
        "Wing_L_Mid": {"head": tuple((left_wing_root + left_wing) / 2), "tail": tuple(left_wing), "parent": "Wing_L_Root"},
        "Wing_L_Tip": {"head": tuple(left_wing), "tail": tuple(left_tip), "parent": "Wing_L_Mid"},
        
        # Right wing (3 segments) - MIRRORED from left
        "Wing_R_Root": {"head": tuple(right_wing_root), "tail": tuple((right_wing_root + right_wing_center) / 2), "parent": "Spine"},
        "Wing_R_Mid": {"head": tuple((right_wing_root + right_wing_center) / 2), "tail": tuple(right_wing_center), "parent": "Wing_R_Root"},
        "Wing_R_Tip": {"head": tuple(right_wing_center), "tail": tuple(right_tip), "parent": "Wing_R_Mid"},
        
        # Tail (3 segments) (Extending +Y)
        "Tail_1": {"head": tuple(tail_base), "tail": tuple(tail_mid), "parent": "Root"},
        "Tail_2": {"head": tuple(tail_mid), "tail": tuple((np.array(tail_mid) + np.array(tail_tip_pos)) / 2), "parent": "Tail_1"},
        "Tail_3": {"head": tuple((np.array(tail_mid) + np.array(tail_tip_pos)) / 2), "tail": tuple(tail_tip_pos), "parent": "Tail_2"},
    }
    
    for name, config in bone_config.items():
        print(f"  {name}: head={config['head']}")
    
    # Create armature
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "DragonArmature"
    armature_data = armature.data
    
    # Remove default bone
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.delete()
    
    edit_bones = armature_data.edit_bones
    
    # Create all bones
    for bone_name, config in bone_config.items():
        bone = edit_bones.new(bone_name)
        bone.head = config["head"]
        bone.tail = config["tail"]
    
    # Set up parenting
    for bone_name, config in bone_config.items():
        if config["parent"]:
            bone = edit_bones[bone_name]
            parent_bone = edit_bones[config["parent"]]
            bone.parent = parent_bone
            bone.use_connect = False
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature, bone_config


def assign_vertex_weights(mesh_obj, armature, bone_config, coords):
    """Assign vertex weights based on proximity to bones"""
    
    print("\n=== ASSIGNING WEIGHTS ===")
    
    # Parent mesh to armature
    mesh_obj.parent = armature
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = armature
    
    # Create vertex groups
    for bone_name in bone_config.keys():
        if bone_name not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=bone_name)
    
    # Define influence zones for each bone type
    # REVERSED for Head/Tail due to Y-axis flip
    bone_zones = {
        'Wing_L': {'x_range': (-1.0, -0.15), 'radius': 0.5, 'falloff': 2.0},
        'Wing_R': {'x_range': (0.15, 1.0), 'radius': 0.5, 'falloff': 2.0},
        'Head': {'y_range': (-0.7, -0.35), 'radius': 0.2, 'falloff': 2.0}, # Head at MIN Y
        'Neck': {'y_range': (-0.35, -0.15), 'radius': 0.15, 'falloff': 2.0},
        'Jaw': {'y_range': (-0.7, -0.4), 'radius': 0.1, 'falloff': 2.0},
        'Tail': {'y_range': (0.15, 0.7), 'radius': 0.15, 'falloff': 2.0}, # Tail at MAX Y
        'Spine': {'y_range': (-0.15, 0.15), 'x_range': (-0.2, 0.2), 'radius': 0.25, 'falloff': 2.0},
        'Root': {'default': True},
    }
    
    # Get bone centers
    bone_centers = {}
    for bone_name, config in bone_config.items():
        head = np.array(config['head'])
        tail = np.array(config['tail'])
        bone_centers[bone_name] = (head + tail) / 2
    
    weight_counts = {name: 0 for name in bone_config.keys()}
    
    for i, coord in enumerate(coords):
        weights = {}
        
        # Wing bones - based on X position
        if coord[0] < -0.15:  # Left wing area
            for bone_name in ['Wing_L_Tip', 'Wing_L_Mid', 'Wing_L_Root']:
                center = bone_centers[bone_name]
                dist = np.linalg.norm(coord - center)
                radius = 0.4 if 'Tip' in bone_name else (0.35 if 'Mid' in bone_name else 0.3)
                if dist < radius:
                    weight = (1 - (dist / radius)) ** 2
                    weights[bone_name] = weight
        
        elif coord[0] > 0.15:  # Right wing area
            for bone_name in ['Wing_R_Tip', 'Wing_R_Mid', 'Wing_R_Root']:
                center = bone_centers[bone_name]
                dist = np.linalg.norm(coord - center)
                radius = 0.4 if 'Tip' in bone_name else (0.35 if 'Mid' in bone_name else 0.3)
                if dist < radius:
                    weight = (1 - (dist / radius)) ** 2
                    weights[bone_name] = weight
        
        # Head/Neck/Jaw - FRONT of model (Y < -0.4) - REVERSED
        if coord[1] < -0.4 and abs(coord[0]) < 0.15:  # Front/head area
            center_head = bone_centers['Head']
            center_jaw = bone_centers['Jaw']
            
            dist_head = np.linalg.norm(coord - center_head)
            dist_jaw = np.linalg.norm(coord - center_jaw)
            
            # Jaw - lower part of head
            if coord[2] < 0.0 and dist_jaw < 0.2:
                weight = (1 - (dist_jaw / 0.2)) ** 2
                weights['Jaw'] = weight
            # Head - main head area
            elif dist_head < 0.2:
                weight = (1 - (dist_head / 0.2)) ** 2
                weights['Head'] = weight
        
        # Neck - between body and head
        elif coord[1] < -0.1 and coord[1] > -0.4 and abs(coord[0]) < 0.15:
            center_neck = bone_centers['Neck']
            dist_neck = np.linalg.norm(coord - center_neck)
            if dist_neck < 0.25:
                weight = (1 - (dist_neck / 0.25)) ** 2
                weights['Neck'] = weight
        
        # Tail - BACK of model (Y > 0.15) - REVERSED
        elif coord[1] > 0.15 and abs(coord[0]) < 0.1:
            center_t1 = bone_centers['Tail_1']
            center_t2 = bone_centers['Tail_2']
            center_t3 = bone_centers['Tail_3']
            
            dist_t1 = np.linalg.norm(coord - center_t1)
            dist_t2 = np.linalg.norm(coord - center_t2)
            dist_t3 = np.linalg.norm(coord - center_t3)
            
            # Assign to closest tail bone
            min_dist = min(dist_t1, dist_t2, dist_t3)
            radius = 0.25
            
            if min_dist < radius:
                if dist_t3 == min_dist:
                    weight = (1 - (dist_t3 / radius)) ** 2
                    weights['Tail_3'] = weight
                elif dist_t2 == min_dist:
                    weight = (1 - (dist_t2 / radius)) ** 2
                    weights['Tail_2'] = weight
                else:
                    weight = (1 - (dist_t1 / radius)) ** 2
                    weights['Tail_1'] = weight
        
        # Spine - central body
        if abs(coord[0]) < 0.15 and coord[1] > -0.15 and coord[1] < 0.15:
            center = bone_centers['Spine']
            dist = np.linalg.norm(coord - center)
            if dist < 0.25:
                weight = (1 - (dist / 0.25)) ** 2
                weights['Spine'] = weight
        
        # Normalize weights and assign
        if weights:
            total = sum(weights.values())
            for bone_name, weight in weights.items():
                normalized = weight / total
                if normalized > 0.01:
                    vg = mesh_obj.vertex_groups.get(bone_name)
                    if vg:
                        vg.add([i], normalized, 'REPLACE')
                        weight_counts[bone_name] += 1
        else:
            # Default to Root
            root_vg = mesh_obj.vertex_groups.get('Root')
            if root_vg:
                root_vg.add([i], 1.0, 'REPLACE')
                weight_counts['Root'] += 1
    
    print("Weight assignments:")
    for name, count in weight_counts.items():
        if count > 0:
            print(f"  {name}: {count:,} vertices")


def create_animations(armature):
    """Create all animations for the dragon using NLA strips for proper export"""
    
    print("\n=== CREATING ANIMATIONS ===")
    
    if not armature.animation_data:
        armature.animation_data_create()
    
    actions = []
    
    # Helper function - sets action and adds keyframe
    def create_action_keyframes(action_name, keyframe_data):
        """Create an action with keyframes and push to NLA"""
        action = bpy.data.actions.new(name=action_name)
        armature.animation_data.action = action
        
        for bone_name, frame, rotation, location in keyframe_data:
            pose_bone = armature.pose.bones.get(bone_name)
            if not pose_bone:
                print(f"    Warning: Bone '{bone_name}' not found")
                continue
            pose_bone.rotation_mode = 'XYZ'
            
            if rotation:
                pose_bone.rotation_euler = rotation
                pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)
            if location:
                pose_bone.location = location
                pose_bone.keyframe_insert(data_path="location", frame=frame)
        
        # Push action to NLA strip for proper export
        track = armature.animation_data.nla_tracks.new()
        track.name = action_name
        strip = track.strips.new(action_name, 1, action)
        strip.name = action_name
        
        # Clear active action so next one starts fresh
        armature.animation_data.action = None
        
        actions.append(action)
        return action
    
    # ===================
    # Wing Flap Animations
    # ===================
    for speed_name, cycle_frames in [("WingFlap_Fast", 15), ("WingFlap_Normal", 30), ("WingFlap_Slow", 60)]:
        half = cycle_frames // 2
        
        up_angle = math.radians(30)
        down_angle = math.radians(-25)
        tip_up = math.radians(40)
        tip_down = math.radians(-35)
        mid_up = math.radians(25)
        mid_down = math.radians(-20)
        
        keyframes = []
        for side in ['L', 'R']:
            # Wings up
            keyframes.append((f"Wing_{side}_Root", 1, (up_angle, 0, 0), None))
            keyframes.append((f"Wing_{side}_Mid", 1, (mid_up, 0, 0), None))
            keyframes.append((f"Wing_{side}_Tip", 1, (tip_up, 0, 0), None))
            # Wings down
            keyframes.append((f"Wing_{side}_Root", half, (down_angle, 0, 0), None))
            keyframes.append((f"Wing_{side}_Mid", half, (mid_down, 0, 0), None))
            keyframes.append((f"Wing_{side}_Tip", half, (tip_down, 0, 0), None))
            # Wings up (loop)
            keyframes.append((f"Wing_{side}_Root", cycle_frames, (up_angle, 0, 0), None))
            keyframes.append((f"Wing_{side}_Mid", cycle_frames, (mid_up, 0, 0), None))
            keyframes.append((f"Wing_{side}_Tip", cycle_frames, (tip_up, 0, 0), None))
        
        # Body bob
        keyframes.append(("Root", 1, None, (0, 0, 0.01)))
        keyframes.append(("Root", half, None, (0, 0, -0.01)))
        keyframes.append(("Root", cycle_frames, None, (0, 0, 0.01)))
        
        create_action_keyframes(speed_name, keyframes)
        print(f"  Created: {speed_name} ({cycle_frames} frames)")
    
    # ===================
    # Fire Breath Animation - Correctly targets Head/Neck/Jaw
    # ===================
    rear = math.radians(15) # Increased for visibility
    lunge = math.radians(-10) # Increased
    jaw_open = math.radians(30) # Increased
    
    fire_keyframes = [
        # Neutral
        ("Neck", 1, (0, 0, 0), None),
        ("Head", 1, (0, 0, 0), None),
        ("Jaw", 1, (0, 0, 0), None),
        # Rear back
        ("Neck", 15, (rear, 0, 0), None),
        ("Head", 15, (rear * 0.5, 0, 0), None),
        ("Jaw", 15, (jaw_open * 0.3, 0, 0), None),
        # Pause, mouth opening
        ("Neck", 25, (rear, 0, 0), None),
        ("Head", 25, (rear * 0.5, 0, 0), None),
        ("Jaw", 25, (jaw_open, 0, 0), None),
        # Lunge forward
        ("Neck", 35, (lunge, 0, 0), None),
        ("Head", 35, (lunge * 0.7, 0, 0), None),
        ("Jaw", 35, (jaw_open * 1.2, 0, 0), None),
        # Hold
        ("Neck", 60, (lunge * 0.8, 0, 0), None),
        ("Head", 60, (lunge * 0.6, 0, 0), None),
        ("Jaw", 60, (jaw_open, 0, 0), None),
        # Return to neutral
        ("Neck", 90, (0, 0, 0), None),
        ("Head", 90, (0, 0, 0), None),
        ("Jaw", 90, (0, 0, 0), None),
    ]
    # Correct Name: FireBreath
    create_action_keyframes("FireBreath", fire_keyframes)
    print(f"  Created: FireBreath (90 frames) - head/jaw animation")
    
    # ===================
    # Tail Sway Animation - Correctly targets Tail bones
    # ===================
    cycle = 60
    sway = math.radians(10) # Increased
    phase = cycle // 4
    
    tail_keyframes = []
    for i, tail_bone in enumerate(["Tail_1", "Tail_2", "Tail_3"]):
        amp = sway * (1 + i * 0.5)
        offset = i * phase
        
        tail_keyframes.append((tail_bone, 1 + offset, (0, 0, amp), None)) # Sway on Z axis (horizontal) or X (vertical)? Typically Z for side-to-side in Blender
        tail_keyframes.append((tail_bone, cycle // 4 + offset, (0, 0, 0), None))
        tail_keyframes.append((tail_bone, cycle // 2 + offset, (0, 0, -amp), None))
        tail_keyframes.append((tail_bone, 3 * cycle // 4 + offset, (0, 0, 0), None))
        tail_keyframes.append((tail_bone, cycle + offset, (0, 0, amp), None))
    
    # Correct Name: TailSway
    create_action_keyframes("TailSway", tail_keyframes)
    print(f"  Created: TailSway (60 frames) - tail animation")
    
    return actions


def export_model(filepath):
    """Export the rigged model to GLB"""
    print(f"\n=== EXPORTING ===")
    print(f"Output: {filepath}")
    
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_skins=True,
        export_all_influences=True,
        export_animations=True,
        export_nla_strips=True,  # Use NLA strips for proper multi-animation export
        export_lights=False,
        export_cameras=False
    )
    print("Export complete!")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 60)
    print("INFERNO SOAR DRAGON RIGGING v2")
    print("=" * 60)
    
    # 1. Clear scene
    print("\n[1] Clearing scene...")
    clear_scene()
    
    # 2. Import model
    print(f"\n[2] Importing: {INPUT_FILE}")
    bpy.ops.import_scene.gltf(filepath=INPUT_FILE)
    
    mesh_obj = next((o for o in bpy.context.scene.objects if o.type == 'MESH'), None)
    if not mesh_obj:
        print("ERROR: No mesh found!")
        return
    print(f"  Found mesh: {mesh_obj.name}")
    
    # 3. Analyze mesh
    print("\n[3] Analyzing mesh geometry...")
    coords, positions = analyze_mesh(mesh_obj)
    
    # 4. Create armature
    print("\n[4] Creating armature...")
    armature, bone_config = create_dragon_armature(positions)
    
    # 5. Assign weights
    print("\n[5] Assigning vertex weights...")
    assign_vertex_weights(mesh_obj, armature, bone_config, coords)
    
    # 6. Create animations
    print("\n[6] Creating animations...")
    actions = create_animations(armature)
    
    # 7. Export
    print("\n[7] Exporting...")
    export_model(OUTPUT_FILE)
    
    print("\n" + "=" * 60)
    print("RIGGING COMPLETE!")
    print("=" * 60)
    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Animations: {[a.name for a in actions]}")


if __name__ == "__main__":
    main()
