import gradio as gr
import os
import asyncio
from ai_memory.codecanvas.context_manager import ContextManager
from assistant_controller.project_manager import ProjectManager

# Shared context (singleton)
default_context = ContextManager()

async def create_combined_ui(pm=None, chat_handler=None, context=None):
    ctx = context or default_context
    pm = pm or ProjectManager()

    # Load plugins once, asynchronously, get plugins dict and possibly updated context
    from ai_memory.codecanvas.ui_script_loader import get_canvas_plugins
    plugins, ctx = await get_canvas_plugins(context=ctx)

    # Create chat handler if not provided, passing shared ContextManager
    from assistant_controller.chat_handler import ChatHandler
    if chat_handler is None:
        chat_handler = ChatHandler(
            context_manager=ctx,
            get_project_path=lambda: ctx.project_path,
            get_active_tab=lambda: ctx.active_tabs[-1] if ctx.active_tabs else "UnknownTab"
        )

    with gr.Blocks() as ui:
        with gr.Tab("🧠 Assistant UI"):
            gr.Markdown("## AI Assistant with Memory and File Analysis")

            with gr.Row():
                project_path_input = gr.Textbox(
                    label="Set Active Project Path",
                    value=ctx.project_path or os.getcwd(),
                    placeholder="Enter full path to your active project folder"
                )
                path_status = gr.Textbox(label="Project Path Status", interactive=False)
                set_path_button = gr.Button("Set Path")

                def set_path(path):
                    ctx.set_project_path(path)
                    return f"Project path set to: {path}"

                set_path_button.click(set_path, inputs=[project_path_input], outputs=[path_status])

            chatbot = gr.Chatbot(label="Chat", type="messages")
            msg = gr.Textbox(placeholder="Type your message here and hit enter...")
            error_box = gr.Textbox(label="Error Output", lines=4, interactive=False)

            async def chatbot_submit(user_message, chat_history):
                ctx.set_active_tabs(["Assistant UI"])
                response = await chat_handler.process_input(user_message)
                chat_history = chat_history or []
                chat_history.append({"role": "user", "content": user_message})
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, chat_history, ""

            msg.submit(chatbot_submit, inputs=[msg, chatbot], outputs=[chatbot, chatbot, error_box])

        with gr.Tab("Code Canvas"):
            # Await async_canvas_ui with loaded plugins
            from ai_memory.codecanvas.canvas_ui import async_canvas_ui

            # Because we're inside sync context manager, we can't await directly here.
            # So we'll use asyncio.create_task and a placeholder container.
            canvas_ui_container = gr.Column()
            
            # Schedule the async loading and UI population task
            asyncio.create_task(
                populate_canvas_ui(canvas_ui_container, pm, chat_handler, ctx, plugins)
            )

    return ui


async def populate_canvas_ui(container, pm, chat_handler, ctx, plugins):
    from ai_memory.codecanvas.canvas_ui import async_canvas_ui

    canvas_ui = await async_canvas_ui(pm, chat_handler, ctx, plugins)
    container.clear()
    container.append(canvas_ui)  # append without calling render()


# Optional synchronous launcher helper for standalone runs
def main():
    import sys
    import threading
    import webbrowser

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def _main_async():
        pm = ProjectManager(profile="default")
        ctx = ContextManager()
        from assistant_controller.chat_handler import ChatHandler
        chat_handler = ChatHandler(context_manager=ctx, get_project_path=lambda: ctx.project_path)

        ui = await create_combined_ui(pm, chat_handler, ctx)
        return ui

    demo = asyncio.run(_main_async())

    def open_browser_later(url="http://127.0.0.1:7861", delay=3):
        import time
        time.sleep(delay)
        webbrowser.open_new_tab(url)

    threading.Thread(target=open_browser_later, daemon=True).start()

    demo.launch(
        server_port=7861,
        inbrowser=False,
        prevent_thread_lock=True,
        share=False,
        quiet=False,
    )


if __name__ == "__main__":
    main()

