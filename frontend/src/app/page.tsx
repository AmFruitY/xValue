import { XValueLanding } from "@/components/landing/xvalue-landing";
import { getFeaturedPlayer } from "@/lib/data/player-repository";
import { createPlayerPresentation } from "@/lib/presentation/player-presentation";

export default function Home() {
  const player = getFeaturedPlayer();
  const presentation = createPlayerPresentation(player);

  return <XValueLanding player={player} presentation={presentation} />;
}
