"""The model's one tool (AGENTS.md §3.2 rule 3 / §5.6).

`offer_help_desk_ticket` never writes to the database. Calling it only
makes the server emit a `ticket_offer` SSE event; a human must click
"Yes", which hits a separate authenticated endpoint (`POST /api/tickets`)
that reads the user from the session, never from anything the model said.
"""

from app.llm.base import ToolDefinition

OFFER_HELP_DESK_TICKET = ToolDefinition(
    name="offer_help_desk_ticket",
    description=(
        "Offer to open a help-desk ticket because the SOURCES do not contain enough "
        "information to answer the question. This does not create a ticket by itself; "
        "it only shows the user a Yes/No prompt."
    ),
    parameters={
        "type": "object",
        "properties": {
            "suggested_title": {
                "type": "string",
                "description": "A short (80 characters or fewer) title summarising the question.",
            },
        },
        "required": ["suggested_title"],
        "additionalProperties": False,
    },
)

ALL_TOOLS = [OFFER_HELP_DESK_TICKET]
