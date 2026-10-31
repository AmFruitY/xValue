import { NeuralDemo } from "@/components/neural/neural-demo";
import { getPredictionRepository, type FeaturedRecords } from "@/lib/predictions/repository";
import type { PredictionFacets } from "@/lib/predictions/types";

// Read the model results per request so a regenerated Parquet is picked up without a rebuild.
export const dynamic = "force-dynamic";

export default async function Home() {
  const repository = getPredictionRepository();
  let facets: PredictionFacets = { total: 0, leagues: [], seasons: [], withMarketValue: 0, rangeFactors: null, source: "—" };
  let featured: FeaturedRecords = { primary: null, secondary: null };
  let loadError = false;
  try {
    [facets, featured] = await Promise.all([repository.facets(), repository.featured()]);
  } catch (error) {
    console.error(error);
    loadError = true;
  }
  return <NeuralDemo facets={facets} primary={featured.primary} secondary={featured.secondary} loadError={loadError} />;
}
