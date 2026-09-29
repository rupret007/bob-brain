"""Fast, server-owned capability answers. These questions never perform actions."""
import re


QUESTIONS = {
    'overview': ('what can you do', 'what can you help with', 'how can you help me',
                 'what are your capabilities', 'what can web bob do'),
    'texting': ('can you send texts', 'can you send text messages', 'can you text',
                'can you send messages', 'can you read my texts', 'can you text people'),
    'instinct': ('can you text instinct', 'can you send messages to instinct',
                'can you send texts to instinct', 'can you reply to instinct'),
    'memory': ('can you remember things', 'can you remember things about me',
               'how does your memory work', 'is my memory private',
               'where do you save memories'),
    'reminders': ('can you set reminders', 'can you remind me', 'can you set routines'),
    'media': ('can you read images', 'can you see photos', 'can you read files',
              'can you watch videos', 'can i attach files'),
    'voice': ('can we talk', 'can you do voice calls', 'can i talk to you'),
    'workers': ('can you start workers', 'can you run coding jobs',
                'can you use other models', 'can you run council'),
}


def topic(text):
    # Full-turn matching avoids stealing real requests, quoted text, or a
    # recipient/body from the handlers that enforce approval and privacy.
    normalized = re.sub(r'\s+', ' ', text.strip().casefold()).rstrip('?.!')
    normalized = re.sub(r'^(?:hey bob[, ]+|bob[, ]+)', '', normalized)
    return next((key for key, phrases in QUESTIONS.items() if normalized in phrases), None)


def reply(text, root):
    kind = topic(text)
    if kind is None:
        return None
    paused = ((root / 'conductor/MAINTENANCE').exists() or
              (root / 'conductor/SOLO-WORKER').exists())
    worker = ('Additional workers and council are paused for solo work; Jobs shows the observed activity.'
              if paused else 'Coding jobs can be queued for draft work; Jobs shows whether they actually start.')
    answers = {
        'overview': ('I can help with writing and songs, research with sources, saved memories, reminders, '
                     'and attached photos or files. You can talk with me using the call button, read texts, '
                     'or review an exact draft before sending through Andrea. Instinct stays read-only. ' + worker),
        'texting': ('Yes—Web Bob supports reading texts and sending a reviewed draft to a direct recipient through '
                    'Andrea’s BlueBubbles bridge. Review the exact recipient and message, then confirm that draft '
                    'separately. A missing delivery receipt means delivery is unconfirmed; use Check delivery on '
                    'the draft to inspect it without resending. Instinct stays read-only.'),
        'instinct': ('I can read and summarize Instinct’s messages and prepare an unsent reply draft. '
                     'Instinct is read-only here; its drafts cannot be sent from Web Bob.'),
        'memory': ('Ask “remember that…” and I’ll show the memory for your confirmation before saving it locally. '
                   'Ask “show my saved memories” to inspect confirmed Web Bob notes directly. '
                   'Saved memories can be included in future model context, so they are not device-only. '
                   'Private texting turns are excluded from model chat context; don’t save secrets as memories.'),
        'reminders': ('Yes—ask “remind me to stretch in 10 minutes” or set a recurring reminder. '
                      'Reminders appear in this chat while Web Bob is running; they are not phone push notifications.'),
        'media': ('Yes—attach a photo, file, or video with your question. I can use extracted text and supported '
                  'image analysis; video uses sampled frames and available transcript, not every moment. '
                  'If something cannot be read, I’ll say so.'),
        'voice': ('Yes—tap the call button and allow microphone access for a two-way voice conversation. '
                   'You can interrupt me or hang up; the transcript stays in this conversation.'),
        'workers': worker,
    }
    return answers.get(kind)
