---
name: unslop
description: De-slop a file or a piece of text on request, against the prose catalogue.
disable-model-invocation: true
---

Run the `/mx:writing-for-humans` pass over what the user names (a file, a diff, the last message): apply every rule of its `CATALOGUE.md` to every sentence, fix each hit in place where the text is yours to edit and report it otherwise, by rule id. Nothing named means the file or text most recently discussed.
