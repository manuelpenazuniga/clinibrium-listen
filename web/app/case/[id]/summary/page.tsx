import { Suspense } from "react"

import { SummaryScreen } from "@/components/summary/summary-screen"

export default function SummaryPage({ params }: PageProps<"/case/[id]/summary">) {
  return (
    <Suspense fallback={<div className="flex-1" />}>
      {params.then(({ id }) => (
        <SummaryScreen sessionId={id} />
      ))}
    </Suspense>
  )
}
