import Ajv2020, { type AnySchema, type ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";
import sseEventContract from "../generated/sse-events.json";
import type { ChatStreamEvent } from "../generated/sse-events";

type SseContract = {
  schema: Record<string, unknown> & { discriminator?: unknown };
};

const validationSchema = { ...(sseEventContract as SseContract).schema };
delete validationSchema.discriminator;
const ajv = new Ajv2020({ strict: true });
addFormats(ajv);
const validate: ValidateFunction<ChatStreamEvent> = ajv.compile(validationSchema as AnySchema);

export function isChatStreamEvent(value: unknown): value is ChatStreamEvent {
  return validate(value);
}
