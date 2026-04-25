export function isWakeIntent(text: string) {
  const t = text.toLowerCase().trim();

  // Direct name triggers
  if (/(zendaya|zenda|z-day|zey|zayda|zai)/.test(t)) return true;

  // Greeting + presence triggers
  if (/(hey|yo|hi|okay|ok|alright|listen|wake up|hello|hey girl)/.test(t)) {
    if (/(zendaya|assistant|girl|bestie|sis|boss)/.test(t)) return true;
  }

  // Conversational triggers ("wake intent" without name)
  if (
    /(i need you|can you hear me|you there|come here|listen to me|talk to me|help me|what's good|are you awake)/.test(
      t
    )
  ) {
    return true;
  }

  // slang / AI assistant social speech
  if (/(yo|hey bae|hey love|girl come on|alexa but better)/.test(t)) return true;

  return false;
}
