import { Suspense } from "react"

import { CaseScreen } from "@/components/case/case-screen"

export default function CasePage({ params, searchParams }: PageProps<"/case/[id]">) {
  return (
    <Suspense fallback={<div className="flex-1" />}>
      <CaseLoader params={params} searchParams={searchParams} />
    </Suspense>
  )
}

async function CaseLoader({
  params,
  searchParams,
}: Pick<PageProps<"/case/[id]">, "params" | "searchParams">) {
  const { id } = await params
  const { demo } = await searchParams
  return <CaseScreen sessionId={id} demoId={typeof demo === "string" ? demo : null} />
}
