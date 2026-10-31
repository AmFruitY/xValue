import type { NextRequest } from "next/server";
import { getPredictionRepository } from "@/lib/predictions/repository";
import { queryFromSearchParams } from "@/lib/predictions/query";

/** GET /api/predictions — filtered, sorted page of model results. The browser never receives the Parquet file. */
export async function GET(request: NextRequest) {
  try {
    const page = await getPredictionRepository().query(queryFromSearchParams(request.nextUrl.searchParams));
    return Response.json(page);
  } catch (error) {
    console.error(error);
    return Response.json({ error: "No se pudieron leer los resultados del modelo." }, { status: 500 });
  }
}
