# VCFighter — Railway VC Fight Player

## What it does

1. `/join <group_id>` → user account joins/gets ready for that group's active Voice Chat.
2. Reply to a Telegram audio/voice message and send `/fight`.
3. The replied audio is downloaded and repeatedly played into the joined VC.
4. `/fightstop` stops the audio but keeps the account in VC.
5. `/leave` stops everything and leaves VC.

The bot also sends a startup message to `CONTROL_GROUP_ID`. `/ping`, `/help`, `/status` work in private chat and the configured control group.

## Railway variables

- `API_ID`
- `API_HASH`
- `SESSION_STRING`
- `CONTROL_GROUP_ID`

`CONTROL_GROUP_ID` is only used for the startup notification and command access. The actual VC target is supplied with `/join`.

## Commands

- `/join -1001234567890`
- `/fight` — reply to audio/voice
- `/fightstop`
- `/status`
- `/leave`
- `/ping`
- `/help`

Do not commit Telegram credentials or session strings to GitHub.


## Automatic reactions

After a group is registered with `/join <group_id>`, the client watches incoming
messages in that group. For each active user, the latest message can receive one
random reaction (`🌚 😂 😅 😭 😘 ♥️`) after one hour.

Commands:
- `/reaction on`
- `/reaction off`

Optional Railway variable:
- `REACTION_INTERVAL=3600` (seconds; default 1 hour)
