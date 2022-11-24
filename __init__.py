# SPDX-License-Identifier: GPL-2.0-or-later
 
bl_info = {
    "name": "Edit Manager",
    "description": "Tools to help editing scene in sequencer",
    "author": "Samuel Bernou",
    "version": (0, 2, 0),
    "blender": (3, 3, 0),
    "location": "",
    "warning": "",
    "category": "Sequencer",
}

import bpy
from typing import List, Sequence, Tuple
from bpy.types import (
    Context,
    MetaSequence,
    Operator,
    PropertyGroup,
    SceneSequence,
    Window,
    WindowManager,
)


def go_to_scene_from_strip(context=None, set_view=True):
    context = context or bpy.context

    strip = context.active_sequence_strip
    if not strip:
        return 'No active strip'
    if strip.type != 'SCENE':
        return 'Active strip is not a scene strip'

    bpy.context.window.scene = strip.scene
    # print(f'\nSwitch to SCENE {strip.scene.name}')
    bpy.context.window.workspace = bpy.data.workspaces['2D Animation']
    
    if set_view:    
        ##-- Set viewport aligned with camera

        ## set viewport on camera view on smaller or bigger viewport area
        ## True, False
        bigger = False
        # shot_scene = strip.scene # re-set scene
        shot_scene = bpy.context.scene
        cam = shot_scene.camera
        if cam:
            print(cam.name)
            areas_3d = []
            loc = cam.matrix_world.to_translation()
            rot = cam.matrix_world.to_quaternion()
            for window in bpy.context.window_manager.windows:
                screen = window.screen
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        r3d = area.spaces[0].region_3d
                        
                        ## skip camera ? (In camera, view location is affected but not rotation)
                        # if r3d.view_perspective == 'CAMERA':
                        #     continue
                        
                        r3d.view_location = loc
                        r3d.view_rotation = rot

                        areas_3d.append(area)

            ## if multiple viewport, set cam active on the smaller viewport (pixel wise)
            print(len(areas_3d))
            if len(areas_3d) > 1:
                print('set_view')
                areas_3d.sort(key=lambda x: (x.width, x.height), reverse=bigger)
                areas_3d[0].spaces[0].region_3d.view_perspective = 'CAMERA'


class EDIT_OT_switch_scene_edit(Operator):
    bl_idname = "edit.switch_scene_edit"
    bl_label = "Switch Edit"
    bl_description = "Switch scene and workspace between shot and edit"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        scn = context.scene
        if scn.name != 'EDIT':
            print('\nSwitch to EDIT')
            bpy.context.window.scene = bpy.data.scenes['EDIT']
            bpy.context.window.workspace = bpy.data.workspaces['Video Editing']
        else:
            ret = go_to_scene_from_strip(context=context, set_view=True)
            if isinstance(ret, str):
                self.report({'ERROR'}, ret)
                return {'CANCELLED'}

            '''
            set_view = True
            strip = context.active_sequence_strip
            if not strip:
                self.report({'ERROR'}, 'No active strip')
                return {'CANCELLED'}
            if strip.type != 'SCENE':
                self.report({'ERROR'}, 'Active strip is not a scene strip')
                return {'CANCELLED'}

            bpy.context.window.scene = strip.scene
            print(f'\nSwitch to SCENE {strip.scene.name}')
            bpy.context.window.workspace = bpy.data.workspaces['2D Animation']
            
            if set_view:    
                ##-- Set viewport aligned with camera

                ## set viewport on camera view on smaller or bigger viewport area
                ## True, False
                bigger = False
                # shot_scene = strip.scene # re-set scene
                shot_scene = bpy.context.scene
                cam = shot_scene.camera
                if cam:
                    print(cam.name)
                    areas_3d = []
                    loc = cam.matrix_world.to_translation()
                    rot = cam.matrix_world.to_quaternion()
                    for window in bpy.context.window_manager.windows:
                        screen = window.screen
                        for area in screen.areas:
                            if area.type == 'VIEW_3D':
                                r3d = area.spaces[0].region_3d
                                
                                ## skip camera ? (In camera, view location is affected but not rotation)
                                # if r3d.view_perspective == 'CAMERA':
                                #     continue
                                
                                r3d.view_location = loc
                                r3d.view_rotation = rot

                                areas_3d.append(area)

                    ## if multiple viewport, set cam active on the smaller viewport (pixel wise)
                    print(len(areas_3d))
                    if len(areas_3d) > 1:
                        print('set_view')
                        areas_3d.sort(key=lambda x: (x.width, x.height), reverse=bigger)
                        areas_3d[0].spaces[0].region_3d.view_perspective = 'CAMERA'
                '''

        return {'FINISHED'}

class EDIT_OT_go_to_scene(Operator):
    bl_idname = "edit.go_to_scene"
    bl_label = "Go To Scene"
    bl_description = "Go to scene"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.name == 'EDIT'

    def execute(self, context):
        go_to_scene_from_strip(context=context, set_view=True)
        return {'FINISHED'}

def send_sound_strip(s, dest_scn):
    '''recreate sound strip in another scene
    :dest_scn: scene destination
    :return: newly create sound strip
    ## TODO check if there is a way to directly link a strip (would be awesome)
    '''

    if s.type != 'SOUND':
        return
    vse = dest_scn.sequence_editor
    ns = vse.sequences.new_sound(name=s.name, filepath=s.sound.filepath, channel=s.channel, frame_start=int(s.frame_start))
    ns.sound = s.sound # reget the same sound source
    
    for attr in ('frame_final_start','frame_final_end','frame_still_start','frame_still_end','frame_offset_start','frame_offset_end','pitch','pan','show_waveform','speed_factor','volume','mute'):
        if hasattr(s, attr):
            setattr(ns, attr, getattr(s, attr))
    
    if ns.volume == 0:
        ns.volume = 1
    return ns

def get_scene_frame_from_sequencer_frame(scn_strip, frame) -> float:
    """return frame in scene referential"""
    return frame - scn_strip.frame_start + scn_strip.scene.frame_start

def get_all_overlapping_sound_strip(scn_strip, skip_mute=True, skip_unselected=True):
    if scn_strip.type != 'SCENE':
        return

    src_scn = scn_strip.id_data
    vse = src_scn.sequence_editor
    overlapping_sounds = []
    for s in vse.sequences:
        if s.type != 'SOUND':
            continue
        if skip_mute and s.mute:
            continue
        if skip_unselected and not s.select:
            continue

        if (s.frame_final_end <  scn_strip.frame_final_start)\
            or (s.frame_final_start > scn_strip.frame_final_end):
            continue
        
        ## on scene strip maybe compare to start/end not final start/end
        # if (s.frame_final_end <  scn_strip.frame_start)\
        #     or (s.frame_final_start > scn_strip.frame_end):
        #     continue
        overlapping_sounds.append(s)
    
    return overlapping_sounds


def send_sound_to_strip_scene(scn_strip, clear_sequencer=True, skip_mute=True, skip_unselected=True):
    if scn_strip.type != 'SCENE':
        return
    tgt_scene = scn_strip.scene

    sounds = get_all_overlapping_sound_strip(scn_strip, skip_mute=skip_mute, skip_unselected=skip_unselected)
    if not sounds:
        print(f'! No sound to send to scene {tgt_scene.name}')
        return
    
    ## TODO clear sounds if exists in scene vse already
    if clear_sequencer:
        for st in reversed(tgt_scene.sequence_editor.sequences):
            tgt_scene.sequence_editor.sequences.remove(st)

    print(f'Duplicating sounds in {tgt_scene.name}:')
    for s in sounds:
        new_start = get_scene_frame_from_sequencer_frame(scn_strip, s.frame_start)
        print(f'- {s.name}')
        ns = send_sound_strip(s, tgt_scene)
        if ns:
            ns.frame_start = new_start        

    return sounds


def dispatch_sounds_in_scenes(selected_scn_only=True, skip_mute=True, skip_unselected=True):
    edit_scene = bpy.context.scene
    edit = edit_scene.sequence_editor

    ct = 0
    for strip in edit.sequences:
        if strip.type != 'SCENE':
            continue

        if 'edit' in strip.scene.name.lower():
            print(f'"{strip.scene.name}" has edit in name, skip')
            continue

        if selected_scn_only and not strip.select:
            continue

        sounds = send_sound_to_strip_scene(strip, skip_mute=skip_mute,  skip_unselected=skip_unselected)
        if sounds:
            ct += 1

    if ct:
        print('INFO', f'Sound duplicated in {ct} scenes')
    else:
        print('ERROR', f'No duplication occured')


class EDIT_OT_duplicate_sound_in_strip_scene(Operator):
    bl_idname = "edit.duplicate_sound_in_strip_scene"
    bl_label = "Sounds To Scenes"
    bl_description = "Send sounds to scene in strips\
        \nCtrl + Click to use default"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.name == 'EDIT'

    selected_scn_only : bpy.props.BoolProperty(name='Selected Scene Only', 
        default=True,
        description='Selected Scene only')
    skip_sound_mute : bpy.props.BoolProperty(name='Ignore Muted Sound', 
        default=True,
        description='Skip muted sound')
    skip_sound_unselected : bpy.props.BoolProperty(name='Ignore Unselected Sound', 
        default=True,
        description='Skip unselected sound')


    def invoke(self, context, event):
        if event.ctrl:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self) # width=
    
    def draw(self, context):
        layout = self.layout
        col=layout.column()
        col.prop(self, 'selected_scn_only')
        col.separator()
        col.label(text='Sounds')
        col.prop(self, 'skip_sound_mute')
        col.prop(self, 'skip_sound_unselected')

    def execute(self, context):
        dispatch_sounds_in_scenes(
            selected_scn_only=self.selected_scn_only,
            skip_mute=self.skip_sound_mute,
            skip_unselected=self.skip_sound_unselected)

        # send_sound_to_strip_scene(edit.active_strip)
        return {'FINISHED'}        


class EDIT_PT_edit_manager_ui(bpy.types.Panel):
    bl_label = "Edit Manager"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator('edit.duplicate_sound_in_strip_scene')

classes = (
    EDIT_OT_switch_scene_edit,
    EDIT_OT_go_to_scene,
    EDIT_OT_duplicate_sound_in_strip_scene,
    EDIT_PT_edit_manager_ui,
)


addon_keymaps = []
def register_keymaps():
    if bpy.app.background:
        return

    addon = bpy.context.window_manager.keyconfigs.addon
    km = addon.keymaps.new(name = "Window", space_type = "EMPTY")
    kmi = km.keymap_items.new('edit.switch_scene_edit', type="F6", value="PRESS") # , shift=True
    addon_keymaps.append((km, kmi))

    km = addon.keymaps.new(name = "Sequencer", space_type = "SEQUENCE_EDITOR")
    kmi = km.keymap_items.new('edit.go_to_scene', type="LEFTMOUSE", value="DOUBLE_CLICK") # , shift=True
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    if not addon_keymaps:
        return
    if bpy.app.background:
        return
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)

    addon_keymaps.clear()

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_keymaps()

def unregister():
    unregister_keymaps()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()