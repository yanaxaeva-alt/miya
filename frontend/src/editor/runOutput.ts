export function extractMiaQuestion(
  outputs: Record<string, string>,
  inputText: string,
): string {
  return outputs.START?.trim() || inputText.trim();
}

export interface MiaAnswerView {
  text: string | null;
  hint?: string;
}

export function extractMiaAnswer(
  outputs: Record<string, string>,
  status?: string,
): MiaAnswerView {
  if (outputs.END?.trim()) {
    return { text: outputs.END.trim() };
  }

  const entries = Object.entries(outputs).filter(
    ([nodeId, text]) => nodeId !== 'START' && text.trim().length > 0,
  );

  if (entries.length === 0) {
    return { text: null };
  }

  if (status === 'waiting_for_approval') {
    const draft = entries.findLast(([, text]) => !text.startsWith('approval_request:'));
    if (draft) {
      return {
        text: draft[1].trim(),
        hint: 'Черновик до согласования — одобрите в Approval Queue, чтобы получить финальный ответ.',
      };
    }
  }

  const last = entries.at(-1);
  return last ? { text: last[1].trim() } : { text: null };
}
