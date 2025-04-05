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
from . import skin_weights_operator


def register():
    skin_weights_operator.register()


def unregister():
    skin_weights_operator.unregister()


if __name__ == "__main__":
    register()
