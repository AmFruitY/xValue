import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "xValue — Cada conexión revela valor",
  description:
    "Resultados del modelo xValue 2025/26: rango estimado del importe de traspaso por jugador y club, con su referencia de mercado. Comprar, vender y comparar.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
