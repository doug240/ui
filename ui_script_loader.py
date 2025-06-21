import os
import re
import importlib.util
import logging
import traceback
import time
import json
import asyncio
import gradio as gr

from ai_memory.codecanvas.context_manager import ContextManager

CANVAS_DIR = os.path.dirname(__file__)
CACHE_FILE = os.path.join(CANVAS_DIR, ".plugin_cache.json")

EXCLUDED_FILES = {
    "__init__.py",
    "canvas_ui.py",
    "ui_core_logic.py",
    "ui_script_loader.py",
    "context_manager.py",
    "tree_utils.py",  # Added here to exclude this file from plugins
}

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(CANVAS_DIR, "plugin_loader.log")),
        logging.StreamHandler()
    ]
)

def extract_metadata(lines, key):
    key_lower = f"# {key.lower()}:"
    for line in lines:
        if line.lower().startswith(key_lower):
            return line.split(":", 1)[1].strip()
    return ""

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load plugin cache: {e}")
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save plugin cache: {e}")

def is_plugin_file(filename):
    return (
        filename.endswith(".py") 
        and filename not in EXCLUDED_FILES 
        and not filename.startswith("__")
    )

def find_plugin_files(root_dir, recursive=True):
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for file in filenames:
            if is_plugin_file(file):
                files.append(os.path.join(dirpath, file))
        if not recursive:
            break
    return files

def has_register_plugin(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return re.search(r"def\s+register_plugin\s*\(", content) is not None
    except Exception as e:
        logger.warning(f"Failed to check register_plugin in {filepath}: {e}")
        return False

async def maybe_await(obj):
    if asyncio.iscoroutine(obj):
        return await obj
    return obj

# === FIXED: Safer and clearer UI resolver ===
async def resolve_plugin_ui(ui_candidate):
    if asyncio.iscoroutine(ui_candidate):
        return await ui_candidate

    if isinstance(ui_candidate, (gr.Blocks, gr.Tabs)):
        logger.info("UI is already a Gradio container instance")
        return ui_candidate

    if callable(ui_candidate):
        if asyncio.iscoroutinefunction(ui_candidate):
            result = await ui_candidate()
        else:
            result = ui_candidate()

        if isinstance(result, (gr.Blocks, gr.Tabs)):
            logger.info("UI function returned a Gradio container")
            return result

        logger.info("UI function returned a component")
        return result

    logger.warning("UI value was neither callable nor a known container")
    return ui_candidate

async def load_plugin_module(path):
    try:
        spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        logger.error(f"Failed to import plugin module {path}: {e}\n{traceback.format_exc()}")
        return None

async def initialize_plugin(mod, context, path, title):
    start_time = time.time()
    plugin_obj = None
    version = getattr(mod, "__version__", None)
    requires = getattr(mod, "__requires__", None)

    if requires:
        logger.info(f"Plugin '{title}' requires: {requires}")

    try:
        if hasattr(mod, "register_plugin"):
            plugin_obj = await maybe_await(mod.register_plugin(context))
            logger.info(f"Registered plugin '{title}' version {version or 'unknown'} from {path}")
        else:
            logger.warning(f"Plugin '{title}' missing 'register_plugin(context)' function")
            return None

        if hasattr(mod, "register_hooks"):
            await maybe_await(mod.register_hooks(context))
            logger.info(f"Registered hooks for plugin '{title}'")

        if not isinstance(plugin_obj, dict) or "ui" not in plugin_obj:
            logger.warning(f"Plugin '{title}' did not return valid plugin dict with 'ui' key")
            return None

        plugin_ui = await resolve_plugin_ui(plugin_obj["ui"])

        elapsed = time.time() - start_time
        logger.info(f"Plugin '{title}' initialized in {elapsed:.2f}s")

        return {
            "title": title,
            "description": extract_metadata(open(path, encoding='utf-8').readlines(), "description"),
            "ui": plugin_ui,
            "version": version,
            "path": path,
            "plugin_obj": plugin_obj
        }

    except Exception as e:
        logger.error(f"Error initializing plugin '{title}': {e}\n{traceback.format_exc()}")
        return None

async def get_canvas_plugins(context=None, recursive=True, use_cache=True):
    if context is None:
        context = ContextManager()
    plugins = {}

    plugin_files = find_plugin_files(CANVAS_DIR, recursive=recursive)
    logger.info(f"Found {len(plugin_files)} plugin files")

    cache = load_cache() if use_cache else {}

    for path in plugin_files:
        mtime = os.path.getmtime(path)
        cache_entry = cache.get(path)
        if use_cache and cache_entry and cache_entry.get("mtime") == mtime:
            logger.info(f"Loading plugin metadata from cache: {path}")
            mod = await load_plugin_module(path)
            if not mod:
                continue
            plugin_obj = await maybe_await(mod.register_plugin(context))
            plugin_ui = await resolve_plugin_ui(plugin_obj.get("ui"))

            plugins[cache_entry["title"]] = {
                **cache_entry,
                "plugin_obj": plugin_obj,
                "ui": plugin_ui,
                "path": path
            }
            continue

        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            title = extract_metadata(lines, "title") or os.path.basename(path)
            mod = await load_plugin_module(path)
            if not mod:
                continue
            plugin_data = await initialize_plugin(mod, context, path, title)
            if plugin_data:
                plugins[plugin_data["title"]] = plugin_data
                cache[path] = {
                    "title": plugin_data["title"],
                    "description": plugin_data["description"],
                    "mtime": mtime,
                    "version": plugin_data["version"]
                }
        except Exception as e:
            logger.error(f"Failed loading plugin {path}: {e}\n{traceback.format_exc()}")

    if use_cache:
        save_cache(cache)

    context.plugins = plugins
    return plugins, context

async def load_scripts(context):
    logger.info("Running async load_scripts() for one-time plugin runners")
    scripts_executed = []

    for title, plugin in context.plugins.items():
        plugin_obj = plugin.get("plugin_obj")
        if plugin_obj and hasattr(plugin_obj, "run"):
            try:
                result = await maybe_await(plugin_obj.run())
                scripts_executed.append((title, "success", result))
                logger.info(f"Executed plugin.run() for {title}")
            except Exception as e:
                scripts_executed.append((title, "error", str(e)))
                logger.error(f"Error executing plugin.run() for {title}: {e}\n{traceback.format_exc()}")

    return scripts_executed

def prepare_plugins():
    print("[patcher] Skipped patching; manual fixes required.")

async def get_canvas_plugins_ui(context=None):
    if context is None:
        context = ContextManager()

    plugins, context = await get_canvas_plugins(context=context)
    await load_scripts(context)

    with gr.Tabs() as plugins_ui:
        if not plugins:
            with gr.TabItem("No Plugins"):
                gr.Markdown("No plugins loaded or available.")
        else:
            for title, plugin_data in plugins.items():
                description = plugin_data.get("description", "(No description)")
                plugin_ui = plugin_data.get("ui")

                with gr.TabItem(title):
                    gr.Markdown(description)
                    if plugin_ui:
                        try:
                            if hasattr(plugin_ui, "render"):
                                plugin_ui.render()
                            elif isinstance(plugin_ui, (gr.Blocks, gr.Tabs)):
                                plugin_ui.render()
                            elif callable(plugin_ui):
                                plugin_ui()
                            else:
                                pass
                        except Exception as e:
                            gr.Markdown(f"\u26a0\ufe0f Failed to render UI: {e}")

    return plugins_ui

if __name__ == "__main__":
    prepare_plugins()
