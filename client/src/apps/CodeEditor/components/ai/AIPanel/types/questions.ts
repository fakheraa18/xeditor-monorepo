// Shared types and constants for question handling

export interface QuestionOption {
  id: string;
  label: string;
}

export interface Question {
  id: string;
  prompt: string;
  options: QuestionOption[];
  allow_multiple?: boolean;
}

export interface PendingQuestion {
  title?: string;
  questions: Question[];
}

export interface QuestionResponseData {
  type: 'question_response';
  title: string;
  responses: Array<{
    question: string;
    answers: string[];
  }>;
}

export interface QuestionSkippedData {
  type: 'question_skipped';
  title?: string;
  questions: Question[];
  user_message: string;
}

// Marker constants for structured messages
export const QUESTION_RESPONSE_MARKER = '<!--QUESTION_RESPONSE-->';
export const QUESTION_SKIPPED_MARKER = '<!--QUESTION_SKIPPED-->';
