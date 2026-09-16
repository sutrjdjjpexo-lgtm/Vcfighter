# Runtime state for all configured/connected voice chats.
joined_chat_ids = set()
current_chat_id = None
fight_file = None
fight_running = False
target_chat_id = None  # backwards-compatible alias for the currently selected chat

reactions_enabled = True
