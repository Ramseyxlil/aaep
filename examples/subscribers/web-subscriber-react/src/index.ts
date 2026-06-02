/**
 * Public entry point for @aaep/web-subscriber-react.
 *
 * Re-exports the main component and supporting types so consumers can:
 *
 *     import {
 *         AAEPSubscriber,
 *         useAAEPEvents,
 *         type AAEPEvent,
 *         type AAEPSubscriberProps,
 *     } from "@aaep/web-subscriber-react";
 */

export { AAEPSubscriber } from "./AAEPSubscriber.js";
export type { AAEPSubscriberProps } from "./AAEPSubscriber.js";

export { useAAEPEvents } from "./useAAEPEvents.js";
export type {
  UseAAEPEventsOptions,
  UseAAEPEventsResult,
} from "./useAAEPEvents.js";

export type {
  AAEPClarificationEvent,
  AAEPConfirmationEvent,
  AAEPDefaultDecision,
  AAEPEvent,
  AAEPEventEnvelope,
  AAEPEventType,
  AAEPRiskLevel,
  AAEPUrgency,
  ConnectionStatus,
  ReplyResult,
} from "./types.js";

export {
  isClarificationEvent,
  isConfirmationEvent,
  isCriticalEvent,
} from "./types.js";


/** Package metadata for runtime version checks. */
export const VERSION = "1.0.0";
export const AAEP_SPEC_VERSION = "1.0.0";
