import asyncio
import threading
import webbrowser
import gradio as gr
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def async_canvas_ui(pm, chat_handler, context, plugins):
    """
    Main async UI builder for Code Canvas.
    `plugins` expected as dict: {plugin_name: plugin_dict_with_ui_key}
    """
    with gr.Blocks(title="Code Canvas", analytics_enabled=False) as demo:
        gr.Markdown("# 🧠 Code Canvas")

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
                        # Render all plugin UIs
                        for name, plugin in plugins.items():
                            try:
                                ui_comp = plugin.get("ui")
                                # Await coroutine or async callable UI components
                                if asyncio.iscoroutine(ui_comp):
                                    ui_comp = await ui_comp
                                elif callable(ui_comp):
                                    if asyncio.iscoroutinefunction(ui_comp):
                                        ui_comp = await ui_comp()
                                    else:
                                        ui_comp = ui_comp()
                                # Log type for debug
                                logger.info(f"Plugin '{name}' UI type after await: {type(ui_comp)}")
                                # UI component is expected to be a Gradio component or container
                                # Just placing ui_comp here to include it in UI
                                ui_comp
                            except Exception as e:
                                gr.Markdown(f"⚠️ Failed to load plugin `{name}`: {e}")

                    elif tab_key == "AssistantEmbedTab":
                        with gr.Column() as assistant_ui_container:
                            gr.Markdown("Loading Assistant UI...")
                        # Schedule async population of assistant UI tab
                        asyncio.create_task(
                            populate_assistant_ui(assistant_ui_container, pm, chat_handler, context)
                        )
                    else:
                        # Render UI for individual plugin matching this tab key, if exists
                        plugin = plugins.get(tab_key)
                        if plugin:
                            ui_comp = plugin.get("ui")
                            if ui_comp:
                                try:
                                    if asyncio.iscoroutine(ui_comp):
                                        ui_comp = await ui_comp
                                    elif callable(ui_comp):
                                        if asyncio.iscoroutinefunction(ui_comp):
                                            ui_comp = await ui_comp()
                                        else:
                                            ui_comp = ui_comp()
                                    logger.info(f"Plugin '{tab_key}' UI type after await: {type(ui_comp)}")
                                    ui_comp
                                except Exception as e:
                                    gr.Markdown(f"⚠️ Plugin `{tab_key}` failed: {e}")

    return demo


async def populate_assistant_ui(container, pm, chat_handler, context):
    """
    Populate the Assistant UI tab asynchronously.
    """
    from assistant_controller.gradio_ui import create_combined_ui
    assistant_ui = await create_combined_ui(pm, chat_handler, context)
    container.clear()
    # Insert assistant_ui directly, assumed to be a Gradio component/container
    container.append(assistant_ui)


def open_browser_later(url: str, delay: int = 3):
    import time
    time.sleep(delay)
    webbrowser.open_new_tab(url)


async def main_async():
    from assistant_controller.project_manager import ProjectManager
    from ai_memory.codecanvas.context_manager import ContextManager
    from assistant_controller.chat_handler import ChatHandler
    from .ui_script_loader import get_canvas_plugins_ui

    pm = ProjectManager(profile="default")
    context = ContextManager()
    # Pass context to ChatHandler for better state coordination
    chat_handler = ChatHandler(
        context_manager=context,
        get_project_path=pm.get_current_project
    )

    # Get plugin dict, must be dict not Gradio UI container
    plugins = await get_canvas_plugins_ui(context)
    if not isinstance(plugins, dict):
        logger.warning(f"Expected plugins dict but got {type(plugins)}; attempting to continue")

    demo = await async_canvas_ui(pm, chat_handler, context, plugins)
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


# ─────────────────────────────────────────────
# Exportable render() for external caller
# ─────────────────────────────────────────────
async def render(pm, chat_handler, context, plugins, *args, **kwargs):
    return await async_canvas_ui(pm, chat_handler, context, plugins)


if __name__ == "__main__":
    main()

# ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
# Exportable render() for external caller
# ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
async def render(*args, **kwargs):
    return await async_canvas_ui(*args, **kwargs)
