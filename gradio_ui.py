import gradio as gr
import os
import asyncio
from ai_memory.codecanvas.context_manager import ContextManager

# Shared context (singleton)
default_context = ContextManager()

async def create_combined_ui(pm=None, chat_handler=None, context=None):
    # Use passed context or fallback to default
    ctx = context or default_context

    # Delayed import to prevent circular import problems
    from assistant_controller.chat_handler import ChatHandler

    # Create chat handler if not provided, **pass context_manager here!**
    if chat_handler is None:
        chat_handler = ChatHandler(
            context_manager=ctx,
            get_project_path=lambda: ctx.project_path,
            get_active_tab=lambda: ctx.active_tabs[-1] if ctx.active_tabs else "UnknownTab"
        )

    with gr.Blocks() as ui:
        with gr.Tab("🧠 Assistant UI"):
            gr.Markdown("## AI Assistant with Memory and File Analysis")

            # Project path selector UI
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

            # Chatbot UI
            chatbot = gr.Chatbot(label="Chat", type="messages")
            msg = gr.Textbox(placeholder="Type your message here and hit enter...")
            error_box = gr.Textbox(label="Error Output", lines=4, interactive=False)

            # Async submit handler
            async def chatbot_submit(user_message, chat_history):
                ctx.set_active_tabs(["Assistant UI"])
                response = await chat_handler.process_input(user_message)
                chat_history = chat_history or []
                chat_history.append({"role": "user", "content": user_message})
                chat_history.append({"role": "assistant", "content": response})
                return chat_history, chat_history, ""

            msg.submit(chatbot_submit, inputs=[msg, chatbot], outputs=[chatbot, chatbot, error_box])

        with gr.Tab("Code Canvas"):
            canvas_ui_container = gr.Column()
            # async background population of Canvas UI tab
            asyncio.create_task(populate_canvas_ui(canvas_ui_container, pm, chat_handler, ctx))

    return ui


async def populate_canvas_ui(container, pm, chat_handler, ctx):
    from ai_memory.codecanvas.canvas_ui import render

    canvas_ui = await render(pm, chat_handler, ctx)
    container.clear()

    # ✅ FIX: Don't call .render(), just append container
    container.append(canvas_ui)
