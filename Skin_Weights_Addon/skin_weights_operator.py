bl_info = {
    "name": "Skin Weights Export/Import",
    "author": "Nguyễn Phúc Nguyễn",
    "version": (1, 0, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > Skin Weights",
    "description": "Export and Import Skin Weights using Position or UV mapping",
    "warning": "",
    "wiki_url": "https://github.com/NguyenNP-24",
    "category": "Rigging",
    "license": "GPL"
}

import bpy
import json
from mathutils.kdtree import KDTree

def get_uv_coords(obj, vert_index):
    """Get the average UV coordinates of a vertex by index."""
    
    # Ensure the object has an active UV layer
    uv_layer = obj.data.uv_layers.active
    if not uv_layer:
        return None  # Return None if no UV layer is available
    
    uv_data = uv_layer.data

    # Collect all UV coordinates associated with the given vertex index
    uvs = [uv_data[loop.index].uv[:] for loop in obj.data.loops if loop.vertex_index == vert_index]
    
    if not uvs:
        return None  # Return None if the vertex has no UV coordinates

    # Compute the average UV coordinate (useful when a vertex has multiple UV mappings)
    avg_uv = [sum(coord) / len(uvs) for coord in zip(*uvs)]
    return avg_uv

def export_skin_weights(filepath):
    if not filepath:
        print("Invalid file path!")
        return

    obj = bpy.context.object
    if obj is None or obj.type != 'MESH':
        print("No mesh selected!")
        return
    
    vertices = obj.data.vertices
    total_verts = len(vertices)
    if total_verts == 0:
        print("No vertices found!")
        return
    
    wm = bpy.context.window_manager
    wm.progress_begin(0, total_verts)  

    log_interval = max(1, total_verts // 10)  # Only print log each 10%
    update_interval = max(1, total_verts // 1000)  # Only update progress bar every 1000 vertices
    
    # Open the file first to write each part, avoid saving the whole thing to RAM
    with open(filepath, 'w') as f:
        f.write('{"vertices": [\n')

        for i, vert in enumerate(vertices):
            uv_coords = get_uv_coords(obj, vert.index) or [0.0, 0.0]

            v_data = {
                "co": list(vert.co),
                "uv": uv_coords,
                "weights": {}
            }

            for group in obj.vertex_groups:
                try:
                    weight = group.weight(vert.index)
                    if weight > 0:
                        v_data["weights"][group.name] = weight
                except RuntimeError:
                    pass  

            # Write JSON line by line directly to file
            json.dump(v_data, f)
            if i < total_verts - 1:
                f.write(',\n')

            # Update less progress bar
            if i % update_interval == 0:
                wm.progress_update(i)

            # Print log each 10% progress
            if i % log_interval == 0:
                print(f"Exporting... {i / total_verts:.0%} done")

        f.write('\n]}')  # Done JSON file

    wm.progress_end()  
    print("✅ Export Successful!")
        
        
def find_closest_uv_match(obj, vert, source_data):
    """Find the closest UV match from the source data."""
    
    if not source_data:
        return -1  # Return -1 if no data available

    # Ensure UV coordinates are valid
    target_uv = get_uv_coords(obj, vert.index)
    if target_uv is None:
        target_uv = [0.0, 0.0]

    min_dist = float('inf')
    best_index = -1
    
    for i, v in enumerate(source_data):
        source_uv = v.get("uv", [0.0, 0.0])
        dist = sum((a - b) ** 2 for a, b in zip(target_uv, source_uv))

        if dist < min_dist:
            min_dist = dist
            best_index = i

    return best_index

def import_skin_weights(filepath, mapping_mode):
    """Import skin weights from a JSON file and apply them to the active mesh."""
    
    if not filepath:
        print("Invalid file path!")
        return

    obj = bpy.context.object
    if obj is None or obj.type != 'MESH':
        print("No mesh selected!")
        return
    
    try:
        with open(filepath, 'r') as f:
            skin_data = json.load(f)
    except Exception as e:
        print(f"Import Failed: {e}")
        return

    # Ensure skin_data has valid "vertices" key
    vertices_data = skin_data.get("vertices", [])
    if not vertices_data:
        print("No valid vertex data found in file!")
        return
    
    if mapping_mode == 'POSITION':
        old_tree = KDTree(len(vertices_data))
        for i, v in enumerate(vertices_data):
            old_tree.insert(v["co"], i)
        old_tree.balance()
    
    for vert in obj.data.vertices:
        if mapping_mode == 'POSITION':
            co, index, _ = old_tree.find(vert.co)
        elif mapping_mode == 'UV':
            index = find_closest_uv_match(obj, vert, vertices_data)
            if index == -1:
                continue  # Skip if no match found
        else:
            continue  # Invalid mapping mode
        
        closest_data = vertices_data[index]
        weights = closest_data.get("weights", {})
        if not weights:
            continue  # Skip if no weights

        for group_name, weight in weights.items():
            group = obj.vertex_groups.get(group_name)
            if not group:
                group = obj.vertex_groups.new(name=group_name)
            group.add([vert.index], weight, 'REPLACE')
    
    print("Import Successful!")


class ExportSkinWeights(bpy.types.Operator):
    """Export skin weights for the active mesh to a JSON file, storing vertex group influences for later re-import."""
    
    bl_idname = "object.export_skin_weights"
    bl_label = "Export Skin Weights"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export skin weights for active mesh to a JSON file, storing vertex group influences for later re-import."
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No valid mesh selected!")
            return {'CANCELLED'}
        
        if not self.filepath:
            self.report({'ERROR'}, "No file selected!")
            return {'CANCELLED'}
        
        try:
            export_skin_weights(self.filepath)
            self.report({'INFO'}, "Skin weights exported successfully!")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class ImportSkinWeights(bpy.types.Operator):
    """Import skin weights from a JSON file using the selected mapping mode (Position or UV)."""
    
    bl_idname = "object.import_skin_weights"
    bl_label = "Import Skin Weights"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import skin weights from a JSON file using the selected mapping mode (Position or UV)."
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    mapping_mode: bpy.props.EnumProperty(
        items=[
            ('POSITION', "Position", "Map by closest vertex position"),
            ('UV', "UV", "Map using UV coordinates")
        ],
        name="Mapping Mode",
        default='POSITION'
    )

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No valid mesh selected!")
            return {'CANCELLED'}
        
        if not self.filepath:
            self.report({'ERROR'}, "No file selected!")
            return {'CANCELLED'}
        
        try:
            import_skin_weights(self.filepath, self.mapping_mode)
            self.report({'INFO'}, "Skin weights imported successfully!")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class SkinWeightPanel(bpy.types.Panel):
    bl_label = "Skin Weight Tools"
    bl_idname = "VIEW3D_PT_skin_weights"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rigging"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("object.export_skin_weights")
        row = layout.row()
        split = layout.split(factor=0.44)  
        split.label(text="Mapping Mode:")
        mapping_value = context.scene.mapping_mode
        icon = 'GROUP_UVS' if mapping_value == 'UV' else 'GROUP_VERTEX'
        split.prop(context.scene, "mapping_mode", text="", icon=icon)
        layout.operator("object.import_skin_weights")

def register():
    bpy.types.Scene.mapping_mode = bpy.props.EnumProperty(
        items=[
            ('POSITION', "Position", "Map by closest vertex position"),
            ('UV', "UV", "Map using UV coordinates")
        ],
        name="Mapping Mode",
        default='POSITION'
    )
    
    bpy.utils.register_class(ExportSkinWeights)
    bpy.utils.register_class(ImportSkinWeights)
    bpy.utils.register_class(SkinWeightPanel)

def unregister():
    del bpy.types.Scene.mapping_mode
    bpy.utils.unregister_class(ExportSkinWeights)
    bpy.utils.unregister_class(ImportSkinWeights)
    bpy.utils.unregister_class(SkinWeightPanel)

if __name__ == "__main__":
    register()
