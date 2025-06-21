import asyncio
import threading
import webbrowser
import gradio as gr

from assistant_controller.project_manager import ProjectManager
from assistant_controller.gradio_ui import create_combined_ui
from ai_memory.codecanvas.context_manager import ContextManager
from .ui_script_loader import get_canvas_plugins_ui

# Global context & project manager
pm = ProjectManager(profile="default")
context = ContextManager()

async def async_canvas_ui(pm_override=None, chat_handler_override=None, context_override=None):
    from assistant_controller.chat_handler import ChatHandler

    pm_instance = pm_override or pm
    context_instance = context_override or context

    def get_project_path_safe():
        if pm_instance and hasattr(pm_instance, "get_current_project"):
            return pm_instance.get_current_project()
        elif context_instance and hasattr(context_instance, "project_path"):
            return context_instance.project_path
        return None

    chat_handler = chat_handler_override or ChatHandler(get_project_path=get_project_path_safe)

    # === Main Canvas UI Container ===
    with gr.Blocks(title="Code Canvas", analytics_enabled=False) as demo:
        gr.Markdown("# ?? Code Canvas")

        # Load plugin UIs
        plugins_block = await get_canvas_plugins_ui(context_instance)

        tab_names = [
            "CodeRunnerTab",
            "FeedbackTab",
            "ProjectTreeViewerTab",
            "CanvasPlugins",
            "AssistantEmbedTab"
        ]

        tab_labels = {
            "CodeRunnerTab": "Code Runner",
            "FeedbackTab": "Feedback Loop",
            "ProjectTreeViewerTab": "Project Tree Viewer",
            "CanvasPlugins": "Canvas Plugins",
            "AssistantEmbedTab": "Assistant UI Embedded",
        }

        with gr.Tabs():
            for tab_key in tab_names:
                with gr.Tab(tab_labels.get(tab_key, tab_key)):
                    if tab_key == "CanvasPlugins":
                        demo.append(plugins_block)  # ? Append already-rendered plugin block
                    elif tab_key == "AssistantEmbedTab":
                        with gr.Column() as assistant_ui_container:
                            gr.Markdown("Loading Assistant UI...")
                        # Populate Assistant UI asynchronously
                        asyncio.create_task(
                            populate_assistant_ui(assistant_ui_container, pm_instance, chat_handler, context_instance)
                        )
                    else:
                        plugin = context_instance.plugins.get(tab_key)
                        if plugin:
                            ui_comp = plugin.get("ui")
                            if ui_comp:
                                try:
                                    if hasattr(ui_comp, "render"):
                                        ui_comp.render()
                                    elif isinstance(ui_comp, (gr.Blocks, gr.Tabs)):
                                        ui_comp  # Already evaluated
                                    elif callable(ui_comp):
                                        result = await ui_comp() if asyncio.iscoroutinefunction(ui_comp) else ui_comp()
                                        result
                                except Exception as e:
                                    gr.Markdown(f"Plugin `{tab_key}` failed: `{e}`")

    return demo

async def populate_assistant_ui(container, pm, chat_handler, context):
    from assistant_controller.gradio_ui import create_combined_ui
    assistant_ui = await create_combined_ui(pm, chat_handler, context)
    container.clear()
    container.append(assistant_ui)  # ? Don't call render()

def open_browser_later(url: str, delay: int = 3):
    import time
    time.sleep(delay)
    webbrowser.open_new_tab(url)

async def main_async():
    demo = await async_canvas_ui()
    return demo

def main():
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    demo = asyncio.run(main_async())

    url = "http://127.0.0.1:7861"
    threading.Thread(target=open_browser_later, args=(url,), daemon=True).start()

    demo.launch(
        server_port=7861,
        inbrowser=False,
        prevent_thread_lock=True,
        share=False,
        quiet=False,
    )

if __name__ == "__main__":
    main()

# 컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴�
# Exportable render() for external caller
# 컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴컴�
async def render(*args, **kwargs):
    return await async_canvas_ui(*args, **kwargs)
