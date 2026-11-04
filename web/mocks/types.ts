import type {
  ConfirmationRequest,
  EngineResultView,
  FieldState,
  OnsetInfo,
  Question,
  ReasonerView,
  Receipt,
  ReferralLetter,
} from "@/lib/contracts"
import type { DemoCase } from "@/lib/demo-cases"

/** Partial SessionState applied by the mock. `fields` merge by key; lists replace. */
export type StatePatch = {
  fields?: Record<string, FieldState>
  questions?: Question[]
  confirmations?: ConfirmationRequest[]
  /** Onset is given relative to session start so the clock is live. */
  onset?: (startedAt: Date) => OnsetInfo | null
  result?: EngineResultView | null
}

export type MockScript = {
  demo: DemoCase
  /** One step per incoming text_turn (or mock-ASR utterance), in order. */
  steps: StatePatch[]
  /** Applied when a document image is uploaded. */
  document?: StatePatch
  /** Extra patch applied when the clinician confirms a given key. */
  onConfirm?: Record<string, StatePatch>
  finalize: { reasoning: ReasonerView; letter: ReferralLetter; receipt: Receipt }
}
