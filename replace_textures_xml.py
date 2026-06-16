import UnityPy
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import datetime
import hashlib
from collections import Counter
import tkinter as tk
from tkinter import filedialog
from PIL import ImageChops
import struct

# --- CONFIGURATION ---
GAME = 3  # Switch to 2 for TMGS2

CONFIG = {
    1: {
        "REPLACEMENT_ROOT": r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\Translated (In Directories)",
        "SRC_BUNDLE_ROOT": r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\Original Data 1.0.4\Data\StreamingAssets",
        "OUTPUT_ROOT": r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\modded_on_demand_new_xml_meshgen_final_4vert_colours_cutouts_legfix_FINAL",
        "XML_INDEX": r"G:\TMGS1 Patch Stuff\TOOLS\Texture Replacer\asset_index_1.xml",
        "DEBUG_EVIDENCE": r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\DEBUG_EVIDENCE"
    },
    2: {
        "REPLACEMENT_ROOT": r"G:\TMGS2 Patch Stuff\TRANSLATED IMAGES\Translated (In Directories)",
        "SRC_BUNDLE_ROOT": r"G:\TMGS2 Patch Stuff\TRANSLATED IMAGES\Original Data\Data\StreamingAssets",
        "OUTPUT_ROOT": r"G:\TMGS2 Patch Stuff\TRANSLATED IMAGES\modded_on_demand_new_xml_meshgen_final_4vert_new_colours_cutouts_legfix_a_FINAL",
        "XML_INDEX": r"C:\Users\Phoenix\Documents\Python Projects\UnityTextureReplacer\asset_index_2.xml",
        "DEBUG_EVIDENCE": r"G:\TMGS2 Patch Stuff\TRANSLATED IMAGES\DEBUG_EVIDENCE"
    },
    3: {
        "REPLACEMENT_ROOT": r"G:\TMGS3 Patch Stuff\TRANSLATED IMAGES\Translated (In Directories)",
        "SRC_BUNDLE_ROOT": r"G:\TMGS3 Patch Stuff\TRANSLATED IMAGES\Original Data\Data\StreamingAssets",
        "OUTPUT_ROOT": r"G:\TMGS3 Patch Stuff\TRANSLATED IMAGES\modded_on_demand_new_xml_meshgen_final_4vert_new_colours_cutouts_legfix_a_FINAL_v2",
        "XML_INDEX": r"C:\Users\Phoenix\Documents\Python Projects\UnityTextureReplacer\asset_index_3.xml",
        "DEBUG_EVIDENCE": r"G:\TMGS3 Patch Stuff\TRANSLATED IMAGES\DEBUG_EVIDENCE"
    },
    4: {
        "REPLACEMENT_ROOT": r"G:\TMGS4PatchStuff\TRANSLATED IMAGES\msg window test",
        "SRC_BUNDLE_ROOT": r"G:\Yuzu Dumps\TMGS4 v110\0100B0100E26C000\romfs\Data\StreamingAssets",
        "OUTPUT_ROOT": r"G:\TMGS4PatchStuff\TRANSLATED IMAGES\modded_on_demand_new_xml_meshgen_final_4vert_new_msg",
        "XML_INDEX": r"C:\Users\Phoenix\Documents\Python Projects\UnityTextureReplacer\asset_index_4.xml",
        "DEBUG_EVIDENCE": r"G:\TMGS4PatchStuff\TRANSLATED IMAGES\DEBUG_EVIDENCE"
    },
}

# Resolve active paths
ACTIVE_CONFIG = CONFIG[GAME]
REPLACEMENT_ROOT = ACTIVE_CONFIG["REPLACEMENT_ROOT"]
SRC_BUNDLE_ROOT = ACTIVE_CONFIG["SRC_BUNDLE_ROOT"]
OUTPUT_ROOT = ACTIVE_CONFIG["OUTPUT_ROOT"]
XML_INDEX_PATH = ACTIVE_CONFIG["XML_INDEX"]
DEBUG_EVIDENCE_DIR = ACTIVE_CONFIG["DEBUG_EVIDENCE"]

# Universal Paths
OBJ_OUTPUT_ROOT = f"G:\\TMGS{GAME} Patch Stuff\\TRANSLATED IMAGES\\GENERATED\\obj"
ALPHA_OUTPUT_ROOT = f"G:\\TMGS{GAME} Patch Stuff\\TRANSLATED IMAGES\\GENERATED\\alpha"
LOG_FILENAME = f"xml_recursive_bundle_search_{GAME}.txt"

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(message)
    try:
        script_dir = Path(__file__).resolve().parent
        log_path = script_dir / LOG_FILENAME
        with open(log_path, "a", encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass

def get_image_hash(img):
    return hashlib.md5(img.tobytes()).hexdigest()

def find_bundle_disambiguated(container_path, target_filename):
    candidates = list(Path(SRC_BUNDLE_ROOT).rglob(target_filename))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    best_candidate, best_score = None, -1
    for cand in candidates:
        try:
            rel_cand = cand.relative_to(SRC_BUNDLE_ROOT)
            cand_dir = str(rel_cand.parent).replace('\\', '/')
            if cand_dir == ".":
                cand_dir = ""
        except ValueError:
            continue
        score = -1
        if cand_dir in container_path:
            score = len(cand_dir)
        elif cand_dir == "":
            score = 0
            
        if score > best_score:
            best_score = score
            best_candidate = cand
    if best_candidate and best_score >= 0:
        log(f"      DISAMBIGUATED {target_filename}: picked '{best_candidate.relative_to(SRC_BUNDLE_ROOT)}'")
        return best_candidate
    return None

def find_bundle_recursive(container_path):
    parts = container_path.split('/')
    if len(parts) < 2:
        return None
    if parts[-2].lower() == "bg":
        found = find_bundle_disambiguated(container_path, f"{parts[-1].rsplit('.', 1)[0]}.assetbundle")
        if found:
            return found
    for i in range(len(parts) - 2, 1, -1):
        found = find_bundle_disambiguated(container_path, f"{parts[i]}.assetbundle")
        if found:
            return found
    return None

def copy_bundle_file(source_path, dest_path):
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return True
    except Exception as e:
        log(f"ERROR copying bundle: {e}")
        return False

def generate_mesh_from_original(sprite_data, replacement_img_path, name):
    log(f"--- Generating 4-Vertex Quad for {name} based on Original Mesh Bounds ---")
    os.makedirs(OBJ_OUTPUT_ROOT, exist_ok=True)
    os.makedirs(ALPHA_OUTPUT_ROOT, exist_ok=True)
    
    obj_dec_path = os.path.join(OBJ_OUTPUT_ROOT, f"{name}_dec.obj")
    alpha_img_path = os.path.join(ALPHA_OUTPUT_ROOT, f"{name}_alpha.png")
    
    try:
        with Image.open(replacement_img_path) as img:
            if "A" in img.getbands():
                img.getchannel("A").save(alpha_img_path)
                log(f"   [ALPHA] Saved alpha channel to {alpha_img_path}")
    except Exception as e:
        log(f"   [ALPHA ERROR]: {e}")

    m_rd = sprite_data.m_RD
    vd = m_rd.m_VertexData
    raw_bytes = vd.m_DataSize
    vertex_count = vd.m_VertexCount
    pos_offset = vd.m_Channels[0].offset

    xs, ys = [], []
    for i in range(vertex_count):
        start = pos_offset + (i * 12)
        if start + 12 <= len(raw_bytes):
            x, y, z = struct.unpack('<3f', raw_bytes[start : start + 12])
            xs.append(x)
            ys.append(y)

    if not xs or not ys:
        log(f"   [ERROR] Could not extract vertices from original sprite {name}")
        return

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    log(f"   [BOUNDS] X: ({min_x}, {max_x}) | Y: ({min_y}, {max_y})")

    verts = [
        (min_x, min_y, 0.0),
        (max_x, min_y, 0.0),
        (max_x, max_y, 0.0),
        (min_x, max_y, 0.0)
    ]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    try:
        with open(obj_dec_path, "w") as f:
            f.write(f"# Quad for {name} generated from original bounds\n")
            f.write("o Quad\n")
            for v in verts:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for u in uvs:
                f.write(f"vt {u[0]} {u[1]}\n")
            f.write("f 1/1 2/2 3/3\nf 1/1 3/3 4/4\n")
        log(f"SUCCESS: Saved quad mesh to {obj_dec_path}")
    except Exception as e:
        log(f"ERROR generating mesh: {e}")

def parse_obj_mesh(file_path):
    vertices, uvs, indices = [], [], []
    with open(file_path, "r") as f:
        for line in f:
            p = line.split()
            if line.startswith("v "):
                vertices.append({"x": float(p[1]), "y": float(p[2]), "z": float(p[3])})
            elif line.startswith("vt "):
                uvs.append({"x": float(p[1]), "y": float(p[2])})
            elif line.startswith("f "):
                for part in p[1:]:
                    indices.append(int(part.split('/')[0]) - 1)
    return vertices, uvs, indices

def pack_vertex_data(new_verts, new_uvs):
    buffer = bytearray()
    for v in new_verts:
        buffer += struct.pack('<3f', v['x'], v['y'], v['z'])
    for uv in new_uvs:
        buffer += struct.pack('<2f', uv['x'], uv['y'])
    buffer += b'\x00' * 8
    return bytes(buffer)

def replace_sprite_mesh(sprite, new_mesh_path, name, alpha_path=None):
    log(f"--- Overwriting Mesh for Sprite {name} ---")
    try:
        new_verts, new_uvs, new_indices = parse_obj_mesh(new_mesh_path)
        m_rd = sprite.m_RD
        m_rd.vertices = [{"pos": v, "uv": u} for v, u in zip(new_verts, new_uvs)]
        m_rd.indices = new_indices
        
        if hasattr(m_rd, "m_SubMeshes") and len(m_rd.m_SubMeshes) > 0:
            sm = m_rd.m_SubMeshes[0]
            sm.indexCount, sm.vertexCount = len(new_indices), len(new_verts)
            sm.firstVertex = sm.firstByte = sm.baseVertex = sm.topology = 0

        if hasattr(m_rd, "m_IndexBuffer"):
            m_rd.m_IndexBuffer = list(struct.pack(f"<{len(new_indices)}H", *new_indices))

        if hasattr(m_rd, "m_VertexData") and m_rd.m_VertexData:
            m_rd.m_VertexData.m_VertexCount = len(new_verts)
            m_rd.m_VertexData.m_DataSize = pack_vertex_data(new_verts, new_uvs)
        
        if alpha_path and os.path.exists(alpha_path):
            if hasattr(m_rd, "alphaTexture") and m_rd.alphaTexture:
                alpha_tex = m_rd.alphaTexture.read()
                with Image.open(alpha_path) as alpha_img:
                    alpha_tex.image = alpha_img
                    alpha_tex.save()
                    log(f"   [SUCCESS] Updated Alpha Texture for {name}")

        sprite.save()
        log(f"   [SUCCESS] Updated SubMeshes, Indices, and Vertices for {name}")
        return sprite
    except Exception as e:
        log(f"   [ERROR] Failed inside replace_sprite_mesh: {e}")
        return None

def run_strict_replacement():
    log(f"--- Starting Replacement for GAME {GAME} ---")
    injection_stats, total_skipped = Counter(), 0
    matched_image_paths = set()

    try:
        root = ET.parse(XML_INDEX_PATH).getroot()
    except Exception as e:
        log(f"XML ERROR: {e}")
        return

    xml_lookup = {}
    for asset in root.findall('Asset'):
        type_node = asset.find('Type')
        if type_node is not None and type_node.text == "Texture2D":
            name = asset.find('Name').text
            if name not in xml_lookup:
                xml_lookup[name] = []
            xml_lookup[name].append({"Container": asset.find('Container').text, "PathID": int(asset.find('PathID').text)})

    rep_root = Path(REPLACEMENT_ROOT)
    valid_images = [p for p in rep_root.rglob("*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg']]
    
    bundle_tasks = {}
    for img_path in valid_images:
        target_name = img_path.stem
        if target_name not in xml_lookup:
            continue
        disk_dir = os.path.dirname(str(img_path.relative_to(rep_root)).replace('\\', '/').lower())

        for cand in xml_lookup[target_name]:
            clean_cont = cand['Container'].rsplit('.', 1)[0].lower()
            if clean_cont.endswith(disk_dir) or os.path.dirname(clean_cont).endswith(disk_dir):
                actual_bundle = find_bundle_recursive(cand['Container'])
                if actual_bundle:
                    b_key = str(actual_bundle)
                    if b_key not in bundle_tasks:
                        bundle_tasks[b_key] = []
                    bundle_tasks[b_key].append({"name": target_name, "path_id": cand['PathID'], "img_path": img_path})
                    matched_image_paths.add(img_path)
                    break

    for b_path, tasks in bundle_tasks.items():
        src_p = Path(b_path)
        if SRC_BUNDLE_ROOT in str(src_p):
            dst_p = Path(OUTPUT_ROOT) / src_p.relative_to(SRC_BUNDLE_ROOT)
        else:
            dst_p = Path(OUTPUT_ROOT) / src_p.name
        
        try:
            env = UnityPy.load(str(src_p))
            mod, t_map = False, {t['path_id']: t for t in tasks}
            
            # Pre-collect sprites to handle those referencing texture tasks
            all_sprites = [obj for obj in env.objects if obj.type.name == "Sprite"]
            sprite_mesh_tasks = {}

            for obj in env.objects:
                if obj.path_id in t_map:
                    task = t_map[obj.path_id]
                    inst = obj.parse_as_object()
                    with Image.open(task['img_path']) as repl_img:
                        if get_image_hash(inst.image) == get_image_hash(repl_img):
                            log(f"   SKIPPING {inst.m_Name}: MD5 MATCH")
                            total_skipped += 1
                        else:
                            mod = True
                            injection_stats[str(src_p.name)] += 1
                            
                            # Mesh check
                            diff = ImageChops.difference(inst.image.getchannel("A"), repl_img.getchannel("A"))
                            if diff.getbbox():
                                # Check every sprite in this bundle
                                for s_obj in all_sprites:
                                    s_data = s_obj.read()
                                    referenced_tex = s_data.m_RD.texture
                                    
                                    # Trigger mesh gen if Sprite name matches OR references this modified texture
                                    is_match = False
                                    if s_data.m_Name == inst.m_Name:
                                        is_match = True
                                    elif referenced_tex is not None and referenced_tex.path_id == obj.path_id:
                                        is_match = True
                                        
                                    if is_match:
                                        generate_mesh_from_original(s_data, task['img_path'], s_data.m_Name)
                                        sprite_mesh_tasks[s_obj.path_id] = {
                                            "obj_path": os.path.join(OBJ_OUTPUT_ROOT, f"{s_data.m_Name}_dec.obj"), 
                                            "alpha_path": os.path.join(ALPHA_OUTPUT_ROOT, f"{s_data.m_Name}_alpha.png"),
                                            "name": s_data.m_Name
                                        }

            if mod and copy_bundle_file(src_p, dst_p):
                out_env = UnityPy.load(str(dst_p))
                for out_obj in out_env.objects:
                    if out_obj.path_id in t_map:
                        tex = out_obj.parse_as_object()
                        with Image.open(t_map[out_obj.path_id]['img_path']) as img:
                            tex.image = img
                            tex.save()
                    elif out_obj.path_id in sprite_mesh_tasks:
                        m_task = sprite_mesh_tasks[out_obj.path_id]
                        replace_sprite_mesh(out_obj.parse_as_object(), m_task['obj_path'], m_task['name'], m_task['alpha_path'])
                with open(dst_p, "wb") as f:
                    f.write(out_env.file.save(packer="original"))
        except Exception as e:
            log(f"BUNDLE ERROR in {src_p.name}: {e}")

    # Unmatched
    unmatched = [img for img in valid_images if img not in matched_image_paths]
    if unmatched:
        log("\n" + "!"*60 + "\nUNMATCHED IMAGES\n" + "!"*60)
        for img in unmatched:
            log(f" NO BUNDLE MATCH: {img.relative_to(rep_root)}")

    log(f"\nSummary: {sum(injection_stats.values())} injected, {total_skipped} skipped.")

if __name__ == "__main__":
    run_strict_replacement()