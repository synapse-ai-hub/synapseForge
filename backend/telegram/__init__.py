"""Telegram integration package.

The bot is a thin bridge: it receives Telegram updates (polling) and emits
events to the event bus. The frontend consumes those events and runs the
exact same chat flow as if the user had typed in the web UI. The bot never
re-streams agent events itself.
"""