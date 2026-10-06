# Twitch chat

BT can read your live chat when you ask.

## Set up
1. In the app's settings page, find the **Twitch chat** section.
2. Tick **Let BT read my live chat** and type your channel name (a pasted twitch.tv link works too).
3. The status line should say "connected to #yourchannel". The box underneath shows the latest messages he has
   kept, so you can see what he would read.

There is no login, token or account: it connects the way anyone can to *read* a public chat, anonymously.
It cannot post. If a firewall blocks it, the status line shows the reason.

## Asking
While a conversation is open ("hey BT" first), say things like:
- "Read me the last three chat messages."
- "What is chat saying?"
- "Read the last two comments."
- "Any new comments from my viewers?"

No number means three. The most he will read at once is set on the page (default 5). He reads each message in his
own voice, says who wrote it, and may add one short remark. If chat is not connected or has been quiet, he says so
with a fixed line instead of making something up.

## What he will not read
- Messages from bots (the ignore list is editable; Nightbot, StreamElements and similar are on it).
- Chat commands that start with "!", your own messages, and copy-paste spam.
- Emotes, which are removed so he does not say "LUL LUL LUL". Links are spoken as "a link".
- Anything containing a word from your **never read** list.
- **Anything a moderator deletes, or from a user who is banned or timed out.** Those are removed from what he has
  kept, so he cannot read out something that was taken down.
- Chat text is handed to the model as quoted, untrusted data with instructions not to follow it, and to skip anything
  hateful or sexual. That reduces risk but is not a guarantee, so if his voice is on your stream, keep your blocked
  words list filled in and consider whether viewers can bait him.

## Not tested live
This was tested against a fake Twitch server on the build machine, not against real Twitch.
