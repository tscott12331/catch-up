/**
 * This file was generated from the backend-owned chat SSE schema.
 * Do not make direct changes to this file.
 */

export type ChatStreamEvent = MessageStartedEvent | MessageDeltaEvent | MessageCompletedEvent | MessageErrorEvent;
/**
 * A UUID version 4 identifier.
 */
export type ConversationId = string;
/**
 * A UUID version 4 identifier.
 */
export type MessageId = string;
/**
 * A UUID version 4 identifier.
 */
export type RepositoryId = string;
export type Type = "message.started";
/**
 * A UUID version 4 identifier.
 */
export type UserMessageId = string;
/**
 * A UUID version 4 identifier.
 */
export type ConversationId1 = string;
/**
 * A UUID version 4 identifier.
 */
export type MessageId1 = string;
/**
 * A UUID version 4 identifier.
 */
export type RepositoryId1 = string;
export type Text = string;
export type Type1 = "message.delta";
export type EndLine = number;
/**
 * A UUID version 4 identifier.
 */
export type Id = string;
/**
 * A UUID version 4 identifier.
 */
export type PassageId = string;
export type Path = string;
export type Revision = string;
export type StartLine = number;
export type Citations = Citation[];
/**
 * A UUID version 4 identifier.
 */
export type ConversationId2 = string;
/**
 * A UUID version 4 identifier.
 */
export type MessageId2 = string;
/**
 * A UUID version 4 identifier.
 */
export type RepositoryId2 = string;
export type Type2 = "message.completed";
export type Code = string;
/**
 * A UUID version 4 identifier.
 */
export type ConversationId3 = string;
export type Message = string;
/**
 * A UUID version 4 identifier.
 */
export type MessageId3 = string;
/**
 * A UUID version 4 identifier.
 */
export type RepositoryId3 = string;
export type Type3 = "message.error";

export interface MessageStartedEvent {
  conversation_id: ConversationId;
  message_id: MessageId;
  repository_id: RepositoryId;
  type: Type;
  user_message_id: UserMessageId;
}
export interface MessageDeltaEvent {
  conversation_id: ConversationId1;
  message_id: MessageId1;
  repository_id: RepositoryId1;
  text: Text;
  type: Type1;
}
export interface MessageCompletedEvent {
  citations: Citations;
  conversation_id: ConversationId2;
  message_id: MessageId2;
  repository_id: RepositoryId2;
  type: Type2;
}
export interface Citation {
  end_line: EndLine;
  id: Id;
  passage_id: PassageId;
  path: Path;
  revision: Revision;
  start_line: StartLine;
}
export interface MessageErrorEvent {
  code: Code;
  conversation_id: ConversationId3;
  message: Message;
  message_id: MessageId3;
  repository_id: RepositoryId3;
  type: Type3;
}
