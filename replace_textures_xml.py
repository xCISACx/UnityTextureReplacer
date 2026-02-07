import UnityPy
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import datetime
import hashlib
from collections import Counter

import meshlib.mrmeshpy as mr
import meshlib.mrmeshnumpy as mrmeshnumpy

REPLACEMENT_ROOT = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\Loose test manual"
OUTPUT_ROOT = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\modded_on_demand_new_xml_TEST_meshgen"
OBJ_OUTPUT_ROOT = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\GENERATED\obj"
ALPHA_OUTPUT_ROOT = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\GENERATED\alpha"
SRC_BUNDLE_ROOT = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\Original Data 1.0.4\Data\StreamingAssets"
XML_INDEX_PATH = r"G:\TMGS1 Patch Stuff\TOOLS\Texture Replacer\asset_index.xml"
LOG_FILENAME = "xml_recursive_bundle_search.txt"
DEBUG_EVIDENCE_DIR = r"G:\TMGS1 Patch Stuff\TRANSLATED IMAGES\DEBUG_EVIDENCE" 

try:
    script_dir = Path(__file__).resolve().parent
except NameError:
    script_dir = Path.cwd()

LOG_FILE_PATH = script_dir / LOG_FILENAME

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(message) 
    try:
        with open(LOG_FILE_PATH, "a", encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except: pass

def get_image_hash(img):
    return hashlib.md5(img.tobytes()).hexdigest()

def find_bundle_disambiguated(container_path, target_filename):
    candidates = list(Path(SRC_BUNDLE_ROOT).rglob(target_filename))
    
    if not candidates:
        return None
        
    if len(candidates) == 1:
        return candidates[0]

    best_candidate = None
    best_score = -1
    
    for cand in candidates:
        try:
            rel_cand = cand.relative_to(SRC_BUNDLE_ROOT)
            cand_dir = str(rel_cand.parent).replace('\\', '/')
            if cand_dir == ".": cand_dir = ""
        except ValueError:
            continue

        if cand_dir == "":
            score = 0 
        elif cand_dir in container_path:
            score = len(cand_dir)
        else:
            score = -1 

        if score > best_score:
            best_score = score
            best_candidate = cand

    if best_candidate and best_score >= 0:
        log(f"      DISAMBIGUATED {target_filename}: picked '{best_candidate.relative_to(SRC_BUNDLE_ROOT)}' (Score: {best_score})")
        return best_candidate
    
    return None

def find_bundle_recursive(container_path):
    parts = container_path.split('/')
    if len(parts) < 2: return None

    if parts[-2].lower() == "bg":
        target_name = parts[-1].rsplit('.', 1)[0]
        target_filename = f"{target_name}.assetbundle"
        log(f"    FOLDER 'bg' detected. Prioritizing: {target_filename}")
        found = find_bundle_disambiguated(container_path, target_filename)
        if found: return found

    start_index = len(parts) - 2
    min_index = 2 

    for i in range(start_index, min_index - 1, -1):
        candidate_name = parts[i]
        candidate_filename = f"{candidate_name}.assetbundle"
        
        found = find_bundle_disambiguated(container_path, candidate_filename)
        if found:
            log(f"      MATCH FOUND AT: {found.relative_to(SRC_BUNDLE_ROOT)}")
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

def save_debug_evidence(bundle_img, replace_img, name):
    evidence_dir = Path(DEBUG_EVIDENCE_DIR)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = evidence_dir / f"EVIDENCE_BUNDLE_{name}.png"
    replace_path = evidence_dir / f"EVIDENCE_REPLACEMENT_{name}.png"
    bundle_img.save(bundle_path)
    replace_img.save(replace_path)
    log(f"      [DEBUG] Saved comparison to: {bundle_path}")

def generate_mesh(replacement_img, name):
    print("--- Start Mesh Generation ---")
    print("Opening replacement image...")
    replacement = Image.open(replacement_img)

    os.makedirs(ALPHA_OUTPUT_ROOT, exist_ok=True)
    os.makedirs(OBJ_OUTPUT_ROOT, exist_ok=True)

    alpha_path = os.path.join(ALPHA_OUTPUT_ROOT, f"{name}_alpha.png")
    obj_path = os.path.join(OBJ_OUTPUT_ROOT, f"{name}.obj")
    obj_dec_path = os.path.join(OBJ_OUTPUT_ROOT, f"{name}_dec.obj")
    
    if 'A' in replacement.getbands():
        alpha = replacement.getchannel('A')
    else:
        print("No alpha channel found, using grayscale...")
        alpha = replacement.convert('L')
    
    alpha.save(alpha_path)
    print(f"Saved alpha to: {alpha_path}")

    print("Loading distance map...")
    settings = mr.DistanceMapLoadSettings()
    dm = mr.loadDistanceMapFromImage(alpha_path, 0)

    print("Generating contours...")
    polyline2 = mr.distanceMapTo2DIsoPolyline(dm, isoValue=127.0)

    print("Triangulating...")
    mesh = mr.triangulateContours(polyline2.contours())

    # Repack mesh optimally.
    mesh.packOptimally()

    # Save Output
    print(f"Saving to {obj_path}...")
    mr.saveMesh(mesh, obj_path)

    # Setup decimate parameters
    settings = mr.DecimateSettings()
    settings.maxError = 0.05 
    settings.subdivideParts = 64

    # Simplify mesh
    mr.decimateMesh(mesh, settings)

    mr.saveMesh(mesh, obj_dec_path)
    
    if os.path.exists(obj_path):
        print(f"SUCCESS: Saved {name}.obj")
    else:
        print("ERROR: File was not created.")

    return mesh

def parse_obj_mesh(file_path):
    vertices = []
    uvs = []
    indices = []
    
    with open(file_path, "r") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                # Sprites are 2D; OBJ Z usually maps to 0 or is ignored
                vertices.append({"x": float(p[1]), "y": float(p[2]), "z": 0.0})
            elif line.startswith("vt "):
                p = line.split()
                uvs.append({"x": float(p[1]), "y": float(p[2])})
            elif line.startswith("f "):
                # Basic triangle parser (assumes triangulated OBJ)
                p = line.split()
                for part in p[1:]:
                    indices.append(int(part.split('/')[0]) - 1)
    return vertices, uvs, indices

def replace_sprite_mesh(sprite, new_mesh_path, name):
    print(f"--- Overwriting Mesh for Sprite {name} ---")
    
    # 1. Parse OBJ for Mesh Data from the file path
    new_verts, new_uvs, new_indices = parse_obj_mesh(new_mesh_path)
    
    # Access Render Data
    m_rd = sprite.m_RD
    
    # Update Vertices (combining pos and uv)
    if len(new_uvs) == len(new_verts):
            m_rd.vertices = [{"pos": v, "uv": u} for v, u in zip(new_verts, new_uvs)]
    else:
            m_rd.vertices = [{"pos": v} for v in new_verts]
    
    # Update Indices
    m_rd.indices = new_indices
    
    # Update Submesh
    if hasattr(m_rd, "m_SubMeshes") and len(m_rd.m_SubMeshes) > 0:
        m_rd.m_SubMeshes[0].indexCount = len(new_indices)
    
    sprite.save()
    print(f"Successfully injected {len(new_verts)} vertices into Sprite.")
    return sprite


def run_strict_replacement():
    log(f"--- Starting Replacement ---")
    
    injection_stats = Counter()
    total_skipped = 0
    
    log("Parsing XML...")
    try:
        tree = ET.parse(XML_INDEX_PATH)
        root = tree.getroot()
    except Exception as e:
        log(f"XML ERROR: {e}"); return

    xml_lookup = {}
    for asset in root.findall('Asset'):
        a_type = asset.find('Type').text if asset.find('Type') is not None else ""
        if a_type != "Texture2D": continue
        
        name = asset.find('Name').text
        if name not in xml_lookup: xml_lookup[name] = []
        
        xml_lookup[name].append({
            "Container": asset.find('Container').text,
            "PathID": int(asset.find('PathID').text)
        })
    
    rep_root = Path(REPLACEMENT_ROOT)
    valid_images = [p for p in rep_root.rglob("*") if p.suffix.lower() in ['.png', '.jpg', '.jpeg']]
    log(f"Found {len(valid_images)} images to process.")
    
    bundle_tasks = {}

    for img_path in valid_images:
        target_name = img_path.stem
        rel_path = img_path.relative_to(rep_root)
        disk_key = str(rel_path.with_suffix('')).replace('\\', '/').lower()
        disk_dir = os.path.dirname(disk_key)

        if target_name not in xml_lookup: continue

        for cand in xml_lookup[target_name]:
            container_clean = cand['Container'].rsplit('.', 1)[0].lower()
            
            log(f"CHECKING: {target_name}")
            log(f"   XML Container: '{cand['Container']}'")
            
            match_direct = container_clean.endswith(disk_dir)
            container_parent = os.path.dirname(container_clean)
            match_parent = container_parent.endswith(disk_dir)
            
            if match_direct or match_parent:
                actual_bundle = find_bundle_recursive(cand['Container'])
                
                if actual_bundle:
                    b_key = str(actual_bundle)
                    if b_key not in bundle_tasks: bundle_tasks[b_key] = []
                    bundle_tasks[b_key].append({
                        "name": target_name,
                        "path_id": cand['PathID'],
                        "img_path": img_path
                    })
                    break 
                else:
                    log(f"   FAILED: Bundle search failed for {cand['Container']}")

    if not bundle_tasks:
        log("\nNo matching tasks found.")
        return

    total_bundles = len(bundle_tasks)
    log(f"\nProcessing {total_bundles} bundles...")
    
    for idx, (b_path, tasks) in enumerate(bundle_tasks.items(), 1):
        src_p = Path(b_path)
        progress = (idx / total_bundles) * 100
        
        log(f"\n[{progress:6.2f}%] ({idx}/{total_bundles}) STARTING BUNDLE: {src_p.name}")
        
        try:
            rel = src_p.relative_to(SRC_BUNDLE_ROOT)
            dst_p = Path(OUTPUT_ROOT) / rel
        except:
            dst_p = Path(OUTPUT_ROOT) / src_p.name
            
        try:
            env = UnityPy.load(str(src_p))
            mod = False
            t_map = {t['path_id']: t for t in tasks}
            
            # Run a pre-scan for Sprites
            target_texture_names = set(t['name'] for t in t_map.values())
            
            # Use a dictionary: {SpriteName: PathID} so we can target it correctly later
            matching_sprites = {}
            for obj in env.objects:
                if obj.type.name == "Sprite":
                    try:
                        data = obj.read()
                        if data.m_Name in target_texture_names:
                            matching_sprites[data.m_Name] = obj.path_id 
                    except:
                        continue
            
            sprite_mesh_tasks = {}

            # Source Bundle Loop and Mesh Generation
            for obj in env.objects:
                if obj.path_id in t_map:
                    task = t_map[obj.path_id]
                    inst = obj.parse_as_object()
                    
                    with Image.open(task['img_path']) as img:
                        replacement_img = img
                        current_img = inst.image
                        
                        current_hash = get_image_hash(current_img)
                        repl_hash = get_image_hash(replacement_img)
                        
                        if current_hash == repl_hash:
                             log(f"   SKIPPING {inst.m_Name}: MD5 MATCH")
                             total_skipped += 1
                        else:
                            # Flag modification for this bundle
                            mod = True
                            rel_path_str = str(src_p.relative_to(SRC_BUNDLE_ROOT)).replace('\\', '/')
                            injection_stats[rel_path_str] += 1
                            
                            # Check if we have a matching Sprite
                            if inst.m_Name in matching_sprites:
                                log(f"      MATCHING SPRITE FOUND: {inst.m_Name}")
                                
                                # Generate Mesh from Image
                                generate_mesh(task['img_path'], inst.m_Name)
                                generated_obj_path = os.path.join(OBJ_OUTPUT_ROOT, f"{inst.m_Name}.obj")
                                
                                # Queue this sprite for update in the final output loop
                                sprite_pid = matching_sprites[inst.m_Name]
                                sprite_mesh_tasks[sprite_pid] = {
                                    "obj_path": generated_obj_path,
                                    "name": inst.m_Name
                                }
                            else:
                                #log(f"      No matching Sprite found for {inst.m_Name}")
                                generate_mesh(task['img_path'], inst.m_Name)

            if mod:
                if not copy_bundle_file(src_p, dst_p): continue
                
                # Final Output Loop
                out_env = UnityPy.load(str(dst_p))
                
                for obj in out_env.objects:
                    # Update Textures
                    if obj.path_id in t_map:
                        task = t_map[obj.path_id]
                        tex = obj.parse_as_object()
                        with Image.open(task['img_path']) as img:
                             tex.image = img
                             tex.save()
                             log(f"   INJECTED TEXTURE: {tex.m_Name}")

                    # Update Sprites
                    elif obj.path_id in sprite_mesh_tasks:
                        task = sprite_mesh_tasks[obj.path_id]
                        sprite = obj.parse_as_object()
                        replace_sprite_mesh(sprite, task['obj_path'], task['name'])
                
                with open(dst_p, "wb") as f:
                    f.write(out_env.file.save(packer="original"))
            else:
                log(f"   No changes needed for bundle: {src_p.name}")

        except Exception as e:
            log(f"BUNDLE ERROR in {src_p.name}: {e}")

    log("\n" + "="*60)
    log("                  FINAL INJECTION SUMMARY")
    log("="*60)
    if not injection_stats:
        log("No injections were performed.")
    else:
        for bundle_path, count in sorted(injection_stats.items()):
            log(f" BUNDLE: {bundle_path:<40} | {count:>3} injection(s)")
    
    log("-" * 60)
    log(f"Total Successful Injections: {sum(injection_stats.values())}")
    log(f"Total Skipped (Identical):    {total_skipped}")
    log("="*60 + "\n")

if __name__ == "__main__":
    if os.path.exists(LOG_FILE_PATH):
        try: os.remove(LOG_FILE_PATH)
        except: pass
    run_strict_replacement()