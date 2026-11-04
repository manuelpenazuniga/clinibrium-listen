import { ListeningOrb } from "@/components/listening-orb";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-16 text-center">
      <ListeningOrb state="listening" />
      <div className="flex max-w-md flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">Clinibrium Listen</h1>
        <p className="text-muted-foreground">
          El médico dicta. Los modelos escuchan, estructuran y preguntan. El motor
          determinístico decide la seguridad. El médico decide.
        </p>
        <p className="text-sm text-muted-foreground">
          The physician dictates. Models listen, structure and ask. A deterministic
          engine makes the safety call. The physician decides.
        </p>
      </div>
    </main>
  );
}
