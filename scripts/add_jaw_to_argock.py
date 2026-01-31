import bpy
from mathutils import Vector
import math

INPUT = "/Users/gabrielgreenstein/blank-wars-models/Metal_Foldout_Chair_Models/Meshy_AI_argock_the_motivator_0131190216_texture.glb"
OUTPUT = "/Users/gabrielgreenstein/blank-wars-models/Metal_Foldout_Chair_Models/argock_metal_foldout_chair.glb"

print("[JAW] Starting Argock rigging...")

# 1. Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for block in bpy.data.meshes:
    if block.users == 0:
        bpy.data.meshes.remove(block)
for block in bpy.data.armatures:
    if block.users == 0:
        bpy.data.armatures.remove(block)

# 2. Import
print("[JAW] Importing original model...")
bpy.ops.import_scene.gltf(filepath=INPUT)

mesh_obj = next((o for o in bpy.context.scene.objects if o.type == 'MESH'), None)
if not mesh_obj:
    print("[JAW] ERROR: No mesh found!")
    exit(1)

mesh_data = mesh_obj.data
world_matrix = mesh_obj.matrix_world
verts = [world_matrix @ v.co for v in mesh_data.vertices]

zs = [v[2] for v in verts]
min_z = min(zs)
max_z = max(zs)
height = max_z - min_z
print(f"[JAW] Mesh: {len(verts):,} vertices")
print(f"[JAW] Bounds Z: {min_z:.4f} to {max_z:.4f} (height: {height:.4f})")

# PARAMETERS - Argock (orc trainer, seated in foldout chair)
# Model is centered at origin, Z range -1.0 to 1.0
# Mouth area at ~73% height based on geometry analysis
MOUTH_X = 0.02       # Slightly right of center (matches head center_x)
JAW_Z_CENTER = 0.46  # ~73% of height from bottom (-1.0 + 2.0 * 0.73)
MOUTH_Y = -0.07      # Front surface of face at mouth level

# Bone Z positions
JAW_Z = JAW_Z_CENTER - 0.02
UPPER_LIP_Z = JAW_Z_CENTER + 0.025
HEAD_TOP_Z = max_z - 0.15

# Radii scaled for 2-unit tall model
JAW_RADIUS = 0.12
UPPER_LIP_RADIUS = 0.12
FALLOFF_EXPONENT = 2.0

print(f"[JAW] Config: X={MOUTH_X:.3f}, Y={MOUTH_Y:.3f}")
print(f"[JAW] Lower Jaw Z={JAW_Z:.3f}, R={JAW_RADIUS}")
print(f"[JAW] Upper Lip Z={UPPER_LIP_Z:.3f}, R={UPPER_LIP_RADIUS}")

# 3. Create Armature
print("[JAW] Creating Armature...")
bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
armature = bpy.context.object
armature.name = "Armature"
armature_data = armature.data
armature_data.name = "Armature"

bpy.ops.armature.select_all(action='SELECT')
bpy.ops.armature.delete()

root_bone = armature_data.edit_bones.new("Root")
root_bone.head = (0, 0, 0)
root_bone.tail = (0, 0, 0.2)

head_bone = armature_data.edit_bones.new("Head")
head_bone.head = (MOUTH_X, MOUTH_Y - 0.1, JAW_Z_CENTER)
head_bone.tail = (MOUTH_X, MOUTH_Y - 0.1, HEAD_TOP_Z)
head_bone.parent = root_bone

head_top_bone = armature_data.edit_bones.new("HeadTop")
head_top_bone.head = (MOUTH_X, MOUTH_Y, HEAD_TOP_Z)
head_top_bone.tail = (MOUTH_X, MOUTH_Y, HEAD_TOP_Z + 0.1)
head_top_bone.parent = head_bone

jaw_bone = armature_data.edit_bones.new("Jaw")
jaw_bone.head = (MOUTH_X, MOUTH_Y, JAW_Z)
jaw_bone.tail = (MOUTH_X, MOUTH_Y - 0.02, JAW_Z - 0.02)
jaw_bone.parent = head_bone

upper_lip_bone = armature_data.edit_bones.new("UpperLip")
upper_lip_bone.head = (MOUTH_X, MOUTH_Y, UPPER_LIP_Z)
upper_lip_bone.tail = (MOUTH_X, MOUTH_Y - 0.02, UPPER_LIP_Z + 0.02)
upper_lip_bone.parent = head_bone

bpy.ops.object.mode_set(mode='OBJECT')

# 4. Parent & Groups
print("[JAW] Parenting mesh...")
mesh_obj.parent = armature
modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
modifier.object = armature

print("[JAW] Creating groups...")
for name in ["Root", "Head", "Jaw", "HeadTop", "UpperLip"]:
    if name not in mesh_obj.vertex_groups:
        mesh_obj.vertex_groups.new(name=name)

root_vg = mesh_obj.vertex_groups["Root"]
head_vg = mesh_obj.vertex_groups["Head"]
jaw_vg = mesh_obj.vertex_groups["Jaw"]
upper_lip_vg = mesh_obj.vertex_groups["UpperLip"]

# 5. Assign Weights (Ellipsoid 3D distance)
print("[JAW] Assigning weights...")
jaw_indices = []
upper_lip_indices = []

# Scaling factors for ellipsoid
X_SCALE = 0.5   # Narrow horizontal
Z_SCALE = 2.2   # Tight vertical

for i, coord in enumerate(verts):
    dx = coord[0] - MOUTH_X
    dy = coord[1] - MOUTH_Y

    # Jaw Distance
    dz_jaw = coord[2] - JAW_Z
    jaw_dist = math.sqrt(
        (dx * X_SCALE)**2 +
        dy**2 +
        (dz_jaw * Z_SCALE)**2
    )

    # Upper Lip Distance
    dz_upper = coord[2] - UPPER_LIP_Z
    upper_dist = math.sqrt(
        (dx * X_SCALE)**2 +
        dy**2 +
        (dz_upper * Z_SCALE)**2
    )

    # HARD SPLIT LOGIC
    weight_jaw = 0.0
    weight_upper = 0.0

    if coord[2] > JAW_Z_CENTER:
        # Above center -> Upper Lip ONLY
        if upper_dist < UPPER_LIP_RADIUS:
            weight_upper = (1 - (upper_dist / UPPER_LIP_RADIUS)) ** FALLOFF_EXPONENT
    else:
        # Below center -> Lower Jaw ONLY
        if jaw_dist < JAW_RADIUS:
            weight_jaw = (1 - (jaw_dist / JAW_RADIUS)) ** FALLOFF_EXPONENT

    if weight_jaw > 0:
        jaw_vg.add([i], weight_jaw, 'REPLACE')
        jaw_indices.append(i)
        head_vg.add([i], 1.0 - weight_jaw, 'REPLACE')
    elif weight_upper > 0:
        upper_lip_vg.add([i], weight_upper, 'REPLACE')
        upper_lip_indices.append(i)
        head_vg.add([i], 1.0 - weight_upper, 'REPLACE')

print(f"[JAW] Lower Jaw vertices: {len(jaw_indices)}")
print(f"[JAW] Upper Lip vertices: {len(upper_lip_indices)}")

# 6. Animation - Talk
print("[JAW] Creating animation...")
if not armature.animation_data:
    armature.animation_data_create()

talk_action = bpy.data.actions.new(name="Talk")
armature.animation_data.action = talk_action

jaw_pose = armature.pose.bones["Jaw"]
jaw_pose.rotation_mode = 'XYZ'
upper_lip_pose = armature.pose.bones["UpperLip"]
upper_lip_pose.rotation_mode = 'XYZ'

# Animation keyframes
frames = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40]
amount = [0, 1.0, 0.2, 0.8, 0, 0.5, 0.9, 0.3, 0.7, 0, 0]

for i, val in enumerate(amount):
    frame = frames[i]
    bpy.context.scene.frame_set(frame)
    # Upper lip moves UP (Negative Z)
    upper_lip_pose.location = (0, 0, -val * 0.03)
    upper_lip_pose.keyframe_insert(data_path="location", frame=frame)
    # Jaw moves DOWN (Positive Z)
    jaw_pose.location = (0, 0, val * 0.05)
    jaw_pose.keyframe_insert(data_path="location", frame=frame)

talk_track = armature.animation_data.nla_tracks.new()
talk_strip = talk_track.strips.new("Talk", 0, talk_action)
talk_strip.name = "Talk"

# 7. Export
print("[JAW] Exporting to:", OUTPUT)
bpy.ops.export_scene.gltf(
    filepath=OUTPUT,
    export_format='GLB',
    export_skins=True,
    export_all_influences=True,
    export_yup=True,
    export_animations=True,
    export_nla_strips=True,
)
print("[JAW] DONE! Argock rigged and exported.")
